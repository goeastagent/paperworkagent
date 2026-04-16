# Claim Extractor 요구사항

## 1. 개요

### 1.1 목적

논문 초안(Markdown)을 입력받아, reference가 필요하지만 아직 달려있지 않은 문장을 식별하고, 각 문장을 claim-explorer가 소비할 수 있는 구조화된 claim으로 변환하는 모듈을 구축한다.

### 1.2 문제 정의

claim-explorer는 단일 claim(`claim_text` + `claim_context`)을 입력받아 관련 논문을 찾는다. 그러나 논문 전체에서 어떤 문장이 reference를 필요로 하는지를 사람이 직접 판단하고 하나씩 입력하는 것은 비효율적이다.

연구자가 논문을 쓸 때 reference가 필요한 문장의 유형은 다음과 같다:

- 선행 연구의 사실이나 발견을 서술하는 문장 (background)
- 특정 방법론이나 도구를 채택했다고 언급하는 문장 (method)
- 다른 연구와 비교하거나 대조하는 문장 (result)
- 결과에 대한 해석 근거를 제시하는 문장 (interpretation)
- 연구의 한계를 다른 연구와 연결짓는 문장 (limitation)

이러한 문장을 자동으로 식별하고 구조화하면, claim-explorer에 batch로 전달하여 논문 전체의 reference를 한 번에 탐색할 수 있다.

### 1.3 설계 철학

**논문 전문을 LLM에 한 번에 전달하여 claim을 추출한다.**

규칙 기반 파싱(문장 분리, citation 정규식, batch 분할 등)을 코드로 구현하지 않는다. LLM이 자연어 이해 능력으로 citation 유무 판단, 문장 경계 인식, reference 필요 여부 판단을 일괄 수행한다.

이 접근의 근거:

| 관점 | 규칙 기반 파싱 + 문단별 LLM | 논문 전체 LLM 일괄 처리 |
|------|--------------------------|----------------------|
| 코드 복잡도 | 높음 (파서, 정규식, batch 로직) | **낮음** (파일 읽기 + LLM 1회) |
| 정확도 | 정규식 한계 (비표준 citation 누락) | **높음** (자연어 이해) |
| 문맥 활용 | 문단 내로 제한 | **논문 전체** |
| 비용 | system prompt 반복으로 오히려 비쌈 | **1회 호출** |
| 엣지 케이스 | 약어, 괄호 내 마침표 등 처리 필요 | **LLM이 자연 처리** |

일반 학술 논문(5,000-8,000 단어, ~7,000-11,000 토큰)은 GPT-5.2의 context window(128K+)에 넉넉히 들어간다.

### 1.4 제품 형태

Claim Extractor는 **독립 실행 가능한 모듈**로 구축한다.

- **CLI**: 논문 Markdown 파일을 입력으로 받아 커맨드라인에서 독립 실행
- **Cursor 스킬**: 에이전트가 호출하여 논문 파일에서 claim 추출 수행
- **Python API**: claim-explorer와 프로그래밍 방식으로 연결 가능

### 1.5 다운스트림 연동

Claim Extractor의 출력은 claim-explorer의 `ExploreInput`과 1:1 대응한다:

```
Claim Extractor 출력 (ExtractedClaim)      claim-explorer 입력 (ExploreInput)
─────────────────────────────────────      ──────────────────────────────────
claim_text                            →    claim_text
claim_context.abstract                →    claim_context.abstract
claim_context.paragraph               →    claim_context.paragraph
claim_context.claim_type              →    claim_context.claim_type
(기본값 10)                            →    max_papers
```

### 1.6 PoC 범위

| 항목 | 범위 | 설명 |
|------|------|------|
| Markdown 입력 | **PoC** | Markdown 형식의 논문 초안 |
| LLM 일괄 추출 | **PoC** | 논문 전문을 LLM에 전달하여 claim 추출 |
| 다중 포맷 지원 | Post-PoC | plain text, PDF, LaTeX 등 |
| 다국어 지원 | Post-PoC | 영어 외 언어 |

Post-PoC 항목은 `[Post-PoC]`로 표시한다.

## 2. 입력

### 2.1 필수 입력

| 필드 | 타입 | 설명 |
|------|------|------|
| `paper_path` | string (파일 경로) | Markdown 형식의 논문 초안 파일 경로 |

