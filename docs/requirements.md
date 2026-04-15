# 논문 레퍼런스 에이전트 요구사항

## 1. 개요

### 1.1 목적
논문 초안(Markdown)과 결과 파일을 입력받아, 주장 단위를 식별하고, 관련 문헌을 탐색하며, 사실 검증과 근거 적합성 평가를 수행한 뒤, 삽입 가능한 참고문헌 후보를 제안하는 에이전트를 구축한다.

### 1.2 문제 정의
연구자는 분석 결과와 논문 초안을 가지고 있어도 다음 작업을 체계적으로 수행하기 어렵다.

- 초안의 문장을 주장 단위로 분해하는 일
- 각 주장에 맞는 선행연구를 찾는 일
- 해당 문헌이 실제로 주장을 지지하는지, 일부만 지지하는지, 반박하는지 판별하는 일
- 방법론적 근거, 실험 결과 근거, 해석적 근거를 구분하는 일
- 논문 본문에 실제로 추가 가능한 참고문헌 형태로 정리하는 일

본 시스템은 이러한 수작업 부담을 줄이되, 근거 추적 가능성과 최종 인간 검토 가능성을 유지해야 한다.

### 1.3 제품 형태
하나의 오케스트레이터가 전체 흐름을 조정하고, 기능별 모듈이 입력 파싱, 문헌 검색, 관련성 평가, 사실 검증, 인용문 작성을 담당하는 모듈형 파이프라인 구조로 구현한다.

Cursor 에이전트가 전체 파이프라인, 문헌 검색, fact-check를 호출할 수 있도록 Cursor 스킬 인터페이스를 제공한다. 스킬은 에이전트에게 실행 절차를 알려주는 지침이며, 핵심 데이터 처리 로직은 Python 패키지로 구현한다. (상세 구조는 아키텍처 문서 5절 참조)

### 1.4 API 사용 원칙

- 문헌 검색과 메타데이터 수집은 무료 또는 공개 API만으로 동작해야 한다
- 무료 API key 또는 email 기반 식별은 허용한다
- 유료 플랜이나 상용 논문 데이터 API를 필수 의존성으로 두지 않는다
- LLM은 선택 가능한 처리 계층으로 사용하며, `.env`를 통해 자격 증명을 주입한다
- 특정 무료 API의 rate limit이 낮거나 일시 불가한 경우 다른 무료 provider로 부분 동작 가능해야 한다

## 2. 목표

### 2.1 주요 목표

- Markdown 논문 초안과 구조화된 결과 파일을 입력받을 수 있어야 한다
- 본문을 주장 단위로 분해할 수 있어야 한다
- 각 주장에 대해 관련 문헌을 탐색할 수 있어야 한다
- 각 문헌이 주장과 얼마나 관련 있는지, 사실상 어떤 관계인지 평가할 수 있어야 한다
- 신뢰도와 근거 설명을 포함한 참고문헌 추천을 생성할 수 있어야 한다
- 파일 기반 결과물로 사용자가 검토하고 채택 또는 거절할 수 있는 형태를 제공해야 한다

### 2.2 초기 버전의 비목표

- 사용자 검토 없이 논문 본문을 완전히 자동 수정하는 기능
- 유료 API 구독 또는 상용 데이터 소스를 전제로 한 구현
- LLM만으로 문헌 검색과 사실 검증을 대체하는 구조
- 논쟁적인 해석에 대해 도메인 전문가 판단을 대체하는 기능
- 웹 UI

## 3. 사용자

### 3.1 주요 사용자

- 논문을 작성 중인 연구자
- 실험 결과를 바탕으로 원고를 정리하는 연구실 구성원
- 내부 리뷰 또는 사전 검토를 수행하는 편집자나 공동저자

### 3.2 사용자 요구

- 본문 주장과 기존 문헌을 연결하고 싶다
- 근거가 약하거나 인용이 빠진 문장을 찾고 싶다
- 단순한 미인용과 실제 사실 오류를 구분하고 싶다
- 참고문헌을 실제 원고 작업 흐름에 넣을 수 있는 형태로 받고 싶다

