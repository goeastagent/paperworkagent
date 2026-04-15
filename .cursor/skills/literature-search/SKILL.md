---
name: literature-search
description: >-
  키워드, DOI, 또는 주제 문장으로 관련 학술 문헌을 검색한다. 논문 찾기,
  선행연구 검색, 문헌 조사, 관련 논문 탐색을 요청할 때 사용한다.
---

# Literature Search

## 사전 조건

- 프로젝트 루트에서 `source .venv/bin/activate` 가능해야 함

## 워크플로

1. 사용자의 검색 의도를 파악한다 (키워드, DOI, 자연어 주제 문장).

2. 검색을 실행한다:

```bash
cd /Users/goeastagent/products/paperworkagent
source .venv/bin/activate
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

4. 사용자가 특정 논문의 상세 정보를 원하면 DOI로 추가 검색한다.

## 매개변수 참고

- `--providers`: 쉼표 구분. 기본값 `openalex,crossref,europepmc`
- `--max-results`: 기본값 20, 최대 50
- `--out`: 결과 JSON 파일 경로