### 2.2 고정 상수

| 항목 | 값 | 설명 |
|------|-----|------|
| `MAX_CLAIMS` | 50 | 최대 추출할 claim 수. confidence 상위 50개만 반환 |

### 2.3 입력 예시

```bash
python -m paperworkagent.cli extract \
  --paper draft.md \
  --out claims.json
```

## 3. 처리 파이프라인

### 3.1 전체 흐름

```
Step 1: 파일 읽기
  ┌──────────────────────────────────────────────┐
  │ Markdown 파일을 텍스트로 읽기                    │
  │ 빈 파일/인코딩 오류 검증                         │
  └──────────────────────────────────────────────┘
          │
          ▼
Step 2: [LLM] 논문 전문 → Claim 추출
  ┌──────────────────────────────────────────────┐
  │ 논문 전문 + system prompt를 LLM에 전달          │
  │ LLM이 일괄적으로:                               │
  │   - Abstract/Acknowledgments/References 건너뜀 │
  │   - 이미 citation이 있는 문장 건너뜀             │
  │   - reference가 필요한 문장 식별                 │
  │   - claim_type 분류                             │
  │   - claim_text 정제                             │
  │   - 소속 문단(paragraph), abstract 추출          │
  │   - confidence, reason 산출                     │
  └──────────────────────────────────────────────┘
          │
          ▼
Step 3: JSON 파싱 및 출력
  ┌──────────────────────────────────────────────┐
  │ LLM 응답을 JSON 파싱                            │
  │ 각 claim 유효성 검증 (claim_text + claim_type)  │
  │ LLM flat 응답 → ExtractedClaim nested 변환      │
  │ confidence 순 정렬                              │
  │ MAX_CLAIMS(50) 개수 제한                        │
  │ ExtractOutput JSON 출력                        │
  └──────────────────────────────────────────────┘
```

### 3.2 Step 1: 파일 읽기

Markdown 파일을 UTF-8 텍스트로 읽는다.

| 검증 | 처리 |
|------|------|
| 파일이 없음 | 즉시 `failed` 반환 |
| 빈 파일 | 즉시 `failed` 반환 |
| 인코딩 오류 | 즉시 `failed` 반환 |

### 3.3 Step 2: LLM 논문 전문 → Claim 추출

논문 전문을 LLM에 한 번에 전달하여, reference가 필요한 claim을 일괄 추출한다. Abstract 추출을 포함한 모든 분석을 LLM이 수행한다.

#### 3.3.1 LLM에 전달하는 정보

| 정보 | 출처 |
|------|------|
| 논문 전문 | Step 1에서 읽은 Markdown 텍스트 |

#### 3.3.2 LLM이 수행하는 판단

LLM은 논문 전체를 읽고 다음을 일괄 수행한다:

1. **논문 제목 추출** — Markdown `#` 헤딩에서 추출
2. **Abstract 추출** — Abstract 섹션 텍스트를 추출하여 `abstract` 필드로 반환
3. **제외 섹션 건너뛰기** — Abstract, Acknowledgments, References 섹션의 문장은 claim 추출 대상에서 제외
4. **이미 citation이 있는 문장 건너뛰기** — `[1]`, `(Smith et al., 2020)`, `Smith et al. (2020)` 등 citation이 달린 문장은 제외
5. **Reference 필요 여부 판단** — citation이 없는 문장 중 reference가 필요한 것 식별
6. **claim_type 분류** — background, method, result, interpretation, limitation
7. **claim_text 정제** — 필요시 원문을 정제하여 검색에 적합한 claim 텍스트 생성
8. **소속 문단 추출** — claim이 등장한 원문 문단을 `paragraph`로 반환
9. **confidence 산출** — reference 필요성에 대한 확신도 (0.0-1.0)
10. **reason 생성** — 왜 reference가 필요한지 한국어로 설명

#### 3.3.3 Reference가 필요한 문장의 판단 기준

| 필요함 | 불필요함 |
|--------|----------|
| 선행 연구의 발견이나 사실을 서술 | 자명한 사실 (예: "Water boils at 100°C") |
| 특정 방법론/도구/데이터셋의 채택을 언급 | 저자 자신의 연구에서 새로 수행한 분석/결과 |
| 다른 연구와 비교/대조 | 논문 내 다른 섹션의 결과를 참조 |
| 통계적 수치나 역학적 사실을 인용 | 연구 설계에 대한 서술 (특정 방법론 언급 없이) |
| 기존 이론이나 프레임워크를 언급 | 논리적 추론/귀결 ("Therefore...", "Thus...") |

