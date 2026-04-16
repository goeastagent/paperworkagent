# Claim Explorer 요구사항

## 1. 개요

### 1.1 목적
단일 claim과 그 context를 입력받아, 여러 라운드의 탐색적 검색을 수행하여 해당 claim에 가장 관련성 높은 논문 후보를 찾아내는 모듈을 구축한다.

### 1.2 문제 정의
현재 retrieve 모듈은 claim당 LLM이 생성한 키워드 1세트로 3개 provider에 1회 검색한 뒤 끝낸다. 이 방식의 한계는 다음과 같다.

- 검색 질의가 단일 각도여서 관련 논문을 놓칠 수 있다
- 검색 결과의 관련성 필터링 없이 전부 assess로 넘겨 비용이 과다하다
- citation graph (references, cited-by)를 활용하지 않아 핵심 논문을 놓친다
- 검색 결과가 부족할 때 질의를 수정하는 적응적 전략이 없다

연구자가 실제로 문헌을 탐색하는 방식 — 여러 각도로 검색하고, 찾은 논문의 참고문헌을 추적하고, 관련 없는 결과를 걸러내고, 필요하면 검색어를 바꾸는 — 을 모방해야 한다.

### 1.3 제품 형태
Claim Explorer는 **독립 실행 가능한 스킬**로 우선 구축한다.

- **CLI**: 단일 claim에 대해 커맨드라인에서 독립 실행
- **Cursor 스킬**: 에이전트가 호출하여 단일 claim에 대해 탐색 수행

파이프라인(orchestrator) 통합은 독립 스킬이 안정화된 후 별도로 진행한다.

### 1.4 스킬 정의
Claim Explorer는 Cursor 스킬로 제공되어 에이전트가 독립적으로 호출할 수 있다.

- 스킬 이름: `claim-explorer`
- 입력: claim 텍스트 + claim_context (abstract, 원문 문단(paragraph), claim_type)
- 출력: 관련 논문 목록 (관련성 근거 포함)

### 1.5 PoC 범위

PoC에서는 **Round 1(다중 각도 초기 검색) + Round 2(관련성 빠른 필터)**만 구현한다.

| 라운드 | 범위 | 설명 |
|--------|------|------|
| Round 1: 다중 각도 초기 검색 | **PoC** | LLM 질의 생성 → provider 검색 → 중복 제거 |
| Round 2: 관련성 빠른 필터 | **PoC** | LLM batch 판단 → high/medium/low/unrelated 분류 |
| Round 3: Citation Graph 확장 | Post-PoC | high 논문의 references/cited-by 추적 |
| Round 4: 적응적 재검색 | Post-PoC | 검색 전략 수정 후 재검색 |

Post-PoC 항목은 본 문서에 설계로 남겨두되, `[Post-PoC]`로 표시한다.

## 2. 입력

### 2.1 필수 입력

| 필드 | 타입 | 설명 |
|------|------|------|
| `claim_text` | string | 탐색 대상 주장 문장 |
| `claim_context` | object | claim의 맥락 정보 |

#### claim_context 구조

| 필드 | 타입 | 설명 |
|------|------|------|
| `abstract` | string | 원본 논문의 초록 |
| `paragraph` | string | claim이 등장한 원문 문단 |
| `claim_type` | enum | background, method, result, interpretation, limitation |

- `abstract`: LLM이 연구 분야, 대상, 방법론을 파악하여 검색 질의의 정확도를 높인다. 별도 `domain` 필드 없이도 맥락 추론이 가능하다.
- `paragraph`: claim이 속한 문단 전체를 제공한다. 단일 문장보다 문단이 더 풍부한 맥락("Unlike previous approaches...", "Building on X et al.,..." 등)과 인접 claim 간의 논리적 흐름을 담고 있어 검색 질의 생성의 정확도가 높아진다.
- `claim_type`: 탐색 전략 분기의 핵심 기준. 섹션명 대신 의미적 역할로 전략을 결정한다.

### 2.2 선택 입력