## 4. 입력과 출력

### 4.1 입력

- 논문 초안 Markdown 파일 (`.md`)
- 구조화된 결과 파일: `csv`, `tsv`, `xlsx`
- 선택 입력: DOI 목록, PMID 목록, seed paper 목록, BibTeX 파일
- 선택 입력: 생의학 메타데이터 (생물종, 질환명, 세포주 등)
- 환경 설정: `.env` (비밀값), `config/project.yaml` (런타임 설정)

### 4.2 출력

- 구조화 주장 목록: `runs/<run_id>/claims.jsonl`
- 후보 문헌 목록: `runs/<run_id>/papers.jsonl`
- 주장-논문 평가: `runs/<run_id>/assessments.jsonl`
- 추천 결과 보고서: `runs/<run_id>/report.md`
- 참고문헌 반영 제안 원고: `runs/<run_id>/paper.with_refs.md`
- 차이 비교용 패치: `runs/<run_id>/paper.patch.md`

### 4.3 출력 예시

**claims.jsonl 레코드 예시:**

```json
{
  "claim_id": "c-003",
  "section": "results",
  "claim_text": "BRCA1 knockdown significantly reduced cell viability in MDA-MB-231 cells (p < 0.01).",
  "claim_type": "result",
  "needs_reference": true,
  "source_location": {"start_line": 45, "end_line": 45, "section": "results"}
}
```

**assessments.jsonl 레코드 예시:**

```json
{
  "claim_id": "c-003",
  "paper_id": "doi:10.1038/s41586-023-06747-5",
  "relevance_score": 0.82,
  "factcheck_label": "support",
  "confidence": 0.75,
  "rationale": "해당 논문은 동일 세포주(MDA-MB-231)에서 BRCA1 억제 시 세포 생존율 감소를 보고하며, 효과 방향과 실험 조건이 일치한다.",
  "evidence_spans": [
    "BRCA1 depletion led to a 40% reduction in cell viability in triple-negative breast cancer cell lines including MDA-MB-231 (Fig. 3a)."
  ]
}
```

**paper.with_refs.md 패치 예시:**

```markdown
BRCA1 knockdown significantly reduced cell viability in MDA-MB-231 cells (p < 0.01).
<!-- [REF_CANDIDATE: c-003 -> doi:10.1038/s41586-023-06747-5 | support | confidence=0.75] -->
```

## 5. 핵심 워크플로

### 5.1 1단계: 입력 처리
논문 초안과 결과 파일을 내부 표준 구조로 정규화한다.

- Markdown 헤더 구조를 파싱하고 섹션 경계를 유지한다
- 표, 그림 설명, 결과 요약을 추출한다
- 구조화된 결과 파일에서 변수명, 지표, 비교 대상을 파악한다
- 모든 파싱 결과에 대해 provenance를 유지한다

### 5.2 2단계: 주장 추출
논문 본문을 주장 단위로 분해한다.

최소한 다음 유형의 주장을 구분해야 한다.

- 배경 설명 주장
- 방법론 주장
- 실험 결과 주장
- 해석 또는 논의 주장
- 한계 또는 주의점

이 단계는 LLM 보조 분류를 사용하면 품질이 크게 향상된다. LLM 없이는 rule-based 문장 분리만 제공하며, claim type 자동 분류 정확도가 제한적이다.

### 5.3 3단계: 문헌 검색
각 주장에 대해 관련 문헌 후보를 수집한다.

검색 방식:

- LLM이 claim_text에서 검색 키워드를 직접 생성
- claim_type에 따라 다중 각도 질의 (Claim Explorer)
- seed paper 확장
- reference graph 및 cited-by 확장
- 관련성 기반 필터링 후 적응적 재검색

상세 탐색 전략은 `claim-explorer-requirements.md`를 참조한다.

### 5.4 4단계: 관련성 분석
후보 문헌이 특정 주장과 얼마나 관련 있는지 평가한다. LLM이 claim과 논문 초록을 비교하여 직접 판정한다.

