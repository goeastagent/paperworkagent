# Claim Explorer 데이터 구조

> 이 문서는 Claim Explorer 모듈의 데이터 모델을 정의한다.
> 탐색 전략, 기능/비기능 요구사항은 [claim-explorer-requirements.md](./claim-explorer-requirements.md)를 참조한다.
>
> **PoC 범위**: Round 1(초기 검색) + Round 2(관련성 필터)만 구현. in-memory 중복 제거를 사용하며, Neo4j는 Post-PoC에서 도입한다.

## 1. 저장소 개요

### 1.1 PoC: In-Memory + 파일 캐시

PoC에서는 탐색 과정의 논문 데이터를 **in-memory 딕셔너리**로 관리하고, 캐싱은 **파일 기반 로그**로 수행한다. 별도 DB 의존성 없이 동작한다.

| 역할 | PoC 구현 | Post-PoC 전환 |
|------|----------|---------------|
| 논문 중복 제거 | in-memory dict (DOI/PMID/PMCID/title 키) | Neo4j MERGE |
| 논문 메타데이터 저장 | ExploreOutput JSON 출력 | Neo4j Paper 노드 |
| 캐싱 | 파일 기반 JSON 로그 | 동일 (파일 캐시 유지) |
| citation 관계 | 미구현 | Neo4j CITES 관계 |

### 1.2 `[Post-PoC]` Neo4j

논문과 인용 관계를 그래프로 관리한다. 탐색 라운드가 진행될수록 그래프가 점진적으로 확장되며, 여러 claim 탐색에서 축적된 그래프를 재활용할 수 있다.

**왜 그래프 DB인가:**

| 요구 | 관계형 DB | 그래프 DB (Neo4j) |
|------|-----------|-------------------|
| citation 경로 탐색 (1-hop, 2-hop) | JOIN 중첩, 성능 저하 | 인접 노드 순회, O(1) per hop |
| 공통 인용 논문 발견 | 다중 self-join | 패턴 매칭 한 줄 |
| 스키마 유연성 (provider별 메타데이터 차이) | ALTER TABLE | 속성 자유 추가 |
| 그래프 시각화 / 디버깅 | 별도 도구 필요 | Neo4j Browser 내장 |

## 2. 중복 제거

### 2.1 식별자 우선순위

provider 간 중복 논문을 다음 우선순위로 비교하여 제거한다:

```
1. DOI가 있으면 → DOI로 비교 (정규화: 소문자, "https://doi.org/" 접두사 제거)
2. PMID가 있으면 → PMID로 비교
3. PMCID가 있으면 → PMCID로 비교
4. 모두 없으면 → title 정규화 비교
```

### 2.2 Title 정규화 비교

식별자가 모두 없는 논문은 title을 정규화하여 비교한다:
- 소문자 변환
- 구두점 제거
- 연속 공백 단일화
- 정규화된 title이 동일하면 같은 논문으로 간주

### 2.3 병합 규칙

동일 논문이 여러 provider에서 발견된 경우:
- 기존 메타데이터가 null인 필드만 새 값으로 채운다(coalesce)
- `source_provider`는 최초 발견 provider를 유지한다
- 식별자(doi, pmid, pmcid)는 가능한 한 모두 채운다

### 2.4 In-Memory 구현

```python
class PaperDeduplicator:
    """DOI/PMID/PMCID/title 기반 in-memory 중복 제거"""

    def __init__(self):
        self._by_doi: dict[str, PaperData] = {}
        self._by_pmid: dict[str, PaperData] = {}
        self._by_pmcid: dict[str, PaperData] = {}
        self._by_title: dict[str, PaperData] = {}  # 정규화된 title

    def add_or_merge(self, paper: PaperData) -> PaperData:
        """논문을 추가하거나, 이미 존재하면 병합하여 반환"""
        existing = self._find_existing(paper)
        if existing:
            return self._merge(existing, paper)
        self._index(paper)
        return paper
```

## 3. `[Post-PoC]` 노드 (Node)

### 3.1 Paper

탐색 과정에서 발견된 모든 논문을 나타낸다.

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `doi` | string | * | DOI (unique constraint) |
| `pmid` | string | * | PMID (unique constraint) |
| `pmcid` | string | * | PMCID (unique constraint) |
| `title` | string | O | 논문 제목 |
| `authors` | string[] | | 저자 목록 |
| `year` | int | | 출판 연도 |
| `abstract` | string | | 초록 |
| `venue` | string | | 학술지명 |
| `source_provider` | string | | 최초 발견 provider (openalex, europepmc, crossref) |
| `created_at` | datetime | O | 노드 생성 시각 (자동) |
| `updated_at` | datetime | O | 마지막 업데이트 시각 (자동) |

