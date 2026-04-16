---
name: claim-explorer
description: >-
  단일 claim과 그 context를 입력받아, 여러 라운드의 탐색적 검색을 수행하여
  해당 claim에 가장 관련성 높은 논문 후보를 찾아낸다. 논문 레퍼런스 탐색,
  관련 문헌 검색, claim 기반 문헌 조사를 요청할 때 사용한다.
---

# Claim Explorer

단일 claim에 대해 다중 각도 검색 + LLM 관련성 필터를 수행하여 관련 논문을 찾는다.

## 워크플로

1. 사용자에게 다음 정보를 확인한다:
   - **claim**: 탐색할 주장 문장
   - **abstract**: 원본 논문의 초록
   - **paragraph**: claim이 등장한 원문 문단
   - **claim_type**: background, method, result, interpretation, limitation 중 하나

2. 탐색을 실행한다:
   ```bash
   python -m paperworkagent.cli explore \
     --claim "<주장 문장>" \
     --abstract "<초록>" \
     --paragraph "<원문 문단>" \
     --type <claim_type> \
     --max-papers 10 \
     --out exploration.json \
     --verbose
   ```

3. `exploration.json`을 읽고 결과를 확인한다:
   - `status` 필드를 확인하여 탐색 성공 여부를 판단한다
     - `success`: 모든 라운드 정상 완료
     - `partial`: 일부 문제 발생했으나 결과 있음
     - `failed`: 유의미한 결과 없음
   - `issues` 배열에 문제가 있으면 사용자에게 알린다
   - `papers` 배열의 논문을 관련성(high → medium → low) 순으로 정리하여 보고한다
   - 각 논문의 `relevance_reason`을 함께 제공한다

4. 결과를 사용자에게 요약한다:
   - `summary` 필드의 한국어 요약을 전달한다
   - high 관련성 논문을 강조한다
   - 검색 통계(search_log)에서 질의 수, 발견 논문 수를 보고한다

5. 사용자가 추가 탐색을 원하면:
   - 다른 claim_type으로 재실행하거나
   - max-papers를 늘려서 재실행한다
