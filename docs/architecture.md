# 논문 레퍼런스 에이전트 시스템 아키텍처

## 1. 문서 목적
본 문서는 시스템의 기술적 구조를 정의한다. 무엇을 만들어야 하는지는 `requirements.md`를 참조한다.

## 2. 설계 원칙

### 2.1 핵심 원칙

- 무료 또는 공개 API만 사용한다
- 파일 기반 워크플로를 우선한다
- 생의학 도메인을 기본 최적화 대상으로 한다
- LLM은 claim 추출, 검색 질의 생성, fact-check 판정의 핵심 처리 엔진이다. 단, 문헌 검색의 원천 데이터 소스로 사용하지 않는다
- 추천 결과는 반드시 근거와 함께 제공한다
- 각 단계의 산출물은 재실행 가능하도록 구조화 파일로 남긴다

### 2.2 비원칙

- 웹 UI를 초기 필수 구성요소로 두지 않는다
- 유료 API에 기능적으로 의존하지 않는다
- 단일 거대 프롬프트 기반 처리에 의존하지 않는다
- 근거 없는 LLM 생성 결과를 사실 검증 결과로 간주하지 않는다

## 3. 기술 스택

| 구분 | 선택 | 이유 |
|------|------|------|
| 언어 | Python 3.12+ | 과학 생태계, LLM 라이브러리, API 클라이언트 지원 |
| HTTP 클라이언트 | httpx | async 지원, connection pooling, timeout 제어 |
| 데이터 모델 | pydantic v2 | 스키마 검증, JSON 직렬화, 타입 안전성 |
| Markdown 파서 | markdown-it-py | CommonMark 준수, 확장 가능, AST 접근 |
| 결과 파일 파서 | pandas | csv/tsv/xlsx 통합 로드 |
| LLM 클라이언트 | litellm | 다중 provider 지원 (OpenAI, Anthropic 등) |
| 비동기 제어 | asyncio + semaphore | provider별 동시성 제한 |
| 캐시 | diskcache 또는 sqlite | 파일 기반, 별도 서버 불필요 |
| 설정 | pydantic-settings | `.env` + `project.yaml` 통합 로드 |
| 테스트 | pytest + pytest-asyncio | async 테스트 지원 |

## 4. 시스템 구조

### 4.1 모듈 구성 (MVP 4개 모듈)

과잉 분할을 피하고, MVP에서 실제로 end-to-end가 동작하는 4개 모듈로 시작한다.

```
┌─────────────────────────────────────────────────┐
│                  orchestrator                    │
│         (실행 순서 관리, 재실행 제어)               │
└──────┬──────────┬──────────┬──────────┬─────────┘
       │          │          │          │
  ┌────▼───┐ ┌───▼────┐ ┌───▼───┐ ┌───▼────┐
  │ ingest │ │retrieve│ │ assess│ │ write  │
  │        │ │        │ │       │ │        │
  │- md    │ │- query │ │- score│ │- report│
  │  parse │ │  gen   │ │- fact │ │- patch │
  │- claim │ │- search│ │  check│ │- refs  │
  │  extract│ │- dedup │ │- link │ │        │
  │        │ │- full  │ │       │ │        │
  │        │ │  text  │ │       │ │        │
  └────────┘ └────────┘ └───────┘ └────────┘
```

| 모듈 | 책임 | 포함 기능 |
|------|------|-----------|
| `ingest` | 입력 → 구조화 claim | Markdown 파싱, 결과 파일 로드, LLM claim 추출/분류 |
| `retrieve` | claim → 후보 논문 | 검색 질의 생성, provider 호출, 중복 제거, full-text/abstract 확보 |
| `assess` | claim + paper → 평가 | evidence span 추출, 관련성 점수, fact-check 라벨, rationale 생성 |
| `write` | 평가 결과 → 산출물 | 추천 정렬, 보고서, Markdown 패치, 참고문헌 섹션 |

MVP 이후 모듈이 커지면 분리할 수 있다. 예를 들어 `retrieve`에서 `fulltext`를 분리하는 것은 코드 크기가 정당화할 때 수행한다.

### 4.2 처리 단위

- `Manuscript`: 입력 원고 파일
- `Claim`: 원고에서 추출한 주장 단위
- `Paper`: 검색된 후보 문헌 단위
- `Assessment`: claim-paper 쌍의 평가 결과

## 5. 스킬 구조 (Cursor 스킬)

### 5.1 동작 방식