#### 3.3.4 claim_type 분류 기준

claim-explorer의 `ClaimType`과 동일한 분류 체계를 사용한다:

| claim_type | 판단 기준 |
|------------|----------|
| `background` | 연구 배경 지식, 기존 사실, 정의, 역학적 수치를 서술 |
| `method` | 특정 알고리즘, 도구, 프레임워크, 데이터셋의 사용을 언급 |
| `result` | 다른 연구의 실험 결과를 인용하거나 비교 |
| `interpretation` | 결과 해석 시 기존 연구의 해석을 참조하거나 대조 |
| `limitation` | 연구 한계를 다른 연구의 한계와 연결하거나, 기존 해결 방안을 언급 |

#### 3.3.5 Claim 텍스트 정제

LLM은 원문 문장을 그대로 `claim_text`로 사용하되, 다음 경우에만 정제한다:

| 상황 | 정제 방식 |
|------|----------|
| 문장이 복수의 독립적 주장을 포함 | 주장별로 분리하여 각각 독립 claim으로 출력 |
| 문장 앞부분이 불필요한 접속사/전환어로 시작 | 접속사 제거 ("However, " → 핵심 주장만) |
| 문장이 claim 부분과 저자 논의를 혼합 | claim에 해당하는 부분만 추출 |

원문 문장은 `original_sentence`에 항상 보존한다.

#### 3.3.6 소속 문단 추출

LLM은 각 claim이 등장한 **원문 문단**(빈 줄로 구분된 텍스트 블록)을 `paragraph` 필드로 반환한다. 이 문단은 claim-explorer의 `claim_context.paragraph`로 직접 사용된다.

문단은 claim의 앞뒤 문맥을 포함하므로, claim-explorer가 검색 질의를 생성할 때 풍부한 맥락을 활용할 수 있다.

### 3.4 Step 3: JSON 파싱 및 출력

#### 3.4.1 LLM 응답 → ExtractedClaim 변환

LLM은 flat JSON을 반환하고, 코드가 nested `ExtractedClaim` 모델로 변환한다:

```
LLM 응답 (flat)                    ExtractedClaim (nested)
─────────────                      ─────────────────────
claim_text                    →    claim_text
paragraph                     →    claim_context.paragraph
claim_type                    →    claim_context.claim_type
abstract (논문 전체 공유)       →    claim_context.abstract
original_sentence             →    original_sentence
section_title                 →    section_title
confidence                    →    confidence
reason                        →    reason
```

`abstract`는 LLM 응답의 최상위 `abstract` 필드에서 가져와 모든 claim의 `claim_context.abstract`에 공유 설정한다.

#### 3.4.2 최상위 필드 검증

LLM 응답의 최상위 필드 누락 시 처리:

| 최상위 필드 | 누락 시 처리 |
|------------|------------|
| `claims` | 빈 배열로 처리. `success` 반환 (논문에 reference가 필요한 문장이 없는 것으로 간주) |
| `abstract` | 빈 문자열로 대체하고 진행 |
| `paper_title` | null로 처리 |

#### 3.4.3 claim 유효성 검증

각 claim에 대해 다음 **필수 필드**가 있어야 유효한 claim으로 인정한다:

| 필드 | 필수 | 누락 시 처리 |
|------|------|-------------|
| `claim_text` | **필수** | 해당 claim 무효 → 건너뜀 |
| `claim_type` | **필수** | 해당 claim 무효 → 건너뜀 |
| `original_sentence` | 선택 | `claim_text`를 복사하여 대체 |
| `section_title` | 선택 | `"Unknown"`으로 대체 |
| `paragraph` | 선택 | `original_sentence`를 복사하여 대체 |
| `confidence` | 선택 | `0.5`로 대체 |
| `reason` | 선택 | 빈 문자열로 대체 |

`claim_type` 파싱 규칙:
- 대소문자 무관 매칭 (예: `"Background"` → `background`)
- `ClaimType` enum에 매칭되지 않는 값이면 `background`를 기본값으로 사용