| 필드 | 타입 | 설명 |
|------|------|------|
| `seed_papers` | string[] | `[Post-PoC]` 이미 알려진 관련 논문 DOI/PMID 목록. Round 3 citation graph 확장의 시작점으로 사용 |
| `max_papers` | int | 최종 반환할 최대 논문 수 (기본: 10) |

LLM이 claim_text와 claim_context에서 핵심 용어, 방법, 결과 지표, 연구 분야를 직접 파악하므로 별도 entities/methods/outcomes/domain 필드는 두지 않는다.

### 2.3 입력 예시

```json
{
  "claim_text": "CatBoost employs ordered boosting and symmetric decision trees, offering robust handling of heterogeneous features and native categorical support",
  "claim_context": {
    "abstract": "This study developed a machine learning-based 30-day readmission prediction model using electronic health records from 12,000 heart failure patients. We compared five gradient boosting frameworks and evaluated their performance with AUROC, AUPRC, and calibration metrics.",
    "paragraph": "We evaluated five gradient boosting frameworks: XGBoost, LightGBM, CatBoost, TabNet, and a tuned random forest baseline. Among the algorithms tested, CatBoost employs ordered boosting and symmetric decision trees, offering robust handling of heterogeneous features and native categorical support. LightGBM uses histogram-based splitting for faster training, while XGBoost remains the most widely adopted in clinical prediction studies.",
    "claim_type": "method"
  },
  "max_papers": 10
}
```

## 3. 출력

### 3.1 출력 구조

| 필드 | 타입 | 설명 |
|------|------|------|
| `status` | enum | 탐색 전체 상태: `success`, `partial`, `failed` |
| `issues` | ExploreIssue[] | 탐색 중 발생한 문제 목록 (없으면 빈 배열) |
| `papers` | ExploredPaper[] | 탐색된 논문 목록 (관련성 순). failed 시 빈 배열 |
| `search_log` | SearchRound[] | 각 탐색 라운드의 기록 |
| `summary` | string | 탐색 결과 요약 (한국어) |

#### status 결정 로직

| status | 조건 |
|--------|------|
| `success` | 모든 라운드가 정상 완료됨 |
| `partial` | 일부 provider 실패, 일부 논문 관련성 판단 실패 등 결과는 있으나 불완전 |
| `failed` | Round 1 결과 0건, 또는 Round 2 완전 실패 등 유의미한 결과를 반환할 수 없음 |

### 3.2 ExploreIssue

탐색 중 발생한 개별 문제를 구조화하여 기록한다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `round` | int | 문제가 발생한 라운드 번호 |
| `type` | enum | `provider_failure`, `llm_failure`, `llm_parse_failure`, `timeout`, `no_results` |
| `message` | string | 사람이 읽을 수 있는 설명 |
| `detail` | string? | provider명, 에러 코드 등 추가 정보 |

### 3.3 ExploredPaper

| 필드 | 타입 | 설명 |
|------|------|------|
| `doi` | string? | DOI (doi, pmid, pmcid 중 하나 이상 필수) |
| `pmid` | string? | PMID |
| `pmcid` | string? | PMCID |
| `title` | string | 논문 제목 |
| `authors` | string[]? | 저자 (provider가 제공하지 않으면 빈 배열) |
| `year` | int? | 출판 연도 |
| `abstract` | string? | 초록 |
| `relevance` | enum | high, medium, low |
| `relevance_reason` | string | 왜 이 논문이 관련 있는지 (한국어) |
| `discovery_method` | string | 어떻게 찾았는지. PoC: initial_search만 사용. `[Post-PoC]` citation_backward, citation_forward, re_search 추가 |
| `discovered_via` | string? | `[Post-PoC]` citation 확장으로 발견된 경우, 출발점이 된 seed 논문의 DOI. PoC에서는 항상 null |
| `venue` | string? | 학술지명 |

`discovered_via`는 citation 경로의 출처를 추적하기 위한 필드다. `discovery_method`가 "어떤 방식으로"를 나타낸다면, `discovered_via`는 "어떤 논문으로부터"를 나타낸다. 이 조합으로 FR-15(각 논문의 발견 경로 기록)를 완전히 충족한다.