### 5.5 5단계: 사실 검증
검색된 문헌이 해당 주장을 어떤 방식으로 뒷받침하는지 판정한다.

라벨: `support`, `partial`, `contradict`, `unrelated`

결과는 라벨과 함께 짧은 근거 설명을 포함해야 한다. LLM은 evidence span 요약과 rationale 초안 생성에 사용할 수 있으나, 원문 근거 없이 라벨을 생성해서는 안 된다.

### 5.6 6단계: 참고문헌 추천
각 주장에 대해 실제로 인용 가능한 문헌을 추천한다.

초기 버전에서는 완전한 citation style 변환보다 식별 가능한 수준의 추천을 우선한다:

- 제목, 저자, 연도, DOI 또는 PMID
- 추천 이유
- 신뢰도(confidence)
- 논문 내 삽입 위치 제안

### 5.7 7단계: 사용자 검토
추천 결과를 사람이 검토할 수 있는 형태로 제공하며, 채택/거절/보류를 선택할 수 있어야 한다. 초기 인터페이스는 파일 기반이다.

## 6. 기능 요구사항

### 6.1 입력 처리

- FR-1: `.md` 형식의 논문 입력 파일을 받아야 한다
- FR-2: 섹션 구분과 문단 경계를 유지해야 한다
- FR-3: `csv`, `tsv`, `xlsx` 형식의 결과 파일을 받아야 한다
- FR-4: 주장과 원문 위치를 연결하는 provenance를 유지해야 한다

### 6.2 주장 추출

- FR-5: 논문 본문을 주장 단위로 분할해야 한다
- FR-6: 각 주장에 대해 섹션과 주장 유형을 분류해야 한다
- FR-7: 외부 참고문헌이 필요한 claim과 불필요한 claim을 구분해야 한다
- FR-8: 실험 결과 진술과 해석적 진술을 구분해야 한다

### 6.3 문헌 검색

- FR-9: 각 주장에 대해 하나 이상의 검색 질의를 생성해야 한다
- FR-10: 설정된 문헌 소스로부터 후보 논문 메타데이터를 수집해야 한다
- FR-11: citation graph 확장을 수행할 수 있어야 한다
- FR-12: 여러 공급자에서 수집된 중복 논문을 제거해야 한다
- FR-13: DOI, PMID, PMCID 등의 식별자를 보존해야 한다
- FR-14: OpenAlex와 Crossref만으로 기본 검색 흐름을 수행할 수 있어야 한다
- FR-15: 특정 provider의 quota 또는 rate limit에 도달했을 때 fallback 또는 부분 결과를 반환해야 한다

### 6.4 분석 및 사실 검증

- FR-16: 주장과 논문 간 관련성 점수를 계산해야 한다
- FR-17: 주장-논문 쌍마다 fact-check 라벨을 부여해야 한다
- FR-18: 메타데이터 또는 본문 근거에 기반한 설명을 생성해야 한다
- FR-19: 근거가 불충분한 주장을 식별해야 한다
- FR-20: 주장과 상충될 가능성이 있는 문헌을 표시해야 한다

### 6.5 참고문헌 출력

- FR-21: 주장별로 우선순위가 매겨진 참고문헌 추천을 생성해야 한다
- FR-22: 최소한 제목, 저자, 연도, DOI 또는 PMID를 포함한 추천 정보를 제공해야 한다
- FR-23: 섹션 및 claim ID와 연결된 삽입 제안을 제공해야 한다
- FR-24: 추천 결과에서 근거와 원천 문헌까지 역추적 가능해야 한다
- FR-25: 참고문헌이 반영된 Markdown 결과 파일 또는 패치 파일을 생성해야 한다

### 6.6 검토

- FR-26: 각 추천에 대해 confidence와 rationale을 제공해야 한다
- FR-27: 채택, 거절, 나중에 검토를 지원해야 한다
- FR-28: 주장 수정 후 검색이나 점수 산정을 다시 실행할 수 있어야 한다