무효 claim이 존재하면 `partial` 상태로 설정하고, 무효 claim 수를 `ExtractIssue`에 기록한다.

#### 3.4.4 정렬 및 제한

1. `confidence` 내림차순 정렬
2. `MAX_CLAIMS`(50) 개수 제한 적용
3. `ExtractOutput` JSON 생성

## 4. 출력

### 4.1 출력 구조

| 필드 | 타입 | 설명 |
|------|------|------|
| `status` | enum | 추출 전체 상태: `success`, `partial`, `failed` |
| `issues` | ExtractIssue[] | 추출 중 발생한 문제 목록 (없으면 빈 배열) |
| `paper_title` | string? | 논문 제목 (LLM이 추출, 없으면 null) |
| `abstract` | string | LLM이 논문에서 추출한 초록 텍스트 |
| `claims` | ExtractedClaim[] | 추출된 claim 목록 (confidence 순) |
| `duration_seconds` | float | 전체 처리 소요 시간 |

#### status 결정 로직

| status | 조건 |
|--------|------|
| `success` | LLM 호출 성공 + JSON 파싱 성공 + 무효 claim 없음 (claim 0개도 success) |
| `partial` | LLM 응답에 무효 claim 존재 등 결과는 있으나 불완전 |
| `failed` | 파일 읽기 실패, LLM 완전 실패 등 유의미한 결과를 반환할 수 없음 |

### 4.2 ExtractedClaim

| 필드 | 타입 | 설명 |
|------|------|------|
| `claim_text` | string | claim-explorer에 전달할 claim 텍스트 |
| `claim_context` | ClaimContext | claim-explorer와 동일 구조 (abstract, paragraph, claim_type) |
| `original_sentence` | string | 원문 문장 (정제 전) |
| `section_title` | string | claim이 위치한 섹션 제목 |
| `confidence` | float | reference 필요성에 대한 확신도 (0.0-1.0) |
| `reason` | string | 왜 reference가 필요한지 (한국어) |

`claim_context`는 claim-explorer의 `ClaimContext` 모델을 그대로 사용한다:

```python
class ClaimContext(BaseModel):
    abstract: str
    paragraph: str
    claim_type: ClaimType
```

#### claim-explorer 변환

`ExtractedClaim`에서 `ExploreInput`으로의 변환은 직접적이다:

```python
ExploreInput(
    claim_text=extracted_claim.claim_text,
    claim_context=extracted_claim.claim_context,
    max_papers=10,
)
```

### 4.3 ExtractIssue

| 필드 | 타입 | 설명 |
|------|------|------|
| `type` | enum | `parse_failure`, `llm_failure`, `llm_parse_failure`, `invalid_claims` |
| `message` | string | 사람이 읽을 수 있는 설명 |
| `detail` | string? | 에러 메시지 등 추가 정보 |

### 4.4 출력 예시

```json
{
  "status": "success",
  "issues": [],
  "paper_title": "Machine Learning-Based 30-Day Readmission Prediction for Heart Failure Patients",
  "abstract": "This study developed a machine learning-based 30-day readmission prediction model using electronic health records from 12,000 heart failure patients...",
  "claims": [
    {
      "claim_text": "Heart failure affects approximately 6.2 million adults in the United States",
      "claim_context": {
        "abstract": "This study developed a machine learning-based 30-day readmission prediction model...",
        "paragraph": "Heart failure affects approximately 6.2 million adults in the United States, imposing a significant burden on healthcare systems. Thirty-day readmission rates remain high despite various intervention programs.",
        "claim_type": "background"
      },
      "original_sentence": "Heart failure affects approximately 6.2 million adults in the United States, imposing a significant burden on healthcare systems.",
      "section_title": "Introduction",
      "confidence": 0.98,
      "reason": "구체적인 역학 통계(6.2 million)를 포함하는 문장으로, 출처 논문 인용이 필수적임"
    },
    {
      "claim_text": "CatBoost employs ordered boosting and symmetric decision trees, offering robust handling of heterogeneous features and native categorical support",
      "claim_context": {
        "abstract": "This study developed a machine learning-based 30-day readmission prediction model...",
        "paragraph": "We evaluated five gradient boosting frameworks: XGBoost, LightGBM, CatBoost, TabNet, and a tuned random forest baseline. Among the algorithms tested, CatBoost employs ordered boosting and symmetric decision trees, offering robust handling of heterogeneous features and native categorical support. LightGBM uses histogram-based splitting for faster training, while XGBoost remains the most widely adopted in clinical prediction studies.",
        "claim_type": "method"
      },
      "original_sentence": "Among the algorithms tested, CatBoost employs ordered boosting and symmetric decision trees, offering robust handling of heterogeneous features and native categorical support.",
      "section_title": "Methods",
      "confidence": 0.95,
      "reason": "CatBoost 알고리즘의 기술적 특성(ordered boosting, symmetric decision tree)을 서술하는 문장으로, 해당 방법론의 원저 논문 인용이 필요함"
    }
  ],
  "duration_seconds": 5.3
}
```