#### discovered_via 설계 근거

1. **가벼운 구현**: DOI 문자열 하나만 추가하면 되므로 복잡도 증가가 거의 없다.
2. **탐색 이력을 별도 저장하지 않는 이유**: explorer는 stateless 함수다(input → output). 탐색 이력을 별도로 쌓으면 운영 데이터와 도메인 데이터가 혼재되고, 실행 횟수에 비례해 무한 성장한다. 횡단 분석이 필요해지면 JSON 출력 파일을 사후 분석하거나, 그때 별도 저장소를 도입한다.

### 3.4 SearchRound

| 필드 | 타입 | 설명 |
|------|------|------|
| `round` | int | 라운드 번호 |
| `type` | string | PoC: initial_search, relevance_filter. `[Post-PoC]` citation_expansion, re_search 추가 |
| `queries` | string[] | 사용된 검색 질의 |
| `papers_found` | int | 찾은 논문 수 |
| `papers_kept` | int | 필터 후 남은 논문 수 |
| `duration_seconds` | float | 소요 시간 |

### 3.5 출력 예시

```json
{
  "status": "success",
  "issues": [],
  "papers": [
    {
      "doi": "10.48550/arXiv.1706.09516",
      "pmid": null,
      "pmcid": null,
      "title": "CatBoost: unbiased boosting with categorical features",
      "authors": ["Prokhorenkova L", "Gusev G", "Vorobev A"],
      "year": 2018,
      "abstract": "We present CatBoost, a new gradient boosting algorithm that handles categorical features...",
      "relevance": "high",
      "relevance_reason": "CatBoost 알고리즘의 원저 논문으로, ordered boosting과 symmetric tree 구조를 직접 설명함",
      "discovery_method": "initial_search",
      "discovered_via": null,
      "venue": "NeurIPS 2018"
    },
    {
      "doi": "10.1145/2939672.2939785",
      "pmid": null,
      "pmcid": null,
      "title": "XGBoost: A Scalable Tree Boosting System",
      "authors": ["Chen T", "Guestrin C"],
      "year": 2016,
      "abstract": "Tree boosting is a highly effective and widely used machine learning method...",
      "relevance": "medium",
      "relevance_reason": "CatBoost가 비교 대상으로 삼는 gradient boosting 프레임워크의 원저. ordered boosting과의 차이를 이해하는 데 간접적으로 관련됨",
      "discovery_method": "initial_search",
      "discovered_via": null,
      "venue": "KDD 2016"
    }
  ],
  "search_log": [
    {"round": 1, "type": "initial_search", "queries": ["CatBoost ordered boosting", "CatBoost categorical features gradient boosting"], "papers_found": 35, "papers_kept": 35, "duration_seconds": 3.2},
    {"round": 2, "type": "relevance_filter", "queries": [], "papers_found": 35, "papers_kept": 8, "duration_seconds": 2.1}
  ],
  "summary": "CatBoost 원저 논문 및 gradient boosting 비교 연구 3편을 포함하여 총 8편의 관련 문헌을 확인함."
}
```

## 4. 탐색 전략

### 4.1 Round 1: 다중 각도 초기 검색

claim을 여러 관점에서 검색한다. LLM이 claim_type에 따라 2-3개의 서로 다른 검색 질의를 생성한다.

| claim_type | 질의 각도 |
|------------|----------|
| background | 개념/용어 중심, 리뷰 논문 중심 |
| method | 방법론 원저, 방법론 비교/벤치마크 |
| result | 동일 지표/outcome 사용 연구, 동일 대상 집단 |
| interpretation | 유사 해석을 제시한 연구, 반대 해석 |
| limitation | 동일 한계를 다룬 연구, 해결 방안 제시 연구 |

**Provider:**

PoC에서는 다음 3개 provider를 모두 사용한다. provider 목록은 설정으로 관리하여 추후 추가/제거가 가능하다.

| Provider | 설명 |
|----------|------|
| OpenAlex | 오픈 액세스 학술 메타데이터. 넓은 커버리지 |
| Europe PMC | 생의학 문헌 중심. PMID/PMCID 지원 |
| Crossref | DOI 기반 메타데이터. 학술지 커버리지 우수 |