Cursor 스킬은 에이전트가 작업 방법을 학습하는 **지침 마크다운**이다. 에이전트가 스킬을 발견하면 SKILL.md를 읽고, 거기에 적힌 절차대로 shell 명령을 실행하고, 산출물 파일을 읽어 사용자에게 결과를 보고한다.

```
사용자 요청 → Cursor 에이전트가 스킬 발견 → SKILL.md 읽기
  → shell에서 Python 스크립트 실행 → 산출물 파일 생성
  → 에이전트가 산출물을 읽고 요약/후속 판단
```

스킬은 코드를 직접 실행하는 런타임이 아니다. 핵심 로직은 Python 패키지(`src/`)에 있고, 스킬은 에이전트에게 "어떤 명령을 실행하고, 어떤 파일을 확인하라"는 워크플로를 알려주는 역할이다.

스킬로 노출하는 단위는 에이전트가 의미 있게 호출할 수 있는 것으로 제한한다.

### 5.2 스킬 구성 (3개)

```
.cursor/skills/
├── paper-reference-agent/     # 전체 파이프라인 실행
│   └── SKILL.md
├── literature-search/         # 키워드/DOI로 관련 문헌 검색 (단독 사용 가능)
│   └── SKILL.md
└── fact-check-claim/          # 주장+논문 → support/contradict 판정 (단독 사용 가능)
    └── SKILL.md
```

| 스킬 | 입력 | 출력 | 용도 |
|------|------|------|------|
| `paper-reference-agent` | 원고 `.md`, 결과 파일 | `runs/<run_id>/` 아래 전체 산출물 | 전체 파이프라인 실행 |
| `literature-search` | 키워드, DOI, 주제 문장 | 후보 논문 목록 JSON | 문헌 검색만 단독 수행 |
| `fact-check-claim` | 주장 텍스트 + 논문 정보 | 라벨 + rationale | 개별 fact-check 수행 |

### 5.3 SKILL.md 골격

**paper-reference-agent/SKILL.md:**

```markdown
---
name: paper-reference-agent
description: >-
  논문 초안 Markdown과 결과 파일을 입력받아 주장 추출, 문헌 검색, 사실 검증,
  참고문헌 추천까지 전체 파이프라인을 실행한다. 사용자가 논문 레퍼런스 정리,
  참고문헌 추천, 인용 검증을 요청할 때 사용한다.
---

# Paper Reference Agent

## 워크플로

1. 사용자에게 원고 파일 경로와 결과 파일 디렉터리를 확인한다
2. 파이프라인을 실행한다:
   ```bash
   python -m paperworkagent.cli run \
     --manuscript <원고경로> \
     --results <결과디렉터리> \
     --out runs/<run_id>
   ```
3. 실행이 완료되면 산출물을 확인한다:
   - `runs/<run_id>/claims.jsonl` — 추출된 주장 목록을 읽고 요약
   - `runs/<run_id>/report.md` — 추천 보고서를 읽고 핵심 내용 전달
   - `runs/<run_id>/paper.with_refs.md` — 패치된 원고 존재 여부 확인
4. 근거 부족 또는 contradiction 경고가 있으면 사용자에게 알린다
5. 사용자가 특정 claim에 대해 추가 검토를 요청하면 부분 재실행한다:
   ```bash
   python -m paperworkagent.cli run \
     --from retrieve --run-dir runs/<run_id>
   ```
```

**literature-search/SKILL.md:**

```markdown
---
name: literature-search
description: >-
  키워드, DOI, 또는 주제 문장으로 관련 학술 문헌을 검색한다. 논문 찾기,
  선행연구 검색, 문헌 조사를 요청할 때 사용한다.
---

# Literature Search

## 워크플로

1. 사용자의 검색 의도를 파악한다 (키워드, DOI, 자연어 주제)
2. 검색을 실행한다:
   ```bash
   python -m paperworkagent.cli search \
     --query "<검색어>" \
     --providers openalex,crossref,europepmc \
     --max-results 20 \
     --out results.json
   ```
3. `results.json`을 읽고 결과를 정리한다:
   - 논문 제목, 저자, 연도, DOI
   - open access 여부
   - 검색어와의 관련성 요약
4. 사용자가 특정 논문의 상세 정보를 원하면 DOI로 추가 조회한다
```

**fact-check-claim/SKILL.md:**

