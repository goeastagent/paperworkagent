# PaperworkAgent

논문 초안에서 주장을 추출하고, 관련 문헌을 검색하며, 사실 검증과 참고문헌 추천을 수행하는 에이전트.

## 설치

```bash
pip install -e ".[dev]"
```

## 사용법

```bash
# 전체 파이프라인 실행
paper-agent run --manuscript paper.md --results results/ --out runs/run-001

# 문헌 검색만 실행
paper-agent search --query "BRCA1 cell viability" --out results.json

# 개별 fact-check
paper-agent fact-check --claim "..." --paper-id "doi:10.1038/..." --out result.json
```

## 설정

- `.env` — API 키 등 비밀값
- `config/project.yaml` — 런타임 설정 (provider, scoring weights 등)

## 구조

```
src/paperworkagent/
├── ingest/      # Markdown 파싱, claim 추출
├── retrieve/    # 문헌 검색, provider 어댑터
├── assess/      # 관련성 점수, fact-check
├── write/       # 보고서, Markdown 패치
├── llm/         # LLM 클라이언트, 프롬프트
└── infra/       # 캐시, rate limiter
```

## 테스트

```bash
pytest
```
