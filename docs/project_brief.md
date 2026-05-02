# PersonaGraph Project Brief

## 한 줄 설명

PersonaGraph는 사용자의 문제를 입력받아 여러 AI Agent가 서로 다른 페르소나와 역할로 의견을 제시하고, Critic이 약점을 지적한 뒤 Synthesizer가 최종 해결안을 만드는 다중 에이전트 문제 해결 시스템이다.

## 2주 MVP 목표

첫 목표는 거대한 에이전트 프레임워크가 아니라, 하나의 문제 입력에서 다음 5단계 로그가 안정적으로 출력되는 데모다.

1. 사용자가 문제를 입력한다.
2. Persona Generator가 필요한 페르소나 3~5개를 만든다.
3. Specialist Agent들이 각자 관점에서 의견을 낸다.
4. Critic Agent가 모순, 약점, 누락을 지적한다.
5. Synthesizer Agent가 최종 답변과 다음 액션을 만든다.
6. Evaluator Agent가 최종 결과를 평가하고 실행 로그를 저장한다.

## 핵심 차별점

- 단순히 AI 응답을 여러 번 호출하는 것이 아니라, 역할 생성부터 비판과 종합까지 이어지는 구조화된 추론 흐름을 보여준다.
- 각 단계의 로그를 UI에서 분리해 보여주기 때문에 발표자가 "왜 이 결론이 나왔는지" 설명하기 쉽다.
- 평가 점수와 저장된 실행 로그를 통해 "한 번 나온 답변"이 아니라 반복 가능한 문제 해결 워크플로임을 보여준다.
- LLM API가 실패해도 로컬 폴백이 동작해 발표 안정성을 확보한다.

## 기술 스택

- Backend: Python, FastAPI
- UI: Streamlit
- LLM: OpenAI-compatible Chat Completions API
- Configuration: `.env`, `OPENAI_API_KEY`, `PERSONA_GRAPH_MODEL`
- Storage: local JSON files under `data/runs/`

## MVP 이후 확장 후보

- 답변 품질 비교용 baseline 모드
- Next.js 기반 발표용 UI
- LangGraph 스타일 상태 머신으로 워크플로 고도화