## 5. LLM 프롬프트 전략

### 5.1 프롬프트 구조

**System 프롬프트:**

```
You are an academic writing assistant. Given a full paper draft in Markdown,
identify sentences that need scholarly references but currently have no citations.

Rules:
- Skip sentences in Abstract, Acknowledgments, and References sections
- Skip sentences that already have citations ([1], (Author et al., 2020), etc.)
- Skip sentences describing the authors' own new analysis, results, or methodology design
- Skip trivial/self-evident statements
- Identify sentences that state facts, mention tools/methods, compare with other studies,
  or reference prior work — these need references

Return a JSON object with:
- paper_title: the title of the paper
- abstract: the full abstract text from the paper
- claims: array of claim objects

For each claim, include:
- claim_text: the core claim for literature search (refined if needed)
- original_sentence: the verbatim original sentence
- section_title: which section it appears in
- paragraph: the full paragraph containing the sentence (verbatim, delimited by blank lines)
- claim_type: one of "background", "method", "result", "interpretation", "limitation"
- confidence: 0.0 to 1.0 (how certain that a reference is needed)
- reason: 1-2 sentence explanation in Korean for why a reference is needed

Return JSON: {"paper_title": "...", "abstract": "...", "claims": [...]}
```

**User 프롬프트:**

```
<paper>
{논문 전문 Markdown}
</paper>
```

### 5.2 기대 LLM 응답

```json
{
  "paper_title": "Machine Learning-Based 30-Day Readmission Prediction...",
  "abstract": "This study developed a machine learning-based 30-day readmission prediction model...",
  "claims": [
    {
      "claim_text": "Heart failure affects approximately 6.2 million adults in the United States",
      "original_sentence": "Heart failure affects approximately 6.2 million adults in the United States, imposing a significant burden on healthcare systems.",
      "section_title": "Introduction",
      "paragraph": "Heart failure affects approximately 6.2 million adults in the United States, imposing a significant burden on healthcare systems. Thirty-day readmission rates remain high despite various intervention programs.",
      "claim_type": "background",
      "confidence": 0.98,
      "reason": "구체적인 역학 통계(6.2 million)를 포함하는 문장으로, 출처 논문 인용이 필수적임"
    }
  ]
}
```

### 5.3 실패 처리

| 실패 유형 | 처리 |
|-----------|------|
| LLM이 유효한 JSON을 반환하지 못함 | 최대 2회 재시도. 재시도에도 실패하면 `failed` 반환 |
| LLM API 호출 실패 (네트워크 등) | 즉시 `failed` 반환, `ExtractIssue`에 기록 |
| JSON 파싱 성공했으나 일부 claim 무효 | 유효한 claim만 사용, `partial` 상태, `ExtractIssue`에 기록 |

### 5.4 토큰 사용량 예측

| 항목 | 예상 토큰 |
|------|----------|
| System 프롬프트 | ~300 토큰 |
| 논문 전문 (입력) | ~7,000-11,000 토큰 |
| LLM 응답 (20-30 claims) | ~3,000-5,000 토큰 |
| **총합** | **~10,000-16,000 토큰** |

LLM 호출 1회로 전체 추출이 완료된다. 재시도 포함 최대 3회.

## 6. 기능 요구사항

각 요구사항에서 LLM이 사용되는 항목은 `[LLM]`으로 표시한다.

### 6.1 파일 처리

- FR-1: Markdown 파일을 UTF-8 텍스트로 읽어야 한다
- FR-2: 빈 파일, 존재하지 않는 파일, 인코딩 오류 시 즉시 `failed`를 반환해야 한다