```markdown
---
name: fact-check-claim
description: >-
  주장 텍스트와 논문 정보를 입력받아 support, partial, contradict, unrelated
  라벨과 근거 설명을 생성한다. 사실 검증, 주장 확인, 문헌 근거 확인을
  요청할 때 사용한다.
---

# Fact Check Claim

## 워크플로

1. 사용자에게 검증할 주장과 대상 논문(DOI 또는 제목)을 확인한다
2. fact-check를 실행한다:
   ```bash
   python -m paperworkagent.cli fact-check \
     --claim "<주장 텍스트>" \
     --paper-id "<DOI 또는 PMID>" \
     --out result.json
   ```
3. `result.json`을 읽고 결과를 보고한다:
   - fact-check 라벨 (support / partial / contradict / unrelated)
   - confidence 점수
   - 근거 설명 (rationale)
   - evidence span (해당 논문에서 근거가 된 문장)
4. confidence가 낮으면 사용자에게 수동 확인을 권고한다
```

### 5.4 에이전트 판단 지점

스킬은 단순 스크립트 실행기가 아니다. 에이전트가 중간 결과를 읽고 판단하는 지점이 있다.

| 지점 | 에이전트 행동 |
|------|--------------|
| 파이프라인 실행 후 | `report.md`를 읽고 핵심 결과를 사용자에게 요약 |
| contradiction 발견 시 | 해당 claim과 반대 논문을 강조해서 보고 |
| confidence 낮은 추천 | 수동 확인이 필요한 항목을 별도 안내 |
| claim 추출 결과 검토 | `claims.jsonl`의 claim 수와 분포를 보고, 누락 의심 시 사용자에게 확인 |
| 부분 재실행 판단 | 사용자가 특정 claim 수정을 요청하면 `--from` 옵션으로 해당 단계부터 재실행 |

### 5.5 확장 경로

MVP에서는 Cursor 스킬만 제공한다. 코어 로직이 Python 패키지 구조(`src/`)로 분리되어 있으므로, 이후 다른 인터페이스를 추가할 때 코어 코드를 변경하지 않고 래퍼만 추가하면 된다.

| 단계 | 인터페이스 | 대상 |
|------|-----------|------|
| MVP | Cursor 스킬 | Cursor 에이전트 |
| 이후 | CLI 서브커맨드 강화 | 사람, 범용 에이전트 |
| 이후 | MCP 서버 | Claude Desktop, 기타 MCP 클라이언트 |

CLI는 이미 스킬이 호출하는 진입점이므로 스킬 없이도 사용 가능하다. MCP는 CLI 또는 패키지 API를 감싸는 얇은 레이어로 추가한다.

### 5.6 코드 구조

```
paperworkagent/
├── .cursor/
│   └── skills/                  # 에이전트용 스킬 인터페이스
├── docs/
│   ├── requirements.md
│   └── architecture.md
├── config/
│   └── project.yaml
├── .env                         # 비밀값 (git 제외)
├── .gitignore
│
├── src/paperworkagent/
│   ├── __init__.py
│   ├── cli.py                   # CLI 진입점 (run, ingest, search, fact-check)
│   ├── orchestrator.py          # 파이프라인 실행 순서, --from/--until 제어
│   ├── config.py                # pydantic-settings (.env + project.yaml)
│   ├── models.py                # Claim, Paper, Assessment pydantic 모델
│   │
│   ├── ingest/
│   │   ├── markdown_parser.py   # Markdown → 섹션/문단 AST
│   │   ├── results_loader.py    # csv/tsv/xlsx → 표준 구조
│   │   └── claim_extractor.py   # LLM으로 claim 추출/분류
│   │
│   ├── retrieve/
│   │   ├── query_builder.py     # LLM으로 검색 질의 생성
│   │   ├── providers/
│   │   │   ├── base.py          # BaseProvider ABC, SearchQuery, PaperResult
│   │   │   ├── openalex.py
│   │   │   ├── crossref.py
│   │   │   └── europepmc.py
│   │   ├── deduplicator.py      # DOI/PMID/PMCID 중복 제거
│   │   └── fulltext_fetcher.py  # OA 경로 full-text 확보
│   │
│   ├── assess/
│   │   └── fact_checker.py      # LLM으로 라벨/점수/rationale 생성
│   │
│   ├── write/
│   │   ├── report_writer.py     # report.md 생성
│   │   ├── markdown_patcher.py  # paper.with_refs.md 생성
│   │   └── citation_formatter.py
│   │
│   ├── llm/
│   │   └── client.py            # litellm 래퍼, 캐시, retry
│   │
│   └── infra/
│       ├── cache.py             # diskcache 기반 캐시
│       └── rate_limiter.py      # provider별 rate limit 제어
│
├── tests/
│   ├── conftest.py              # live 테스트 마커, LLM client fixture
│   ├── fixtures/                # 샘플 원고
│   ├── test_ingest/
│   ├── test_assess/
│   └── test_write/
│
├── runs/                        # 실행 결과 (git 제외)
├── .cache/                      # API/LLM 캐시 (git 제외)
├── pyproject.toml
└── README.md
```