`*` doi, pmid, pmcid 중 **하나 이상** 반드시 존재해야 한다. 모두 없는 경우 title로 식별한다.

**MERGE 전략:**

```
doi가 있으면   → MERGE ON doi   → pmid/pmcid가 있으면 SET
pmid만 있으면  → MERGE ON pmid  → pmcid가 있으면 SET
pmcid만 있으면 → MERGE ON pmcid
모두 없으면    → MERGE ON normalized_title
```

## 4. `[Post-PoC]` 관계 (Relationship)

### 4.1 CITES

```
(:Paper)-[:CITES]->(:Paper)
```

논문 A가 논문 B를 참고문헌으로 인용하는 관계.

| 속성 | 타입 | 설명 |
|------|------|------|
| `source` | string | 인용 관계의 출처 provider (openalex, europepmc, crossref) |
| `discovered_at` | datetime | 관계 발견 시각 |

**방향 규칙:**

```
Backward citation (참고문헌 추적):
  (seed:Paper)-[:CITES]->(reference:Paper)
  "seed 논문이 reference를 인용함"

Forward citation (피인용 추적):
  (citing:Paper)-[:CITES]->(seed:Paper)
  "citing 논문이 seed를 인용함"
```

방향은 항상 **인용하는 쪽 → 인용되는 쪽**으로 일관한다.

## 5. `[Post-PoC]` 인덱스 및 제약조건

```cypher
-- 고유 제약조건
CREATE CONSTRAINT paper_doi_unique IF NOT EXISTS
FOR (p:Paper) REQUIRE p.doi IS UNIQUE;

CREATE CONSTRAINT paper_pmid_unique IF NOT EXISTS
FOR (p:Paper) REQUIRE p.pmid IS UNIQUE;

CREATE CONSTRAINT paper_pmcid_unique IF NOT EXISTS
FOR (p:Paper) REQUIRE p.pmcid IS UNIQUE;

-- 검색용 인덱스
CREATE INDEX paper_year IF NOT EXISTS
FOR (p:Paper) ON (p.year);

CREATE FULLTEXT INDEX paper_text IF NOT EXISTS
FOR (p:Paper) ON EACH [p.title, p.abstract];
```

## 6. `[Post-PoC]` 라운드별 그래프 구축 흐름

각 탐색 라운드에서 그래프가 점진적으로 확장된다.

```
Round 1 (다중 각도 초기 검색)
  ┌──────────────────────────────────┐
  │ provider 검색 결과 → Paper MERGE │
  │ CITES 관계 없음                   │
  └──────────────────────────────────┘

Round 2 (관련성 빠른 필터)
  ┌──────────────────────────────────────────┐
  │ LLM이 relevance 판단                      │
  │ 그래프 구조 변경 없음                       │
  │ (relevance는 탐색 출력에만 포함, 그래프 외부) │
  └──────────────────────────────────────────┘

Round 3 (Citation Graph 확장)
  ┌──────────────────────────────────────────────┐
  │ high 논문의 references/cited-by API 조회       │
  │ 새 Paper 노드 MERGE                           │
  │ CITES 관계 생성                                │
  │ 이미 그래프에 존재하는 관계는 API 호출 건너뜀    │
  └──────────────────────────────────────────────┘

Round 4 (적응적 재검색, 조건부)
  ┌──────────────────────────────────┐
  │ 추가 검색 결과 → Paper MERGE     │
  └──────────────────────────────────┘
```

## 7. `[Post-PoC]` 주요 Cypher 쿼리 패턴

### 7.1 논문 MERGE (중복 방지)

```cypher
MERGE (p:Paper {doi: $doi})
ON CREATE SET p.title = $title, p.authors = $authors,
             p.year = $year, p.abstract = $abstract,
             p.venue = $venue, p.source_provider = $provider,
             p.pmid = $pmid, p.pmcid = $pmcid,
             p.created_at = datetime(), p.updated_at = datetime()
ON MATCH SET  p.abstract = coalesce(p.abstract, $abstract),
              p.venue = coalesce(p.venue, $venue),
              p.pmid = coalesce(p.pmid, $pmid),
              p.pmcid = coalesce(p.pmcid, $pmcid),
              p.updated_at = datetime()
RETURN p
```

### 7.2 CITES 관계 MERGE

