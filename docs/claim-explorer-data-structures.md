# Claim Explorer 데이터 구조

> 이 문서는 Claim Explorer 모듈의 데이터 모델을 정의한다.
> 탐색 전략, 기능/비기능 요구사항은 [claim-explorer-requirements.md](./claim-explorer-requirements.md)를 참조한다.
>
> **PoC 범위**: Round 1(초기 검색) + Round 2(관련성 필터)만 구현. Paper 노드만 사용하며, CITES 관계와 citation 관련 쿼리는 Post-PoC에서 구현한다.

## 1. 저장소 개요

### 1.1 Neo4j

논문과 인용 관계를 그래프로 관리한다. 탐색 라운드가 진행될수록 그래프가 점진적으로 확장되며, 여러 claim 탐색에서 축적된 그래프를 재활용할 수 있다.

### 1.2 왜 그래프 DB인가

| 요구 | 관계형 DB | 그래프 DB (Neo4j) |
|------|-----------|-------------------|
| citation 경로 탐색 (1-hop, 2-hop) | JOIN 중첩, 성능 저하 | 인접 노드 순회, O(1) per hop |
| 공통 인용 논문 발견 | 다중 self-join | 패턴 매칭 한 줄 |
| 스키마 유연성 (provider별 메타데이터 차이) | ALTER TABLE | 속성 자유 추가 |
| 그래프 시각화 / 디버깅 | 별도 도구 필요 | Neo4j Browser 내장 |

## 2. 노드 (Node)

### 2.1 Paper

탐색 과정에서 발견된 모든 논문을 나타낸다.

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `doi` | string | * | DOI (unique constraint) |
| `pmid` | string | * | PMID (unique constraint) |
| `title` | string | O | 논문 제목 |
| `authors` | string[] | | 저자 목록 |
| `year` | int | | 출판 연도 |
| `abstract` | string | | 초록 |
| `venue` | string | | 학술지명 |
| `source_provider` | string | | 최초 발견 provider (openalex, europepmc, crossref) |
| `created_at` | datetime | O | 노드 생성 시각 (자동) |
| `updated_at` | datetime | O | 마지막 업데이트 시각 (자동) |

`*` doi 또는 pmid 중 **하나 이상** 반드시 존재해야 한다.

**MERGE 전략:**

```
doi가 있으면  → MERGE ON doi  → pmid가 있으면 SET
pmid만 있으면 → MERGE ON pmid
```

두 값 모두 있는 경우 doi를 우선 키로 사용한다. ON MATCH에서는 기존 값이 null인 필드만 업데이트(coalesce)하여 데이터 손실을 방지한다.

## 3. `[Post-PoC]` 관계 (Relationship)

### 3.1 CITES

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

## 4. 인덱스 및 제약조건

```cypher
-- 고유 제약조건
CREATE CONSTRAINT paper_doi_unique IF NOT EXISTS
FOR (p:Paper) REQUIRE p.doi IS UNIQUE;

CREATE CONSTRAINT paper_pmid_unique IF NOT EXISTS
FOR (p:Paper) REQUIRE p.pmid IS UNIQUE;

-- 검색용 인덱스
CREATE INDEX paper_year IF NOT EXISTS
FOR (p:Paper) ON (p.year);

CREATE FULLTEXT INDEX paper_text IF NOT EXISTS
FOR (p:Paper) ON EACH [p.title, p.abstract];
```

## 5. 라운드별 그래프 구축 흐름

각 탐색 라운드에서 그래프가 점진적으로 확장된다.