### 6.2 Claim 추출

- FR-3: `[LLM]` 논문 전문을 LLM에 전달하여 reference가 필요한 문장을 식별해야 한다
- FR-4: `[LLM]` 이미 citation이 있는 문장은 건너뛰어야 한다 (citation 형식은 LLM이 자연어 이해로 판단)
- FR-5: `[LLM]` 각 claim에 대해 claim_type(background, method, result, interpretation, limitation)을 분류해야 한다
- FR-6: `[LLM]` 각 claim에 대해 confidence 점수(0.0-1.0)를 산출해야 한다
- FR-7: `[LLM]` 각 claim에 대해 reference가 필요한 이유를 한국어로 생성해야 한다
- FR-8: `[LLM]` 필요 시 claim_text를 정제하되, 원문 문장은 `original_sentence`에 보존해야 한다
- FR-9: `[LLM]` 각 claim이 소속된 원문 문단을 `paragraph`로 반환해야 한다
- FR-10: `[LLM]` 각 claim이 소속된 섹션 제목을 `section_title`로 반환해야 한다
- FR-11: `[LLM]` Abstract, Acknowledgments, References 섹션의 문장은 추출 대상에서 제외해야 한다
- FR-12: `[LLM]` 논문의 Abstract 텍스트를 추출하여 `abstract` 필드로 반환해야 한다
- FR-13: LLM이 유효한 JSON을 반환하지 못하면 최대 2회 재시도해야 한다

### 6.3 claim 유효성 검증

- FR-14: `claim_text`와 `claim_type`이 모두 있는 claim만 유효로 인정해야 한다. 둘 중 하나라도 없으면 해당 claim을 건너뛴다
- FR-15: `claim_type`은 대소문자 무관 매칭해야 한다. `ClaimType` enum에 매칭되지 않으면 `background`를 기본값으로 사용한다
- FR-16: 선택 필드(`original_sentence`, `section_title`, `paragraph`, `confidence`, `reason`)가 누락되면 기본값으로 대체해야 한다

### 6.4 출력

- FR-17: 추출된 claim을 confidence 내림차순으로 정렬해야 한다
- FR-18: claim이 50개를 초과하면 confidence 상위 50개만 반환해야 한다
- FR-19: 각 claim의 `claim_context`는 claim-explorer의 `ClaimContext` 모델과 호환되어야 한다
- FR-20: 전체 처리 소요 시간을 `duration_seconds`에 기록해야 한다

### 6.5 `[Post-PoC]` 확장

- FR-21: `[Post-PoC]` plain text 입력을 지원해야 한다
- FR-22: `[Post-PoC]` LaTeX 입력을 지원해야 한다
- FR-23: `[Post-PoC]` 영어 외 언어의 논문을 처리할 수 있어야 한다

## 7. 비기능 요구사항

### 7.1 성능

- NFR-1: 일반적인 논문(~8,000 단어)에 대해 전체 추출이 90초 이내여야 한다 (캐시 미스 기준)
- NFR-2: 캐시 히트 시 1초 이내여야 한다

### 7.2 비용

- NFR-3: 논문 1편당 LLM 호출 횟수는 최대 3회 이내여야 한다 (정상 1회 + 재시도 최대 2회)
- NFR-4: LLM 응답은 파일 기반 캐시로 저장하여, 동일 논문에 대한 재실행 시 API 호출을 건너뛰어야 한다

### 7.3 견고성

- NFR-5: LLM 호출이 완전히 실패하면 `status`를 `failed`, `claims`를 빈 배열로 설정하고 사유를 `ExtractIssue`에 기록해야 한다
- NFR-6: 파일 읽기에 실패하면 즉시 `failed`를 반환해야 한다
- NFR-7: 모든 비정상 상황은 `ExtractIssue`로 구조화하여 출력에 포함해야 한다

## 8. 캐싱

### 8.1 캐시 저장소

LLM 응답을 **파일 기반**으로 캐싱한다.

| 대상 | 캐시 키 | 설명 |
|------|---------|------|
| LLM claim 추출 응답 | `(논문 전문, 모델명)`의 SHA-256 해시 | 동일 논문 + 동일 모델 → 캐시 히트 |