```cypher
MATCH (a:Paper {doi: $citing_doi}), (b:Paper {doi: $cited_doi})
MERGE (a)-[r:CITES]->(b)
ON CREATE SET r.source = $source, r.discovered_at = datetime()
RETURN r
```

### 7.3 Backward citation 확장 (참고문헌 추적)

```cypher
MATCH (seed:Paper {doi: $doi})-[:CITES]->(ref:Paper)
WHERE NOT ref.doi IN $already_found
RETURN ref
```

### 7.4 Forward citation 확장 (피인용 추적)

```cypher
MATCH (citing:Paper)-[:CITES]->(seed:Paper {doi: $doi})
WHERE NOT citing.doi IN $already_found
RETURN citing
```

### 7.5 2-hop 확장 (공통 인용 논문 발견)

seed 논문이 인용한 참고문헌을 다른 논문도 함께 인용하고 있다면, 그 논문은 관련성이 높을 가능성이 크다.

```cypher
MATCH (seed:Paper {doi: $doi})-[:CITES]->(ref:Paper)<-[:CITES]-(other:Paper)
WHERE other.doi <> seed.doi
  AND NOT other.doi IN $already_found
WITH other, count(ref) AS shared_refs
ORDER BY shared_refs DESC
LIMIT 10
RETURN other, shared_refs
```

### 7.6 그래프에 이미 citation 정보가 있는지 확인

Round 3에서 API 호출 전에 그래프를 먼저 확인하여 불필요한 호출을 줄인다.

```cypher
MATCH (p:Paper {doi: $doi})-[:CITES]->()
RETURN count(*) > 0 AS has_outgoing_citations
```

## 8. `[Post-PoC]` 그래프 재활용

동일 프로젝트 내에서 여러 claim을 순차 탐색하면, 이전 claim에서 구축한 Paper 노드와 CITES 관계가 그대로 남아있다.

**재활용 시나리오:**

```
Claim A 탐색
  → Paper X (high) 발견
  → Paper X의 references 20개 CITES 관계 구축

Claim B 탐색
  → 초기 검색에서 Paper X 재발견 (MERGE → 기존 노드 반환)
  → Paper X의 citation 확장 시 이미 CITES 관계 존재
  → API 호출 없이 그래프에서 즉시 조회 가능
```

**이점:**
- citation API 호출 횟수 감소 (비용/속도)
- 같은 분야의 claim들이 공유하는 핵심 논문이 자연스럽게 그래프 허브로 부상
- 탐색이 누적될수록 Round 3의 소요 시간 단축

## 9. 탐색 메타데이터 역할 분리

### 9.1 원칙

탐색 과정에서 생성되는 **claim-specific 메타데이터**(관련성 판단, 발견 경로)는 탐색 출력(ExploreOutput JSON)에만 포함한다. `[Post-PoC]` Neo4j 도입 시에도 객관적 서지 사실만 그래프에 저장한다.

| 데이터 | 성격 | 저장 위치 |
|--------|------|-----------|
| Paper 메타데이터 (doi, title, abstract...) | 서지 사실 (불변) | PoC: ExploreOutput JSON / Post-PoC: Neo4j Paper 노드 |
| `[Post-PoC]` CITES 관계 | 서지 사실 (불변) | Neo4j CITES 관계 |
| relevance, relevance_reason | claim-specific 판단 (가변) | ExploreOutput JSON |
| discovery_method, discovered_via | 탐색 경로 기록 (가변) | ExploreOutput JSON |

### 9.2 discovered_via

`[Post-PoC]` citation 확장(Round 3)으로 발견된 논문의 출발점을 추적하는 필드.

**discovery_method와의 관계:**

| discovery_method | discovered_via | 의미 |
|------------------|----------------|------|
| `initial_search` | null | 검색 질의로 직접 발견 |
| `citation_backward` | seed 논문 DOI | seed 논문의 참고문헌에서 발견 |
| `citation_forward` | seed 논문 DOI | seed 논문을 인용한 논문으로 발견 |
| `re_search` | null | 적응적 재검색으로 직접 발견 |

### 9.3 `[Post-PoC]` CITES에 citation context를 넣지 않는 이유