## 7. 섹션별 동작 기준

1차 최적화 대상은 생의학 논문이다.

### 7.1 Methods

- 방법론적 유사성
- 프로토콜 비교 가능성
- 장비 또는 assay 일치 여부
- 생물종, 세포주, 조직, 샘플 처리 조건의 일치성

### 7.2 Results

- 효과 방향의 일치성
- 사용된 결과 지표의 유사성
- 통계적 또는 정량적 비교 가능성
- biomarker, phenotype, pathway, treatment response 등의 결과 요소 일치성

### 7.3 Discussion

- 해석을 지지하는 문헌 존재 여부
- 기존 문헌과의 비교 또는 차이
- 과도한 일반화 또는 overclaim 가능성
- 반대 문헌 존재 여부

## 8. 데이터 모델

### 8.1 Claim Record

| 필드 | 타입 | 설명 |
|------|------|------|
| `claim_id` | string | 고유 식별자 (예: `c-003`) |
| `section` | string | 원본 섹션명 |
| `claim_text` | string | 주장 원문 |
| `claim_type` | enum | `background`, `method`, `result`, `interpretation`, `limitation` |
| `needs_reference` | bool | 외부 참고문헌이 필요한지 여부 |
| `source_location` | object | `{start_line, end_line, section}` |

### 8.2 Candidate Paper Record

| 필드 | 타입 | 설명 |
|------|------|------|
| `paper_id` | string | DOI 우선, 없으면 PMID 또는 내부 ID |
| `title` | string | 논문 제목 |
| `authors` | string[] | 저자 목록 |
| `year` | int | 출판 연도 |
| `venue` | string | 학술지명 |
| `abstract` | string | 초록 |
| `doi` | string? | DOI |
| `pmid` | string? | PubMed ID |
| `pmcid` | string? | PMC ID |
| `source_providers` | string[] | 수집 provider 목록 |
| `open_access_url` | string? | OA 전문 URL |

### 8.3 Assessment Record

| 필드 | 타입 | 설명 |
|------|------|------|
| `claim_id` | string | 주장 ID |
| `paper_id` | string | 논문 ID |
| `relevance_score` | float | 0.0 ~ 1.0 |
| `factcheck_label` | enum | `support`, `partial`, `contradict`, `unrelated` |
| `confidence` | float | 0.0 ~ 1.0 |
| `rationale` | string | 판정 근거 설명 |
| `evidence_spans` | string[] | 근거 문장 목록 |

## 9. 비기능 요구사항

### 9.1 추적 가능성

- NFR-1: 모든 추천 결과는 원본 주장과 원본 논문까지 추적 가능해야 한다
- NFR-2: provider 식별자와 검색 provenance를 보존해야 한다

### 9.2 모듈성

- NFR-3: 입력 처리, 검색, 점수 산정, 출력 생성이 분리된 모듈 구조여야 한다
- NFR-4: 각 모듈은 독립적으로 테스트 가능해야 한다

### 9.3 확장성

- NFR-5: 새로운 문헌 공급자를 전체 구조 변경 없이 추가할 수 있어야 한다
- NFR-6: 생의학 중심 규칙을 기본값으로 하되, 분야별 점수 산정 규칙을 설정 가능해야 한다

### 9.4 신뢰성

- NFR-7: 공식 API와 안정적인 메타데이터 소스를 우선 사용해야 한다
- NFR-8: 특정 provider가 일시 불가할 때도 부분 동작이 가능해야 한다
- NFR-9: 무료 API의 rate limit과 quota를 고려한 요청 빈도 제한, 캐싱, 재시도 전략을 가져야 한다

### 9.5 비용 제약

- NFR-10: 필수 기능 수행을 위해 유료 API 구독을 요구해서는 안 된다
- NFR-11: 문헌 검색과 메타데이터 수집은 무료 provider만으로 수행되어야 한다
- NFR-12: LLM 미설정 시 축소 기능 모드로 동작할 수 있어야 한다. 단, claim 분류 정확도와 rationale 품질이 크게 저하됨을 사용자에게 명시해야 한다