**기대 동작:**
- claim당 2-3개 질의 생성
- 각 질의를 3개 provider에 동시 전송
- query당 provider당 최대 20개 결과 (per query per provider)
- 전체 중복 제거 후 ~30-60개 후보

### 4.2 Round 2: 관련성 빠른 필터

Round 1 결과에 대해 LLM이 초록만 보고 관련성을 빠르게 판단한다.

**기대 동작:**
- 각 논문의 초록(전체)과 claim을 LLM에 전달
- high / medium / low / unrelated 분류
- unrelated는 즉시 제거
- batch 처리: 한 프롬프트에 10개 논문을 묶어 판단 (LLM 호출 횟수 절감)
- LLM이 JSON 형식으로 응답하지 못한 논문은 모아서 재시도 (최대 2회)

### 4.3 최종 정리

Round 2 결과를 관련성 등급 순(high → medium → low)으로 정렬하고, `max_papers` 개수만 반환한다. 동일 등급 내에서는 별도 정렬을 하지 않는다.

### 4.4 `[Post-PoC]` Round 3: Citation Graph 확장

Round 2에서 high로 평가된 논문(최대 3-5개)의 참고문헌과 피인용 논문을 추적한다.

**기대 동작:**
- high 논문의 `get_references()` 호출 → 참고문헌 DOI 목록
- high 논문의 `get_cited_by()` 호출 → 피인용 논문 DOI 목록
- 수집된 DOI로 메타데이터 조회
- Round 2와 동일한 관련성 필터 적용
- 이미 발견된 논문은 제외

### 4.5 `[Post-PoC]` Round 4: 적응적 재검색 (조건부)

Round 1-3에서 high 관련성 논문이 2개 미만이면 LLM이 검색 전략을 수정하고 재검색한다.

**트리거 조건:** `count(relevance == "high") < 2`

**기대 동작:**
- LLM에게 "이 claim에 대해 이런 질의로 검색했는데 관련 논문이 부족합니다. 다른 검색 전략을 제안해주세요." 요청
- 새로운 질의로 Round 1과 동일한 검색 수행
- 이미 발견된 논문은 제외
- 최대 1회만 수행 (무한 루프 방지)

## 5. 기능 요구사항

각 요구사항에서 LLM이 사용되는 항목은 `[LLM]`으로 표시한다.

### 5.1 검색 (Round 1)

- FR-1: `[LLM]` claim_text, claim_context를 분석하여 claim_type에 따라 2-3개의 서로 다른 검색 질의를 생성해야 한다
- FR-2: 각 질의를 설정된 provider(OpenAlex, Europe PMC, Crossref)에 동시 전송해야 한다. provider 목록은 설정으로 관리하여 추후 확장 가능해야 한다
- FR-3: provider 간 중복 논문을 DOI → PMID → PMCID 순으로 비교하여 제거해야 한다. 세 식별자가 모두 없는 경우 title 정규화 비교로 중복을 판단한다
- FR-4: `[Post-PoC]` seed_papers가 주어지면 citation graph 확장의 시작점으로 사용해야 한다

### 5.2 관련성 필터 (Round 2)

- FR-5: `[LLM]` 각 논문의 초록(전체)과 claim을 비교하여 high/medium/low/unrelated 관련성을 분류해야 한다
- FR-6: `[LLM]` batch 프롬프트로 10개 논문을 한 번에 판단하여 LLM 호출을 절감해야 한다
- FR-7: `[LLM]` 각 논문에 대해 관련성 판단 근거를 한국어로 생성해야 한다
- FR-8: LLM이 유효한 JSON을 반환하지 못한 논문은 실패 항목만 모아서 재시도해야 한다 (최대 2회)

### 5.3 `[Post-PoC]` Citation Graph (Round 3)

- FR-9: high 관련성 논문의 참고문헌(backward)을 API로 추적해야 한다
- FR-10: high 관련성 논문의 피인용(forward)을 API로 추적해야 한다
- FR-11: `[LLM]` citation 추적으로 발견된 논문에도 FR-5와 동일한 관련성 필터를 적용해야 한다