## 6. 단계별 상세 설계

요구사항의 7단계 워크플로를 4개 모듈로 매핑한 상세 설계이다.

### 6.1 ingest 모듈

**Markdown 파싱:**
- markdown-it-py로 AST 생성
- 헤더 구조 기반 섹션 경계 식별
- 문단, 표, 리스트, figure caption 추출
- 원문 라인 번호 보존

**결과 파일 로드:**
- pandas로 csv/tsv/xlsx 통합 로드
- 컬럼명, 데이터 타입 자동 추론
- 수치 비교 표현 추출

**claim 추출 (LLM):**
- 섹션별로 LLM에 텍스트를 전달하여 claim 단위로 분해
- claim_type 분류 (background, method, result, interpretation, limitation)
- claim_text, claim_type, needs_reference를 LLM이 직접 판단
- 자기 논문의 절차 서술은 추출하지 않거나 needs_reference=false로 표시
- 프롬프트는 `ingest/claim_extractor.py`에 정의

**산출물:** `claims.jsonl`

### 6.2 retrieve 모듈

**검색 질의 생성 (LLM):**
- claim_text와 claim_type을 LLM에 전달하여 검색 키워드 생성
- 복잡한 discussion 문장도 데이터베이스 친화적 키워드로 변환
- 프롬프트는 `retrieve/query_builder.py`에 정의

**provider 호출 순서:**
1. OpenAlex 검색
2. Crossref 보강
3. 생의학 claim이면 Europe PMC 검색
4. 상위 후보의 reference + cited-by 확장
5. provider 간 중복 제거 (DOI/PMID/PMCID 기준)

**provider 공통 인터페이스:**

```python
class BaseProvider(ABC):
    @abstractmethod
    async def search(self, query: SearchQuery) -> list[PaperResult]: ...

    @abstractmethod
    async def get_references(self, paper_id: str) -> list[str]: ...

    @abstractmethod
    async def get_cited_by(self, paper_id: str) -> list[str]: ...
```

**full-text 확보 우선순위:**
1. Europe PMC full-text
2. PMC open access
3. Unpaywall 경유 OA URL
4. abstract만 사용 (fallback)

**산출물:** `papers.jsonl`

### 6.3 assess 모듈

**fact-check (LLM):**
- claim과 paper(제목+초록)를 LLM에 전달
- LLM이 직접 판정: label, relevance_score, confidence, rationale, evidence_spans
- claim당 키워드 overlap 상위 10개 paper만 LLM에 전달 (비용 제어를 위한 lexical pre-filter)
- 초록이 없는 paper는 LLM 호출 없이 unrelated로 분류
- 프롬프트는 `assess/fact_checker.py`에 정의

**산출물:** `assessments.jsonl`

### 6.4 write 모듈

**보고서 생성:**
- claim별 상위 논문 정렬
- LLM이 생성한 rationale을 추천 이유로 사용
- 근거 부족/반대 문헌 경고 포함

**Markdown 패치:**
- 원문 유지, 인용 후보 주석 삽입
- 문서 하단에 추천 참고문헌 목록 추가
- 별도 패치용 Markdown 생성

**산출물:** `report.md`, `paper.with_refs.md`, `paper.patch.md`

## 7. LLM 구조

### 7.1 설계 원칙

LLM은 시스템의 **필수 구성 요소**이다. claim 추출, 검색 질의 생성, fact-check 판정 모두 LLM이 직접 수행한다. `LLM_API_KEY`가 설정되어 있지 않으면 파이프라인 시작 시 에러가 발생한다.

```
orchestrator
  │
  ├─ settings.llm.require_api_key()  ← 시작 시 검증
  ├─ LLMClient(settings.llm, cache)  ← 1회 생성, 전 단계에서 공유
  │
  ├─ ingest:   extract_claims(manuscript, llm)     ← LLM이 claim 추출/분류
  ├─ retrieve:  build_query(claim, llm)             ← LLM이 검색 질의 생성
  ├─ assess:   assess_claim_paper(claim, paper, llm) ← LLM이 라벨/점수/rationale 생성
  └─ write:    rule-based (LLM 결과를 포맷팅)
```