### 9.6 안전성과 품질

- NFR-13: 근거가 불충분한 주장을 완전히 검증된 것으로 표시해서는 안 된다
- NFR-14: 불확실성과 반대 근거 가능성을 사용자에게 드러내야 한다
- NFR-15: LLM이 생성한 설명은 항상 원문 근거 span 또는 메타데이터와 연결되어야 한다

## 10. LLM 의존도 명세

LLM은 "선택 사항"이나 실질적 영향도는 높다. 아래 표는 LLM 유무에 따른 기능 차이를 명시한다.

| 기능 | LLM 활성 | LLM 비활성 |
|------|----------|------------|
| claim 분할 | 문맥 기반 재구성 | 문장 단위 기계적 분리 |
| claim type 분류 | 정확도 높음 | rule-based, 정확도 제한적 |
| 검색 질의 생성 | discussion 등 복잡 문장 처리 가능 | 키워드 추출만 가능 |
| evidence span 선별 | full-text에서 관련 문단 우선 선별 | 전체 본문 대상 lexical match만 가능 |
| rationale 생성 | 자연어 설명 | 점수와 라벨만 제공 |
| 추천 이유 문장화 | 사람이 읽기 쉬운 설명 | 메타데이터 나열 |

## 11. 외부 연동

### 11.1 Provider 우선순위

| 순위 | Provider | 역할 | 필수 여부 |
|------|----------|------|-----------|
| 1순위 | OpenAlex | 메타데이터, citation graph | 필수 |
| 1순위 | Crossref | DOI 중심 서지 메타데이터 | 필수 |
| 1순위 | Europe PMC / PMC | 생의학 메타데이터, full-text | 생의학 분야 필수 |
| 2순위 | Semantic Scholar | paper graph, 추천 보조 | 선택 |
| 2순위 | Unpaywall | 오픈액세스 경로 탐색 | 선택 |

핵심 파이프라인은 1순위 provider만으로 동작해야 하며, 2순위는 결과 보강용 선택 옵션이다.

### 11.2 연동 원칙

- 공식 API를 우선 사용한다
- 무료 또는 공개 API만 사용한다
- 무료 API key 발급이 필요한 경우 설정 단계에서 안내한다
- full-text가 필요한 경우 오픈액세스 경로를 우선 사용한다
- 유료 플랜에서만 제공되는 엔드포인트에 의존하지 않는다

## 12. MVP 범위

### 12.1 MVP에 반드시 포함

- Markdown 파서 + 결과 파일 로더
- claim 추출기 (rule-based + LLM 보조)
- OpenAlex + Crossref + Europe PMC adapter
- full-text fetcher (OA 경로)
- relevance scorer + fact-checker
- report writer + markdown patch writer
- 파일 기반 결과 출력

### 12.2 MVP 이후

- Semantic Scholar adapter
- Unpaywall adapter
- 고급 citation formatter (BibTeX, CSL-JSON 자동 변환)
- discussion 반대 문헌 및 overclaim 분석 강화
- 인터랙티브 UI
- 사용자 피드백 학습 루프

## 13. 수용 기준

초기 프로토타입은 다음 조건을 만족해야 한다.

- 논문 초안을 입력하면 구조화된 주장 목록을 생성할 수 있다
- 각 주장에 대해 복수의 후보 문헌을 메타데이터와 함께 수집할 수 있다
- 주장-논문 쌍에 대해 관련성 점수와 fact-check 라벨을 생성할 수 있다
- 사용자는 각 추천의 근거를 확인할 수 있다
- 근거 부족 또는 반대 가능성이 있는 주장은 명시적으로 표시된다
- 유료 API 없이도 최소 기능이 끝까지 수행된다
- `.md` 원고 파일을 입력받아 참고문헌 추천이 반영된 파일 기반 결과를 생성할 수 있다
- LLM 활성화 시 claim 분류와 추천 설명 품질이 향상되며, 비활성화 시에도 검색 파이프라인은 유지된다