캐시 키에 모델명을 포함하는 이유: 모델을 변경하면 동일 논문이라도 다른 결과를 생성할 수 있으므로, stale 캐시 반환을 방지한다.

### 8.2 캐시 디렉터리 레이아웃

```
.cache/claim-extractor/
└── llm/
    └── {hash}.json
```

`{hash}`는 캐시 키의 SHA-256 해시 앞 16자리를 사용한다.

### 8.3 캐시 파일 형식

```json
{
  "cached_at": "2026-04-16T12:00:00Z",
  "input_hash": "a1b2c3d4e5f67890",
  "model": "gpt-5.2",
  "output": { "paper_title": "...", "abstract": "...", "claims": [...] }
}
```

TTL은 두지 않으며, 캐시 디렉터리 삭제로 초기화한다. 논문을 한 글자라도 수정하거나 모델을 변경하면 해시가 바뀌므로 자동으로 새 LLM 호출이 발생한다.

## 9. LLM 설정

### 9.1 모델 설정

| 태스크 | 설정 키 | 기본 모델 |
|--------|---------|-----------|
| claim 추출 | `llm.claim_extract.model` | `gpt-5.2` |

### 9.2 timeout

논문 전문(~10,000 토큰 입력 + ~5,000 토큰 출력)을 한 번에 처리하므로, claim-explorer(문단 단위)보다 긴 timeout이 필요하다.

| 설정 키 | 기본값 | 설명 |
|---------|--------|------|
| `llm.claim_extract.timeout_seconds` | 90 | LLM API 호출 타임아웃 |

### 9.3 재시도 정책

| 항목 | 정책 |
|------|------|
| LLM JSON 파싱 실패 | 최대 2회 재시도. 실패 시 `failed` 반환 |
| LLM API 호출 실패 | 즉시 `failed` 반환 |

## 10. 공통 모듈 리팩터링

### 10.1 LLMClient 일반화

현재 `LLMClient`는 `ExploreSettings`에 강결합되어 있다. extractor에서도 사용하기 위해 공통 인터페이스로 일반화한다.

**현재 (explore 전용):**

```python
class LLMClient:
    def __init__(self, settings: ExploreSettings) -> None:
        self._settings = settings
```

**변경 후 (공통):**

```python
class LLMClient:
    def __init__(self, *, api_key: str, default_model: str, max_calls: int, timeout: int) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._max_calls = max_calls
        self._timeout = timeout
        self._call_count = 0
```

| 변경 | 설명 |
|------|------|
| 위치 이동 | `src/paperworkagent/explore/llm.py` → `src/paperworkagent/common/llm.py` |
| 생성자 | Settings 객체 대신 개별 파라미터(api_key, default_model, max_calls, timeout)를 받는다 |
| explore 쪽 | `ExploreSettings`에서 파라미터를 추출하여 `LLMClient` 생성. import를 `common.llm`으로 변경 |
| extract 쪽 | `ExtractSettings`에서 파라미터를 추출하여 `LLMClient` 생성 |

### 10.2 FileCache 이동

| 변경 | 설명 |
|------|------|
| 위치 이동 | `src/paperworkagent/explore/cache.py` → `src/paperworkagent/common/cache.py` |
| 인터페이스 | 변경 없음 (이미 범용적) |

### 10.3 하위 호환성

이전 경로(`explore/llm.py`, `explore/cache.py`)에 re-export stub을 남기지 않는다. explore 모듈의 모든 import를 `common` 경로로 일괄 변경한다.

```
변경 전: from paperworkagent.explore.llm import LLMClient
변경 후: from paperworkagent.common.llm import LLMClient

변경 전: from paperworkagent.explore.cache import FileCache
변경 후: from paperworkagent.common.cache import FileCache
```

이전 파일(`explore/llm.py`, `explore/cache.py`)은 삭제한다.

### 10.4 공유 모델

| 모듈 | 위치 | 재사용 방법 |
|------|------|-------------|
| `ClaimType`, `ClaimContext` | `src/paperworkagent/explore/models.py` | claim-explorer 호환성 보장을 위해 직접 import. 중복 정의 금지 |

### 10.5 ExtractSettings 설계

