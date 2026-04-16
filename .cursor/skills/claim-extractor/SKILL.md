---
name: claim-extractor
description: >-
  논문 초안(Markdown)을 입력받아, reference가 필요하지만 아직 citation이 없는 문장을
  자동으로 식별하여 구조화된 claim 목록으로 출력한다. 논문에서 claim 추출,
  레퍼런스 필요 문장 식별, claim-explorer 입력 준비를 요청할 때 사용한다.
---

# Claim Extractor

논문 Markdown 파일에서 reference가 필요한 문장을 LLM으로 추출하여 claim-explorer가 소비할 수 있는 구조화된 claim 목록을 생성한다.

## 워크플로

1. 사용자에게 다음 정보를 확인한다:
   - **논문 파일**: Markdown 형식의 논문 초안 경로

2. 추출을 실행한다:
   ```bash
   python -m paperworkagent.cli extract \
     --paper "<논문 파일 경로>" \
     --out claims.json \
     --verbose
   ```

3. `claims.json`을 읽고 결과를 확인한다:
   - `status` 필드를 확인하여 추출 성공 여부를 판단한다
     - `success`: 정상 완료
     - `partial`: 일부 claim이 무효 처리됨
     - `failed`: 유의미한 결과 없음
   - `issues` 배열에 문제가 있으면 사용자에게 알린다
   - `claims` 배열의 claim을 confidence 순으로 정리하여 보고한다
   - 각 claim의 `section_title`, `claim_type`, `reason`을 함께 제공한다

4. 결과를 사용자에게 요약한다:
   - 총 추출된 claim 수를 보고한다
   - claim_type별 분포(background, method, result, interpretation, limitation)를 보고한다
   - confidence가 높은 상위 claim을 강조한다

5. claim-explorer와 연동이 필요하면:
   - 각 claim의 `claim_text`와 `claim_context`를 claim-explorer에 전달할 수 있다
   - claim-explorer 스킬을 사용하여 개별 claim에 대한 관련 논문 탐색을 수행한다
