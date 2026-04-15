---
name: fact-check-claim
description: >-
  주장 텍스트와 논문 정보를 입력받아 support, partial, contradict, unrelated
  라벨과 근거 설명을 생성한다. 사실 검증, 주장 확인, 문헌 근거 확인,
  논문 주장 검증을 요청할 때 사용한다.
---

# Fact Check Claim

## 사전 조건

- 프로젝트 루트에서 `source .venv/bin/activate` 가능해야 함

## 워크플로

1. 사용자에게 검증할 주장과 대상 논문(DOI 또는 제목)을 확인한다.

2. fact-check를 실행한다:

```bash
cd /Users/goeastagent/products/paperworkagent
source .venv/bin/activate
python -m paperworkagent.cli fact-check \
  --claim "<주장 텍스트>" \
  --paper-id "<DOI 또는 PMID>" \
  --out result.json
```

3. `result.json`을 읽고 결과를 보고한다:
   - fact-check 라벨: `support` / `partial` / `contradict` / `unrelated`
   - confidence 점수 (0–100%)
   - 근거 설명 (rationale)
   - evidence span (해당 논문에서 근거가 된 문장)

4. confidence가 낮으면 사용자에게 수동 확인을 권고한다.

## 라벨 해석

| 라벨 | 의미 |
|------|------|
| support | 문헌이 주장을 지지함 |
| partial | 일부만 지지하거나 조건이 다름 |
| contradict | 문헌이 주장과 상충함 |
| unrelated | 관련성이 낮음 |
