# PersonaGraph

PersonaGraph는 하나의 문제를 여러 페르소나 에이전트가 각자의 관점으로 토론하고, 사용자가 중간중간 의견을 더하면 Agent들이 이어서 반응하며 최종 결론을 갱신하는 다중 에이전트 의사결정 데모입니다.

## MVP Flow

1. 사용자가 문제를 입력합니다.
2. Persona Generator가 필요한 페르소나 3~5개를 생성합니다. 기본값은 5명입니다.
3. 미리 정의된 데포르메 피규어형 페르소나 이미지와 성격 중 하나를 각 페르소나에 임의로 배정합니다.
4. Moderator Agent가 의제, 발언 순서, 상호 응답 규칙을 안내합니다.
5. Specialist Agent들이 자기 관점으로 첫 의견을 제시합니다.
6. Moderator Agent가 응답 라운드의 논점을 좁히고, Specialist Agent들이 앞선 발언에 직접 동의, 반박, 보완합니다.
7. Critic Agent가 전체 토론의 모순, 약점, 누락을 지적합니다.
8. Synthesizer Agent가 최종 답변을 통합합니다.
9. Evaluator Agent가 최종 결과를 점수와 총평으로 평가합니다.
10. Streamlit UI에서 배너, 데포르메 페르소나 캐릭터, 에이전트 토론 네트워크, 대화창형 토론 로그, 최종 결론, 평가 요약을 표시하고 실행 결과를 저장합니다.
11. 사용자가 대화창 하단에 의견을 입력하면 기본 2명, 최대 3명의 Agent가 답하고 Synthesizer Agent가 현재까지의 중간 결론을 갱신합니다.

## UI Highlights

- 라운드별 토론 흐름 표시: 준비 단계, 오프닝, 첫 의견, 상호 응답, 비판 검토, 최종 종합
- 발언별 카드 UI: 누가 말했는지, 어떤 단계인지, 몇 라운드인지 명확히 표시
- 요약/전문 보기: 기본 화면에서는 발언 요약을 보여주고, 클릭하면 전체 발언을 확인
- 대화형 사용자 개입: 새 토론과 저장된 토론 모두에서 사용자가 의견을 추가하고 Agent 응답을 이어붙임
- 단체 대화방 감각: 기본 5명의 Agent가 대화방에 있고, 한 번의 사용자 입력에는 기본 2명, 최대 3명만 응답
- 데포르메 페르소나 이미지와 토론 네트워크 시각화
- LLM API 실패 시에도 로컬 폴백 응답으로 데모 지속

## Setup

```bash
cd persona-graph
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 LLM API 키를 설정합니다.

```bash
OPENAI_API_KEY=your_api_key_here
PERSONA_GRAPH_MODEL=gpt-5.4-mini
```

`OPENAI_BASE_URL`을 설정하면 OpenAI-compatible provider도 사용할 수 있습니다.

API 키가 없거나 호출이 실패하면 로컬 폴백 응답으로 전체 워크플로가 계속 진행됩니다.

## Run API

```bash
cd persona-graph
uvicorn app.main:app --reload --port 8000
```

API 문서:

- http://localhost:8000/docs

예시 요청:

```bash
curl -X POST http://localhost:8000/solve \
  -H "Content-Type: application/json" \
  -d '{
    "problem": "2주 안에 보여줄 수 있는 AI 프로젝트 MVP를 정해야 한다.",
    "persona_count": 5,
    "debate_rounds": 1,
    "use_llm": true
  }'
```

요청 필드:

- `problem`: 해결할 문제
- `persona_count`: 생성할 페르소나 수, 3~5
- `debate_rounds`: 상호 응답 라운드 수, 1~3
- `use_llm`: LLM API 사용 여부
- `model`: 사용할 모델명
- `temperature`: 응답 다양성

사용자 의견 이어붙이기:

```bash
curl -X POST http://localhost:8000/runs/<run_id>/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "나는 비용보다 발표 임팩트가 더 중요하다고 봐.",
    "max_agents": 2,
    "use_llm": true
  }'
```

이어붙이기 요청 필드:

- `content`: 사용자가 대화창에 추가할 의견
- `max_agents`: 이번 턴에 답할 Agent 수, 1~3, 기본값 2
- `use_llm`: LLM API 사용 여부
- `model`: 사용할 모델명
- `temperature`: 응답 다양성

저장된 실행 목록:

```bash
curl http://localhost:8000/runs
```

특정 실행 불러오기:

```bash
curl http://localhost:8000/runs/<run_id>
```

## Run UI

```bash
cd persona-graph
streamlit run ui/streamlit_app.py
```

Streamlit 기본 주소:

- http://localhost:8501

UI는 `새 토론 실행` 탭과 `저장된 토론 보기` 탭으로 구성됩니다. 새 토론은 실행 후 `data/runs/`에 JSON으로 저장됩니다. 토론 결과가 표시된 뒤에는 하단 입력창에서 의견을 추가해 같은 `run_id`의 대화를 이어갈 수 있습니다.

## Project Structure

```text
persona-graph/
  app/
    main.py
    agents/
      persona_generator.py
      moderator.py
      specialist.py
      critic.py
      synthesizer.py
      evaluator.py
      supervisor.py
    llm.py
    characters.py
    schemas.py
    storage.py
    workflow.py
  ui/
    streamlit_app.py
  assets/
    hero/
      personagraph-agent-network.png
    personas/
      persona-deformed-sheet.png
      nori.png
      orbit.png
      ...
    characters/
      sallycore-companion.png
  data/
    runs/
  docs/
    character_design.md
    project_brief.md
    demo_scenarios.md
  README.md
```

## Next Milestones

- 대표 샘플 3개로 토론 품질과 요약 품질 비교
- 일반 LLM 답변 vs PersonaGraph 토론 답변 비교 모드
- 발표용 스크린샷/GIF 추가
- 토론 결과를 Markdown 또는 PDF로 내보내기
- 라운드별 평가 지표와 에이전트별 기여도 표시
- Moderator 기반 동적 응답자 선택