### 5.4 `[Post-PoC]` 적응적 재검색 (Round 4)

- FR-12: `[LLM]` high 관련성 논문이 부족할 때 이전 검색 결과를 분석하여 새로운 검색 전략을 생성해야 한다
- FR-13: 재검색은 최대 1회로 제한해야 한다
- FR-14: 재검색에서는 이미 발견된 논문을 제외해야 한다

### 5.5 추적 가능성

- FR-15: 각 논문이 어떤 라운드, 어떤 검색 질의에서 발견되었는지 기록해야 한다
- FR-16: 각 탐색 라운드의 질의, 결과 수, 소요 시간을 기록해야 한다
- FR-17: `[LLM]` 전체 탐색 과정의 요약을 한국어로 생성해야 한다

## 6. 비기능 요구사항

### 6.1 성능

- NFR-1: claim 1개당 전체 탐색 완료 시간이 30초 이내여야 한다 (캐시 미스 기준)
- NFR-2: 캐시 히트 시 5초 이내여야 한다
- NFR-3: provider 호출은 semaphore로 동시성을 제한해야 한다 (기본 동시 호출 수: 3)

### 6.2 비용

- NFR-4: 관련성 필터는 batch 프롬프트를 사용해 LLM 호출 횟수를 최소화해야 한다
- NFR-5: claim 1개당 LLM 호출 횟수는 최대 100회 이내여야 한다
- NFR-6: 모든 LLM 응답과 provider 검색 결과는 파일 기반 로그로 캐싱되어야 한다 (→ 섹션 9 참조)

### 6.3 견고성

- NFR-7: 특정 provider 실패 시 나머지 provider 결과로 계속 진행해야 한다. 실패한 provider는 `ExploreIssue`에 기록하고 `status`를 `partial`로 설정한다
- NFR-8: LLM 호출이 완전히 실패하면 해당 라운드를 건너뛰어야 한다. Round 2 완전 실패 시 `status`를 `failed`, `papers`를 빈 배열로 설정하고 사유를 `ExploreIssue`에 기록한다
- NFR-9: `[Post-PoC]` citation graph 조회 실패 시 Round 3를 건너뛰고 진행해야 한다. 실패 사유는 `ExploreIssue`에 기록한다
- NFR-10: 모든 비정상 상황은 `ExploreIssue`로 구조화하여 출력에 포함해야 한다. caller는 `status` 필드로 결과 신뢰도를 즉시 판단할 수 있어야 한다

## 7. claim_type별 탐색 전략 상세

### 7.1 background

**목적:** claim에서 언급하는 개념이나 사실의 근거가 되는 원저 또는 리뷰 논문을 찾는다.

**질의 전략:**
1. 핵심 개념 + "review" 또는 "overview"
2. 핵심 엔티티의 정식 명칭으로 직접 검색

**예시:**
- claim: "BRCA1 is a well-known tumor suppressor gene involved in DNA repair"
- 질의 1: "BRCA1 tumor suppressor DNA repair review"
- 질의 2: "BRCA1 function DNA damage response"

### 7.2 method

**목적:** claim에서 사용하는 방법론의 원저, 검증 연구, 또는 유사 적용 사례를 찾는다.

**질의 전략:**
1. 방법론 이름 + 원저/최초 제안
2. 방법론 + 적용 도메인 (biomedical 등)
3. 방법론 + 비교/벤치마크

**예시:**
- claim: "CatBoost employs ordered boosting and symmetric decision trees"
- 질의 1: "CatBoost ordered boosting algorithm"
- 질의 2: "CatBoost clinical prediction model"
- 질의 3: "gradient boosting comparison XGBoost LightGBM CatBoost"

### 7.3 result

**목적:** 유사한 실험 조건에서 비슷하거나 다른 결과를 보고한 연구를 찾는다.

**질의 전략:**
1. 동일 대상 + 동일 outcome
2. 동일 방법 + 동일 질환/조건
3. 동일 지표 + 유사 연구 설계

### 7.4 interpretation

