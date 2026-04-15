---
name: paper-reference-agent
description: >-
  논문 초안 Markdown과 결과 파일을 입력받아 주장 추출, 문헌 검색, 사실 검증,
  참고문헌 추천까지 전체 파이프라인을 실행한다. 사용자가 논문 레퍼런스 정리,
  참고문헌 추천, 인용 검증, 문헌 분석을 요청할 때 사용한다.
---

# Paper Reference Agent

## 사전 조건

- 프로젝트 루트에서 `source .venv/bin/activate` 가능해야 함
- `.env`에 LLM API 키 설정 (선택, 없어도 기본 기능 동작)

## 워크플로

1. 사용자에게 원고 파일 경로를 확인한다. 결과 파일 디렉터리가 있는지도 확인한다.

2. 파이프라인을 실행한다:

```bash
cd /Users/goeastagent/products/paperworkagent
source .venv/bin/activate
python -m paperworkagent.cli run \
  --manuscript <원고경로> \
  --out runs/<run_id>
```

3. 실행이 완료되면 산출물을 확인한다:
   - `runs/<run_id>/claims.jsonl` — 추출된 주장 목록을 읽고 개수와 섹션 분포를 요약
   - `runs/<run_id>/report.md` — 추천 보고서를 읽고 핵심 내용을 사용자에게 전달
   - `runs/<run_id>/paper.with_refs.md` — 패치된 원고가 존재하는지 확인

4. 보고서에서 다음 항목을 우선 확인하고 사용자에게 알린다:
   - 경고 사항 (근거 부족, 반대 문헌)
   - confidence가 낮은 추천 (수동 확인 권고)
   - contradiction 라벨이 붙은 claim-paper 쌍

5. 사용자가 특정 claim에 대해 추가 검토를 요청하면 부분 재실행한다:

```bash
python -m paperworkagent.cli run \
  --from retrieve --out runs/<run_id>
```

## 산출물 구조

```
runs/<run_id>/
├── claims.jsonl          # 추출된 주장 (JSONL)
├── papers.jsonl          # 후보 문헌 (JSONL)
├── assessments.jsonl     # claim-paper 평가 (JSONL)
├── report.md             # 추천 보고서
└── paper.with_refs.md    # 참고문헌 주석이 삽입된 원고
```