### 7.2 설정 흐름

`.env`의 `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`가 필수이다.

```
.env (LLM_PROVIDER, LLM_MODEL, LLM_API_KEY)
  → Settings.model_post_init() → LLMSettings(provider, model, api_key)
  → LLMSettings.require_api_key()  ← 비어있으면 RuntimeError
  → LLMClient(settings.llm, cache) → litellm.acompletion()
```

### 7.3 단계별 LLM 역할

| 단계 | 모듈 함수 | LLM 입력 | LLM 출력 | 호출 빈도 |
|------|----------|---------|---------|-----------|
| ingest | `claim_extractor.extract_claims()` | 섹션 텍스트 | claim JSON 배열 (text, type, needs_reference) | 섹션 수 (3-5회) |
| retrieve | `query_builder.build_query()` | claim_text + section + claim_type | 검색 키워드 JSON | claim 수 (15-25회) |
| assess | `fact_checker.assess_claim_paper()` | claim + paper abstract | label, relevance, confidence, rationale, evidence_spans JSON | claim당 상위 10 papers |
| write | (LLM 미사용) | — | — | — |

### 7.4 비용 제어

- 모든 LLM 응답은 `(prompt_hash, model)` 키로 diskcache에 캐싱 (TTL 1년). 재실행 시 동일 프롬프트는 캐시에서 반환
- assess 단계에서는 전체 paper가 아닌 **claim당 키워드 overlap 상위 10개 paper만** LLM에 전달 (lexical pre-filter)
- claim 20개, paper 500개 기준 예상 LLM 호출: ingest 4회 + retrieve 20회 + assess 200회 = 약 224회

### 7.5 프롬프트 관리

각 모듈이 자체 프롬프트를 상수로 관리한다.

| 위치 | 프롬프트 | JSON 출력 형식 |
|------|---------|---------------|
| `ingest/claim_extractor.py` | `_SYSTEM` / `_USER` | `[{claim_text, claim_type, needs_reference}]` |
| `retrieve/query_builder.py` | `_SYSTEM` / `_USER` | `{keywords: [...]}` |
| `assess/fact_checker.py` | `_SYSTEM` / `_USER` | `{label, relevance_score, confidence, rationale, evidence_spans}` |

## 8. 동시성 및 성능 설계

### 7.1 문제

claim 20개 × provider 3개 = 최소 60회 API 호출. cited-by 확장까지 포함하면 수백 회. 순차 실행 시 실행 시간이 비현실적으로 길어진다.

### 7.2 동시성 모델

```python
async def retrieve_for_claims(claims: list[Claim]) -> list[Paper]:
    semaphores = {
        "openalex": asyncio.Semaphore(5),
        "crossref": asyncio.Semaphore(3),
        "europepmc": asyncio.Semaphore(3),
    }
    tasks = [retrieve_one_claim(claim, semaphores) for claim in claims]
    return await asyncio.gather(*tasks)
```

- provider별 semaphore로 동시 요청 수 제한
- claim 단위 병렬 실행, provider 호출은 semaphore 내에서 제어
- LLM 호출도 별도 semaphore로 동시성 제한

### 7.3 실행 시간 목표

| 단계 | 목표 시간 (claim 20개 기준) |
|------|----------------------------|
| ingest | < 10초 |
| retrieve | < 120초 (병렬) |
| assess | < 60초 (LLM 활성 시) |
| write | < 10초 |
| **전체** | **< 4분** |

### 7.4 캐시 전략

| 캐시 대상 | 키 | TTL |
|-----------|-----|-----|
| provider 검색 결과 | `(provider, query_hash)` | 7일 |
| paper 메타데이터 | `(provider, paper_id)` | 30일 |
| full-text | `(paper_id)` | 30일 |
| LLM 응답 | `(prompt_hash, model)` | 무기한 |

## 8. 데이터 흐름

### 8.1 처리 순서

```
                          LLMClient (optional)
                              │
paper.md + results/ ──▶ ingest ──[enhance_claims]──▶ claims.jsonl
                                                         │
                                                         ▼
                                                    retrieve ──▶ papers.jsonl
                                                         │
                                                         ▼
                                                     assess ──[enhance_assessment]──▶ assessments.jsonl
                                                         │
                                                         ▼
                                                      write ──▶ report.md
                                                               paper.with_refs.md
```