**목적:** 유사한 해석을 제시한 연구, 또는 다른 해석을 제시한 연구를 찾는다.

**질의 전략:**
1. 핵심 해석 키워드 중심 검색
2. 반대 방향의 해석도 의도적으로 검색 ("however", "in contrast")
3. 관련 메타분석 또는 종합 연구

### 7.5 limitation

**목적:** 동일한 한계를 보고한 연구, 또는 해당 한계를 극복한 연구를 찾는다.

**질의 전략:**
1. 한계 유형 + 연구 설계
2. 해결 방안이 될 수 있는 방법론

## 8. 관련성 필터 프롬프트 전략

### 8.1 Batch 판단

한 프롬프트에 claim 1개 + 논문 10개를 묶어 관련성을 판단한다.

**입력 형식:**
```
Claim: "CatBoost employs ordered boosting..."

Papers:
1. "Title" (Year) [doi: 10.xxx/yyy] - Abstract: <전체 초록>
2. "Title" (Year) [pmid: 12345678] - Abstract: <전체 초록>
3. "Title" (Year) - Abstract: <전체 초록>
...

For each paper, return: {id, relevance: high|medium|low|unrelated, reason: 1 sentence in Korean}
```

논문 식별은 batch 내 순번(id: 1, 2, 3...)으로 한다. DOI/PMID/PMCID는 가용한 식별자를 참조 정보로 표기하되, LLM 응답에서의 매칭은 순번 기반으로 처리한다.

**기대 출력:**
```json
[
  {"id": 1, "relevance": "high", "reason": "CatBoost 원저 논문"},
  {"id": 2, "relevance": "unrelated", "reason": "CatBoost와 무관한 NLP 연구"}
]
```

### 8.2 실패 재시도

LLM이 유효한 JSON을 반환하지 못한 논문(파싱 실패, 누락된 id 등)은 실패 항목만 모아서 별도 batch로 재시도한다. 최대 2회 재시도하며, 그래도 실패하면 해당 논문은 `unrelated`로 처리한다.

### 8.3 판단 기준

| 관련성 | 기준 |
|--------|------|
| high | claim을 직접 지지하거나 반박하는 핵심 근거 논문 |
| medium | 관련은 있으나 간접적, 부분적으로만 관련 |
| low | 같은 분야이나 claim과 직접 연결되지 않음 |
| unrelated | claim과 무관 |

## 9. 캐싱

### 9.1 캐시 저장소

모든 LLM 응답과 provider 검색 결과를 **파일 기반 로그**로 캐싱한다.

| 대상 | 캐시 키 | 저장 형식 |
|------|---------|-----------|
| provider 검색 결과 | `(provider, query_string)` | JSON 파일 |
| LLM 질의 생성 응답 | `(claim_text, claim_type)` | JSON 파일 |
| LLM 관련성 판단 응답 | `(claim_text, sorted_paper_identifiers)` | JSON 파일 |

각 논문의 identifier는 DOI → PMID → PMCID → normalized_title 순으로 가용한 첫 번째 식별자를 사용한다.

캐시 파일은 프로젝트 내 지정 디렉터리(예: `.cache/claim-explorer/`)에 저장한다. TTL은 두지 않으며, 수동 삭제로 캐시를 초기화한다.

### 9.2 캐시 히트 동작

캐시 히트 시 provider API 호출이나 LLM 호출을 건너뛰고 캐시된 결과를 즉시 사용한다. search_log에는 캐시 히트 여부를 기록하지 않되, 소요 시간(duration_seconds)이 자연스럽게 짧아지므로 간접적으로 확인 가능하다.

## 10. LLM 설정

### 10.1 모델 설정

각 LLM 태스크는 독립적으로 모델을 지정할 수 있다. 기본값은 모두 OpenAI GPT-5.2를 사용한다.

| 태스크 | 설정 키 | 기본 모델 |
|--------|---------|-----------|
| 질의 생성 (Round 1) | `llm.query_generation.model` | `gpt-5.2` |
| 관련성 판단 (Round 2) | `llm.relevance_filter.model` | `gpt-5.2` |
| 요약 생성 | `llm.summary.model` | `gpt-5.2` |