```python
class ExtractLLMTaskSettings(BaseSettings):
    model: str = "gpt-5.2"
    temperature: float = 0.1
    timeout_seconds: int = 90


class ExtractLLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    provider: str = "openai"
    model: str = "gpt-5.2"
    api_key: str = ""

    claim_extract: ExtractLLMTaskSettings = Field(default_factory=ExtractLLMTaskSettings)


class ExtractSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm: ExtractLLMSettings = Field(default_factory=ExtractLLMSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    max_llm_calls: int = 3
```

`CacheSettings`는 explore와 공유하되, `directory` 기본값은 `Path(".cache/claim-extractor")`로 오버라이드한다.

## 11. 실행 인터페이스

### 11.1 CLI

```bash
python -m paperworkagent.cli extract \
  --paper draft.md \
  --out claims.json \
  --verbose
```

### 11.2 Cursor 스킬

```
.cursor/skills/claim-extractor/SKILL.md
```

### 11.3 Python API

```python
from paperworkagent.extract.extractor import extract_claims
from paperworkagent.extract.config import load_settings
from paperworkagent.extract.models import ExtractInput

settings = load_settings()
inp = ExtractInput(paper_path="draft.md")
result = await extract_claims(inp, settings)

# claim-explorer와 연동
from paperworkagent.explore.models import ExploreInput
for claim in result.claims:
    explore_input = ExploreInput(
        claim_text=claim.claim_text,
        claim_context=claim.claim_context,
    )
```

## 12. 데이터 구조

### 12.1 Python 데이터 모델

```python
from pydantic import BaseModel, Field
from enum import Enum
from paperworkagent.explore.models import ClaimType, ClaimContext


class ExtractStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExtractIssueType(str, Enum):
    PARSE_FAILURE = "parse_failure"
    LLM_FAILURE = "llm_failure"
    LLM_PARSE_FAILURE = "llm_parse_failure"
    INVALID_CLAIMS = "invalid_claims"


MAX_CLAIMS: int = 50


class ExtractInput(BaseModel):
    paper_path: str


class ExtractedClaim(BaseModel):
    claim_text: str
    claim_context: ClaimContext
    original_sentence: str
    section_title: str
    confidence: float
    reason: str


class ExtractIssue(BaseModel):
    type: ExtractIssueType
    message: str
    detail: str | None = None


class ExtractOutput(BaseModel):
    status: ExtractStatus
    issues: list[ExtractIssue] = Field(default_factory=list)
    paper_title: str | None = None
    abstract: str
    claims: list[ExtractedClaim]
    duration_seconds: float
```

## 13. 수용 기준

### PoC 수용 기준

- Markdown 논문 파일을 입력으로 받아 LLM에 전문을 전달한다
- LLM이 이미 citation이 있는 문장을 건너뛰고, reference가 필요한 문장을 식별하여 claim으로 추출한다
- LLM이 논문의 abstract를 추출하여 모든 claim의 context에 공유한다
- 각 claim에 claim_type, confidence 점수, 한국어 reason이 포함된다
- 각 claim에 소속 섹션 제목과 원문 문단이 포함된다
- 추출된 claim의 `claim_context`가 claim-explorer의 `ExploreInput`과 호환된다
- claim 유효성 검증: `claim_text`와 `claim_type`이 필수이며, 나머지 필드는 기본값으로 대체된다
- `claim_type` 파싱 실패 시 `background`를 기본값으로 사용한다
- LLM JSON 파싱 실패 시 최대 2회 재시도한다
- 추출 상태(status: success/partial/failed)와 발생 이슈(issues)가 출력에 포함된다
- LLM 실패 등 비정상 상황에서도 구조화된 에러를 반환한다
- LLM 응답이 파일 기반 캐시로 저장된다. 캐시 키에 모델명이 포함된다
- 논문 1편(~8,000 단어)당 90초 이내에 완료된다
- LLM 호출은 논문당 최대 3회 이내이다 (정상 1회 + 재시도 2회)
- `LLMClient`와 `FileCache`가 `common` 패키지로 이동되고, explore의 기존 import가 모두 새 경로로 변경된다
- CLI와 Cursor 스킬로 단독 실행 가능하다
- Python API로 claim-explorer와 프로그래밍 방식으로 연동할 수 있다

### Post-PoC 수용 기준

- plain text, LaTeX 등 추가 입력 포맷을 지원한다
- 영어 외 언어의 논문을 처리할 수 있다