`[enhance_*]`는 LLM이 활성화된 경우에만 실행된다. 비활성 시 rule-based 결과가 그대로 사용된다.

### 8.2 재실행 전략

각 단계 산출물을 파일로 저장해 부분 재실행이 가능하다. `--from`과 `--until`을 조합해 범위를 지정할 수 있다.

```bash
# 전체 실행
paper-agent run --manuscript paper.md --out runs/run-001

# ingest만 단독 실행
paper-agent ingest --manuscript paper.md --out runs/run-001

# assess까지만 실행 (write 생략)
paper-agent run --manuscript paper.md --until assess --out runs/run-001

# retrieve부터 재실행 (claims.jsonl 재사용)
paper-agent run --manuscript paper.md --from retrieve --out runs/run-001

# assess만 단독 재실행 (claims + papers 재사용, write 생략)
paper-agent run --manuscript paper.md --from assess --until assess --out runs/run-001
```

## 9. Provider 전략

### 9.1 Provider Adapter 패턴

모든 provider는 `BaseProvider` 인터페이스를 구현한다.

```python
@dataclass
class SearchQuery:
    keywords: list[str]
    year_range: tuple[int, int] | None = None
    max_results: int = 20

@dataclass
class PaperResult:
    paper_id: str
    title: str
    authors: list[str]
    year: int
    abstract: str | None
    doi: str | None
    pmid: str | None
    source_provider: str
```

### 9.2 Fallback 정책

- OpenAlex 실패 → Crossref + Europe PMC 결과로 계속 진행
- full-text 실패 → abstract 기반 평가로 계속 진행
- 특정 claim에서 근거 부족 → unsupported flag를 남기고 종료하지 않는다
- LLM 호출 실패 → 해당 claim-paper 쌍을 unrelated로 분류하고 계속 진행

### 9.3 Rate Limit 제어

| Provider | 무료 한도 (근사치) | Semaphore | Backoff |
|----------|-------------------|-----------|---------|
| OpenAlex | 100,000 req/day (polite pool) | 5 | exp 1-8초 |
| Crossref | 50 req/초 (polite pool) | 3 | exp 1-8초 |
| Europe PMC | 제한 완화 | 3 | exp 1-4초 |
| Semantic Scholar | 100 req/5분 (key 없이) | 1 | exp 2-16초 |

## 10. 오류 처리

### 10.1 복구 가능한 오류

- 특정 provider timeout → 다른 provider 결과로 계속 진행
- full-text 미확보 → abstract 기반 평가로 계속 진행
- 결과 파일 일부 파싱 실패 → 경고 후 나머지 처리
- 개별 claim-paper LLM 평가 실패 → unrelated로 분류, 계속 진행
- LLM JSON 파싱 실패 → 해당 항목 스킵, 계속 진행

시스템은 부분 결과를 유지한 채 계속 진행한다.

### 10.2 복구 불가능한 오류

- `LLM_API_KEY` 미설정 (파이프라인 시작 시 즉시 에러)
- 입력 Markdown 파일 누락
- 출력 디렉터리 생성 실패
- claim 추출 결과가 완전히 비어 있는 경우

명시적 오류 메시지와 함께 실행을 중단한다.

## 11. 설정 파일

### 11.1 `.env` (비밀값)

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...

# 선택: provider별 API key
OPENALEX_EMAIL=user@example.com
SEMANTIC_SCHOLAR_API_KEY=...
```

### 11.2 `config/project.yaml` (런타임 설정)

```yaml
project:
  name: "my-paper"
  domain: "biomedical"

llm:
  temperature: 0.1
  timeout_seconds: 30
  max_retries: 3

retrieval:
  providers: ["openalex", "crossref", "europepmc"]
  max_papers_per_claim: 20
  expand_citations: true

cache:
  enabled: true
  directory: ".cache"
```

## 12. 품질 검증

### 12.1 검증 포인트

- claim 추출 품질 (수동 라벨 대비 precision/recall)
- 중복 논문 제거 정확도
- support/contradict 구분 품질
- Markdown 결과 반영 정확도
- LLM 사용 시와 미사용 시 결과 차이

### 12.2 평가 데이터

- 수동 라벨링한 생의학 원고 샘플
- known citation pair 샘플
- contradiction 사례 샘플

## 13. 다음 설계 문서

- claim schema 정의서 (pydantic 모델 상세)
- provider adapter 명세 (API 엔드포인트, 응답 매핑)
- scoring rubric (차원별 세부 기준)
- 실행 계획서 (구현 순서, 마일스톤)