추후 비용 최적화를 위해 태스크별로 다른 모델(예: 관련성 판단에 저렴한 모델)을 지정할 수 있다.

### 10.2 재시도 정책

| 항목 | 정책 |
|------|------|
| LLM JSON 파싱 실패 | 실패한 항목만 모아서 재시도, 최대 2회 |
| LLM API 호출 실패 (네트워크 등) | 해당 라운드 건너뛰고 이전 라운드 결과 사용 |
| provider API 호출 실패 | 해당 provider 건너뛰고 나머지 provider 결과로 진행 |

## 11. 중복 제거 전략

### 11.1 식별자 기반 비교

provider 간 중복 논문을 다음 우선순위로 비교하여 제거한다:

```
1. DOI가 있으면 → DOI로 비교
2. PMID가 있으면 → PMID로 비교
3. PMCID가 있으면 → PMCID로 비교
4. 모두 없으면 → title 정규화 비교
```

### 11.2 Title 정규화 비교

식별자가 모두 없는 논문은 title을 정규화하여 비교한다:
- 소문자 변환
- 구두점 제거
- 연속 공백 단일화
- 정규화된 title이 동일하면 같은 논문으로 간주

### 11.3 병합 규칙

동일 논문이 여러 provider에서 발견된 경우, 기존 메타데이터가 null인 필드만 새 값으로 채운다(coalesce). `source_provider`는 최초 발견 provider를 유지한다.

## 12. 데이터 구조

Python 데이터 모델은 별도 문서를 참조한다.

→ **[claim-explorer-data-structures.md](./claim-explorer-data-structures.md)**

`[Post-PoC]` Neo4j 도입 시:
- **저장소**: Neo4j — Paper 노드 저장 및 citation 경로 탐색(1-hop, 2-hop)
- **노드**: Paper (doi/pmid/pmcid unique constraint)
- **관계**: `(:Paper)-[:CITES]->(:Paper)` — Round 3에서 생성
- **그래프 재활용**: 여러 claim 탐색 시 이전에 구축된 노드/관계를 API 호출 없이 재활용

## 13. 실행 인터페이스

### 13.1 CLI

```bash
python -m paperworkagent.cli explore \
  --claim "CatBoost employs ordered boosting..." \
  --abstract "This study developed a machine learning-based..." \
  --paragraph "We evaluated five gradient boosting frameworks..." \
  --type method \
  --max-papers 10 \
  --out exploration.json
```

### 13.2 Cursor 스킬

```
.cursor/skills/claim-explorer/SKILL.md
```

## 14. 수용 기준

### PoC 수용 기준

- claim_type에 따라 2-3개의 서로 다른 검색 질의가 생성된다 (Round 1)
- 3개 provider(OpenAlex, Europe PMC, Crossref)에 동시 검색하고 DOI/PMID/PMCID/title 기준으로 중복이 제거된다
- 검색 결과에 대해 LLM이 관련성을 batch로 판단하고, 각 논문에 관련성 근거가 제공된다 (Round 2)
- LLM JSON 파싱 실패 시 실패 항목만 모아서 최대 2회 재시도한다
- 전체 탐색 과정(질의, 결과 수, 소요 시간)이 search_log에 기록된다
- 탐색 상태(status: success/partial/failed)와 발생 이슈(issues)가 출력에 포함된다
- provider 실패, LLM 실패 등 비정상 상황에서도 가용한 결과를 반환하고 이슈를 구조화하여 기록한다
- LLM 응답과 provider 검색 결과가 파일 기반 로그로 캐싱된다
- claim 1개당 30초 이내에 완료된다
- CLI와 Cursor 스킬로 단독 실행 가능하다

### Post-PoC 수용 기준

- Neo4j에 Paper 노드와 citation graph(CITES 관계)가 구축되고, references/cited-by를 추적하여 추가 논문을 발견할 수 있다
- 여러 claim 탐색 시 이전에 구축된 그래프를 재활용할 수 있다
- 검색 결과가 부족할 때 적응적 재검색이 수행된다