```
Round 1 (다중 각도 초기 검색) [PoC]
  ┌──────────────────────────────────┐
  │ provider 검색 결과 → Paper MERGE │
  │ CITES 관계 없음                   │
  └──────────────────────────────────┘

Round 2 (관련성 빠른 필터) [PoC]
  ┌──────────────────────────────────────────┐
  │ LLM이 relevance 판단                      │
  │ 그래프 구조 변경 없음                       │
  │ (relevance는 탐색 출력에만 포함, 그래프 외부) │
  └──────────────────────────────────────────┘

Round 3 (Citation Graph 확장) [Post-PoC]
  ┌──────────────────────────────────────────────┐
  │ high 논문의 references/cited-by API 조회       │
  │ 새 Paper 노드 MERGE                           │
  │ CITES 관계 생성                                │
  │ 이미 그래프에 존재하는 관계는 API 호출 건너뜀    │
  └──────────────────────────────────────────────┘

Round 4 (적응적 재검색, 조건부) [Post-PoC]
  ┌──────────────────────────────────┐
  │ 추가 검색 결과 → Paper MERGE     │
  └──────────────────────────────────┘
```

## 6. 주요 Cypher 쿼리 패턴

### 6.1 논문 MERGE (중복 방지)

```cypher
MERGE (p:Paper {doi: $doi})
ON CREATE SET p.title = $title, p.authors = $authors,
             p.year = $year, p.abstract = $abstract,
             p.venue = $venue, p.source_provider = $provider,
             p.created_at = datetime(), p.updated_at = datetime()
ON MATCH SET  p.abstract = coalesce(p.abstract, $abstract),
              p.venue = coalesce(p.venue, $venue),
              p.updated_at = datetime()
RETURN p
```

### 6.2 `[Post-PoC]` CITES 관계 MERGE

```cypher
MATCH (a:Paper {doi: $citing_doi}), (b:Paper {doi: $cited_doi})
MERGE (a)-[r:CITES]->(b)
ON CREATE SET r.source = $source, r.discovered_at = datetime()
RETURN r
```

### 6.3 `[Post-PoC]` Backward citation 확장 (참고문헌 추적)

```cypher
MATCH (seed:Paper {doi: $doi})-[:CITES]->(ref:Paper)
WHERE NOT ref.doi IN $already_found
RETURN ref
```

### 6.4 `[Post-PoC]` Forward citation 확장 (피인용 추적)

```cypher
MATCH (citing:Paper)-[:CITES]->(seed:Paper {doi: $doi})
WHERE NOT citing.doi IN $already_found
RETURN citing
```

### 6.5 `[Post-PoC]` 2-hop 확장 (공통 인용 논문 발견)

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

### 6.6 `[Post-PoC]` 그래프에 이미 citation 정보가 있는지 확인

Round 3에서 API 호출 전에 그래프를 먼저 확인하여 불필요한 호출을 줄인다.

```cypher
MATCH (p:Paper {doi: $doi})-[:CITES]->()
RETURN count(*) > 0 AS has_outgoing_citations
```

## 7. `[Post-PoC]` 그래프 재활용

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

## 8. 탐색 메타데이터와 그래프의 역할 분리

### 8.1 원칙

Neo4j 그래프에는 **객관적 서지 사실**(Paper 노드, CITES 관계)만 저장한다. 탐색 과정에서 생성되는 **claim-specific 메타데이터**(관련성 판단, 발견 경로)는 탐색 출력(ExploreOutput JSON)에만 포함한다.

| 데이터 | 성격 | 저장 위치 |
|--------|------|-----------|
| Paper 메타데이터 (doi, title, abstract...) | 서지 사실 (불변) | Neo4j Paper 노드 |
| CITES 관계 | 서지 사실 (불변) | Neo4j CITES 관계 |
| relevance, relevance_reason | claim-specific 판단 (가변) | ExploreOutput JSON |
| discovery_method, discovered_via | 탐색 경로 기록 (가변) | ExploreOutput JSON |

### 8.2 discovered_via

citation 확장(Round 3)으로 발견된 논문의 출발점을 추적하는 필드.

**discovery_method와의 관계:**

| discovery_method | discovered_via | 의미 |
|------------------|----------------|------|
| `initial_search` | null | 검색 질의로 직접 발견 |
| `citation_backward` | seed 논문 DOI | seed 논문의 참고문헌에서 발견 |
| `citation_forward` | seed 논문 DOI | seed 논문을 인용한 논문으로 발견 |
| `re_search` | null | 적응적 재검색으로 직접 발견 |