| 관점 | 설명 |
|------|------|
| 데이터 확보 | 현재 API(OpenAlex, Crossref, Europe PMC)는 인용 관계만 반환. citation context(인용 문맥)는 논문 전문 접근이 필요하며 대부분 유료/접근 불가 |
| claim 의존성 | 같은 CITES 관계라도 탐색하는 claim에 따라 해석이 달라짐. claim A에서는 "method 원저로서", claim B에서는 "비교 baseline으로서" 관련될 수 있음 |
| 그래프 공유 | CITES는 여러 claim 탐색에 걸쳐 공유되는 구조이므로, claim-specific 해석을 넣으면 충돌 |
| 기존 해결책 | relevance_reason + discovered_via 조합이 동일한 정보를 탐색 결과 레벨에서 제공 |

## 10. Python 데이터 모델

탐색 로직에서 사용하는 Pydantic 모델 정의.

```python
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from enum import Enum


class Relevance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRELATED = "unrelated"


class DiscoveryMethod(str, Enum):
    INITIAL_SEARCH = "initial_search"
    CITATION_BACKWARD = "citation_backward"   # [Post-PoC]
    CITATION_FORWARD = "citation_forward"     # [Post-PoC]
    RE_SEARCH = "re_search"                   # [Post-PoC]


class ExploreStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExploreIssueType(str, Enum):
    PROVIDER_FAILURE = "provider_failure"
    LLM_FAILURE = "llm_failure"
    LLM_PARSE_FAILURE = "llm_parse_failure"
    TIMEOUT = "timeout"
    NO_RESULTS = "no_results"


class ClaimType(str, Enum):
    BACKGROUND = "background"
    METHOD = "method"
    RESULT = "result"
    INTERPRETATION = "interpretation"
    LIMITATION = "limitation"


class ClaimContext(BaseModel):
    abstract: str
    paragraph: str
    claim_type: ClaimType


class ExploreInput(BaseModel):
    claim_text: str
    claim_context: ClaimContext
    seed_papers: list[str] = Field(default_factory=list)  # [Post-PoC]
    max_papers: int = 10


class PaperData(BaseModel):
    """탐색 과정에서 사용하는 논문 데이터 (in-memory 중복 제거 대상)"""
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    venue: str | None = None
    source_provider: str | None = None


class ExploredPaper(BaseModel):
    """탐색 결과로 반환되는 논문 (Paper 메타데이터 + 탐색 메타데이터)"""
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    venue: str | None = None
    relevance: Relevance
    relevance_reason: str
    discovery_method: DiscoveryMethod
    discovered_via: str | None = None  # [Post-PoC] citation 확장 시 출발점 seed 논문의 DOI


class SearchRound(BaseModel):
    round: int
    type: str
    queries: list[str] = Field(default_factory=list)
    papers_found: int
    papers_kept: int
    duration_seconds: float


class ExploreIssue(BaseModel):
    """탐색 중 발생한 개별 문제"""
    round: int
    type: ExploreIssueType
    message: str
    detail: str | None = None


class ExploreOutput(BaseModel):
    status: ExploreStatus
    issues: list[ExploreIssue] = Field(default_factory=list)
    papers: list[ExploredPaper]
    search_log: list[SearchRound]
    summary: str
```

## 11. 캐시 파일 구조

### 11.1 디렉터리 레이아웃

```
.cache/claim-explorer/
├── provider/
│   ├── openalex/
│   │   └── {query_hash}.json
│   ├── europepmc/
│   │   └── {query_hash}.json
│   └── crossref/
│       └── {query_hash}.json
└── llm/
    ├── query_generation/
    │   └── {input_hash}.json
    └── relevance_filter/
        └── {input_hash}.json
```

### 11.2 캐시 키 생성

| 대상 | 해시 입력 | 설명 |
|------|-----------|------|
| provider 검색 | `(provider_name, query_string)` | 동일 provider + 동일 쿼리 → 캐시 히트 |
| LLM 질의 생성 | `(claim_text, claim_type)` | 동일 claim + 동일 type → 캐시 히트 |
| LLM 관련성 판단 | `(claim_text, sorted_paper_identifiers)` | 동일 claim + 동일 논문 세트 → 캐시 히트 |

각 논문의 identifier는 DOI → PMID → PMCID → normalized_title 순으로 가용한 첫 번째 식별자를 사용한다.

`{query_hash}`, `{input_hash}`는 입력값의 SHA-256 해시 앞 16자리를 사용한다.

### 11.3 캐시 파일 형식

각 캐시 파일은 다음 구조를 따른다:

```json
{
  "cached_at": "2026-04-16T12:00:00Z",
  "input": { "...원본 입력..." },
  "output": { "...캐시된 응답..." }
}
```

TTL은 두지 않으며, 캐시 디렉터리 삭제로 초기화한다.
