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
10. FastAPI 백엔드가 토론 실행과 저장을 맡고, Streamlit 프론트엔드는 API 이벤트를 받아 배너, 데포르메 페르소나 캐릭터, 에이전트 토론 네트워크, 대화창형 토론 로그, 최종 결론, 평가 요약을 표시합니다.
11. 사용자가 대화창 하단에 의견을 입력하면 기본 2명, 최대 3명의 Agent가 답하고 Synthesizer Agent가 현재까지의 중간 결론을 갱신합니다.

## UI Highlights

- 라운드별 토론 흐름 표시: 준비 단계, 오프닝, 첫 의견, 상호 응답, 비판 검토, 최종 종합
- 발언별 카드 UI: 누가 말했는지, 어떤 단계인지, 몇 라운드인지 명확히 표시
- 요약/전문 보기: 기본 화면에서는 발언 요약을 보여주고, 클릭하면 전체 발언을 확인
- 대화형 사용자 개입: 새 토론과 저장된 토론 모두에서 사용자가 의견을 추가하고 Agent 응답을 이어붙임
- 단체 대화방 감각: 기본 5명의 Agent가 대화방에 있고, 한 번의 사용자 입력에는 기본 2명, 최대 3명만 응답
- 데포르메 페르소나 이미지와 토론 네트워크 시각화
- 라운드별 검색 활동 카드: 초기 검색, 라운드 검색, 후속 검색이 실제 대화 흐름 위치에 표시
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
UPSTAGE_API_KEY=your_upstage_api_key_here
PERSONA_GRAPH_MODEL=openai:gpt-5.4-mini
PERSONA_GRAPH_AVAILABLE_MODELS=openai:gpt-5.4-mini,upstage:solar-pro3
```

`PERSONA_GRAPH_AVAILABLE_MODELS`는 사용자에게 노출할 모델 목록입니다. API 키는 서버 `.env`에만 두고, 사용자는 이 목록 안에서 모델만 선택합니다.
모델 ID는 `provider:model` 형식을 권장합니다. 현재 기본 provider router는 `openai`와 `upstage`를 지원합니다.

Provider별 기본 설정:

- `openai:*`: `OPENAI_API_KEY`, 선택적으로 `OPENAI_BASE_URL`
- `upstage:*`: `UPSTAGE_API_KEY`, 선택적으로 `UPSTAGE_BASE_URL`, 기본값 `https://api.upstage.ai/v1`

API 키가 없거나 호출이 실패하면 로컬 폴백 응답으로 전체 워크플로가 계속 진행됩니다.

## 검색 설정

검색 모드는 요청마다 `auto`, `always`, `off` 중 하나로 선택할 수 있습니다. 기본값은 `auto`이며, 최신성/추천/비교/가격/메타/API 같은 신호가 있으면 자동으로 검색합니다.
검색은 한 번의 flat query list가 아니라 라운드별 공용 query tree로 동작합니다. 초기 입력 직후, 각 토론 라운드 시작 전, 사용자 후속 발화 직후에 Supervisor가 공용 검색 context를 만들고 모든 Agent가 같은 `research_context`를 공유합니다.

각 검색 pass는 root query 최대 3개를 먼저 검색하고, LLM이 사용 가능하면 각 root 결과를 바탕으로 child query를 최대 3개씩 확장합니다. query당 결과는 최대 3개, 최종 context는 중복 제거 후 최대 18개 snippet으로 제한합니다. LLM이 꺼져 있으면 child 확장은 건너뛰고 root 검색만 수행합니다.

검색 결과가 실제 Agent prompt에 들어간 경우, 저장된 run JSON의 `search_records`에 `phase`, `round_number`, `queries`, `query_tree`, 정리된 검색 context가 남습니다. API 키나 raw HTTP 응답은 저장하지 않습니다.

Tavily API 키가 있으면 Tavily를 우선 사용하고, 없으면 DuckDuckGo HTML 검색 fallback을 사용합니다.

  1. Tavily 패키지 설치(새로운 환경에 세팅하는 경우 requirements.txt 내에 들어있기 때문에 필요 없음)

        pip install tavily-python

  2. Tavily API 키 발급

        https://app.tavily.com 에서 회원가입 후 API 키 발급

  3. .env 파일에 키 추가

        TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx

## 응답 품질 파이프라인

최종 종합 단계에서는 첫 시도에 후보 답변 3개를 만들고, judge가 사용자 의도와 토론 근거에 가장 맞는 후보를 선택합니다.
선택된 후보만 사용자에게 표시되며, 이후 기존 평가/역방향 검증 루프가 품질을 다시 확인합니다.
저장된 run JSON의 `reasoning_records`에는 후보 제목, 후보 미리보기, 선택된 후보 ID, 선택 이유 요약, 점수만 남습니다. 내부 사고과정이나 raw judge 응답은 저장하지 않습니다.
LLM이 꺼져 있거나 API 키가 없으면 이 단계는 `skipped_no_llm`으로 기록되고 기존 로컬 폴백 답변을 사용합니다.

선별 품질 메모리를 쓰고 싶으면 직접 고른 run JSON만 `data/memory_runs/`에 넣습니다. 일반 실행 로그인 `data/runs/`는 테스트/데모 흔적이 섞일 수 있어 품질 메모리에 자동 포함하지 않습니다.
메모리 경로는 `PERSONA_GRAPH_MEMORY_RUNS_DIR`로 바꿀 수 있고, 저장된 응답의 `memory_records`에는 실제 prompt에 넣은 짧은 context만 남습니다.
선별 메모리는 Critic, Synthesizer, reverse verification 단계에서만 사용되며, 개별 페르소나 발화에는 주입하지 않습니다.

## Run API

```bash
cd persona-graph
uvicorn app.main:app --reload --port 8000
```

API 문서:

- http://localhost:8000/docs

사용 가능한 모델 목록:

```bash
curl http://localhost:8000/models
```

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
- `model`: 서버 허용 목록에 있는 모델 ID. 예: `openai:gpt-5.4-mini`, `upstage:solar-pro3`. 비우면 `PERSONA_GRAPH_MODEL` 기본값을 사용합니다.
- `search_mode`: 검색 모드, `auto` | `always` | `off`, 기본값 `auto`
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
- `model`: 서버 허용 목록에 있는 모델 ID. 예: `openai:gpt-5.4-mini`, `upstage:solar-pro3`. 비우면 `PERSONA_GRAPH_MODEL` 기본값을 사용합니다.
- `search_mode`: 검색 모드, `auto` | `always` | `off`, 기본값 `auto`
- `temperature`: 응답 다양성

저장된 실행 목록:

```bash
curl http://localhost:8000/runs
```

특정 실행 불러오기:

```bash
curl http://localhost:8000/runs/<run_id>
```

실시간 이벤트 스트림:

```bash
curl -N -X POST http://localhost:8000/solve/stream \
  -H "Content-Type: application/json" \
  -d '{
    "problem": "2주 안에 보여줄 수 있는 AI 프로젝트 MVP를 정해야 한다.",
    "persona_count": 3,
    "debate_rounds": 1,
    "use_llm": false
  }'
```

## Run Frontend

```bash
cd persona-graph
PERSONA_GRAPH_API_URL=http://127.0.0.1:8000 streamlit run ui/streamlit_app.py
```

Streamlit 기본 주소:

- http://localhost:8501

프론트엔드는 `PERSONA_GRAPH_API_URL`에 설정된 백엔드를 호출합니다. 새 토론과 후속 의견은 백엔드에서 실행되고 `data/runs/`에 JSON으로 저장됩니다. 토론 결과가 표시된 뒤에는 하단 입력창에서 의견을 추가해 같은 `run_id`의 대화를 이어갈 수 있습니다.

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
    model_catalog.py
    prompt_examples.py
    run_memory.py
    characters.py
    schemas.py
    search.py
    storage.py
    terminal_logging.py
    workflow.py
  ui/
    streamlit_app.py
    api_client.py
    streamlit_browser.py
    streamlit_chat.py
    streamlit_common.py
    streamlit_flow.py
    streamlit_header.py
    streamlit_settings.py
    streamlit_sidebar.py
    streamlit_state.py
    streamlit_streaming.py
    streamlit_styles.py
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