**예시:**

```
CatBoost 논문(10.48550/arXiv.1706.09516)이 Round 2에서 high로 평가됨
  → Round 3에서 이 논문의 참고문헌을 추적
  → XGBoost 논문(10.1145/2939672.2939785)을 발견

XGBoost 논문의 탐색 메타데이터:
  discovery_method: "citation_backward"
  discovered_via: "10.48550/arXiv.1706.09516"
  relevance_reason: "CatBoost가 비교 대상으로 삼는 gradient boosting 프레임워크의 원저"
```

이 조합으로 "어떤 논문이 → 어떤 방식으로 → 어떤 seed로부터 발견되었는지"가 완전히 추적 가능하다(FR-14 충족).

### 8.3 CITES에 citation context를 넣지 않는 이유

| 관점 | 설명 |
|------|------|
| 데이터 확보 | 현재 API(OpenAlex, Crossref, Europe PMC)는 인용 관계만 반환. citation context(인용 문맥)는 논문 전문 접근이 필요하며 대부분 유료/접근 불가 |
| claim 의존성 | 같은 CITES 관계라도 탐색하는 claim에 따라 해석이 달라짐. claim A에서는 "method 원저로서", claim B에서는 "비교 baseline으로서" 관련될 수 있음 |
| 그래프 공유 | CITES는 여러 claim 탐색에 걸쳐 공유되는 구조이므로, claim-specific 해석을 넣으면 충돌 |
| 기존 해결책 | relevance_reason + discovered_via 조합이 동일한 정보를 탐색 결과 레벨에서 제공 |

### 8.4 Neo4j에 탐색 이력을 넣지 않는 이유

Exploration 노드(`(:Exploration)-[:FOUND]->(:Paper)`)를 도입하면 여러 claim 횡단 분석이 가능하지만, 현재 단계에서는 도입하지 않는다.

| 관점 | 설명 |
|------|------|
| 스킬 정체성 | explorer는 stateless 함수(input → output). 탐색 이력을 Neo4j에 쌓으면 stateful 서비스가 됨 |
| 데이터 성격 혼재 | Paper/CITES는 도메인 데이터(실세계 서지 사실). Exploration은 운영 데이터(시스템 행위 기록). 같은 그래프에 혼재 |
| 무한 성장 | Paper/CITES는 실세계 논문 수로 bounded. Exploration은 실행 횟수에 비례해 무한 성장 |
| YAGNI | 횡단 분석의 소비자가 현재 없음. 필요 시 JSON 출력 파일 사후 분석 또는 별도 저장소 도입 |

## 9. Python 데이터 모델

탐색 로직에서 사용하는 Pydantic 모델 정의. Neo4j 노드/관계와 1:1 매핑된다.

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class Relevance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRELATED = "unrelated"


class DiscoveryMethod(str, Enum):
    INITIAL_SEARCH = "initial_search"
    CITATION_BACKWARD = "citation_backward"
    CITATION_FORWARD = "citation_forward"
    RE_SEARCH = "re_search"


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
    seed_papers: list[str] = Field(default_factory=list)
    max_papers: int = 10


class PaperNode(BaseModel):
    """Neo4j Paper 노드와 매핑되는 모델"""
    doi: str | None = None
    pmid: str | None = None
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
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    venue: str | None = None
    relevance: Relevance
    relevance_reason: str
    discovery_method: DiscoveryMethod
    discovered_via: str | None = None  # citation 확장 시 출발점 seed 논문의 DOI


class SearchRound(BaseModel):
    round: int
    type: str
    queries: list[str] = Field(default_factory=list)
    papers_found: int
    papers_kept: int
    duration_seconds: float


class ExploreOutput(BaseModel):
    papers: list[ExploredPaper]
    search_log: list[SearchRound]
    summary: str
```
