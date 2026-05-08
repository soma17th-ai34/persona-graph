# UI Implementation Tasks

## Scope

이번 작업의 원칙은 **UI-only**다. [ui/streamlit_app.py](../../ui/streamlit_app.py) 안에서 화면 구조, 렌더링, 세션 상태, CSS만 조정한다.

절대 수정하지 않는 영역:

- `app/agents/`
- `app/workflow.py`
- `app/schemas.py`
- `app/storage.py`
- `app/main.py`
- 저장 JSON 포맷
- API request/response schema

백엔드를 바꿔야만 가능한 요구는 구현 범위에서 제외한다. 대신 UI에서 파생 렌더링하거나, 현재 세션 안에서만 유지하는 방식으로 처리한다.

## Feasibility Matrix

| Requirement | UI-only | 판단 |
| --- | --- | --- |
| ChatGPT/Gemini형 채팅 레이아웃 | 가능 | Streamlit + 커스텀 HTML/CSS로 구현 가능 |
| 접고 펼 수 있는 레프트 사이드바 | 가능 | `st.sidebar` 기본 접힘 기능 활용 |
| 채팅 내역 표시 | 가능 | `list_runs()` / `load_run()` 사용 |
| 헤더 좌측 브랜드명만 표시 | 가능 | 기존 히어로 제거 후 커스텀 헤더 |
| 우측 실행 설정 버튼 + 모달 | 가능 | `st.dialog` 사용 |
| 빈 상태 중앙 질문 | 가능 | 세션에 대화가 없을 때 별도 empty state 렌더 |
| 샘플 시나리오 | 가능 | 기존 `SAMPLE_PROBLEMS` 재사용 |
| 사용자 우측 / Agent 좌측 버블 | 가능 | 메시지 stage 기준으로 정렬 |
| 페르소나별 버블 테두리 | 가능 | `character.accent_color` 또는 캐릭터 border token 사용 |
| 현재 누가 의견 내는 중 표시 | 가능 | 기존 stream event `agent_started` 사용 |
| 페르소나 첫 인사 버블 | 가능 | `response.personas`에서 UI-only로 파생 렌더. JSON에는 저장하지 않음 |
| 첫 입력 후 설정 확인 카드 | 가능 | `st.session_state` 상태 머신으로 구현 |
| 토론 때마다 묻기 / 기본값 사용 | 가능 | 현재 Streamlit 세션 안에서만 유지. 영구 저장은 하지 않음 |
| 마지막 채팅 자동 스크롤 | 부분 가능 | JS 삽입으로 가능하지만 Streamlit DOM 변경에 취약 |
| ChatGPT 디자인 시스템 그대로 적용 | 불가 | 비공개/외부 서비스 토큰 복제 대신 유사한 자체 토큰으로 재해석 |

## Session State Contract

UI-only 구현은 Streamlit session state만 사용한다.

| Key | Type | Purpose |
| --- | --- | --- |
| `pg_chat_mode` | `str` | `empty`, `configuring`, `streaming`, `completed`, `streaming_followup` 중 하나 |
| `pg_current_response` | `SolveResponse | None` | 현재 화면에 표시할 실행 결과 |
| `pg_current_run_id` | `str | None` | 사이드바에서 선택한 저장 run |
| `pg_draft_problem` | `str` | 입력창 draft |
| `pg_pending_problem` | `str | None` | 설정 확인 대기 중인 첫 문제 |
| `pg_settings` | `dict` | 참여 Agent 수, 토론 깊이, 후속 답변 Agent 수, 모델 설정 |
| `pg_settings_policy` | `str` | `ask_each_time` 또는 `use_session_default` |
| `pg_show_settings_dialog` | `bool` | 실행 설정 모달 표시 여부 |
| `pg_stream_messages` | `list` | streaming 중 UI에 임시로 보여줄 메시지 |
| `pg_stream_personas` | `list` | streaming 중 UI에 임시로 보여줄 페르소나 |
| `pg_active_agent` | `dict | None` | 현재 발화 준비 중인 Agent 표시 |

주의: 이 값들은 앱 재시작 후 유지하지 않는다. 영구 저장이 필요한 기능은 UI-only 범위 밖이다.

## State Model

```text
empty
  사용자가 문제 입력
  -> configuring

configuring
  설정 카드 노출
  사용자가 "이 설정으로 시작"
  -> streaming

streaming
  personas_ready, agent_started, agent_message 이벤트 렌더
  final_response 수신
  -> completed

completed
  저장된 run 로드 가능
  사용자가 후속 의견 입력
  -> streaming_followup

streaming_followup
  user message, selected agent replies, synthesis 이벤트 렌더
  final_response 수신
  -> completed
```

## Existing Function Mapping

| Existing | Action | New/Replacement |
| --- | --- | --- |
| `render_app_header` | 대체 | `render_chat_header` |
| `render_start_cta` | 대체 | `render_empty_state` |
| `render_response` | 축소/대체 | `render_chat_thread` + `render_chat_composer` |
| `render_conversation_room` | 대체 | `render_chat_thread` |
| `render_live_stream_panel` | 재사용/수정 | `render_streaming_chat_thread` |
| `render_live_chat_message` | 수정 | `render_chat_bubble` |
| `render_typing_indicator` | 수정 | `render_active_agent_status` |
| `render_discussion_input` | 대체 | `render_chat_composer` |
| `render_agent_network` | 숨김 | v1 채팅 UI에서는 렌더하지 않음 |
| `render_selected_agent_info` | 숨김 | intro bubble과 메시지 메타로 대체 |
| 하단 `st.sidebar` 실행 설정 | 대체 | history sidebar + settings dialog |
| 하단 `st.radio` 탭 | 제거 | sidebar history로 저장 run 접근 |

## Phase 0: Guardrails / Preparation

### Goal

구현 전에 UI-only 경계를 고정하고, 기존 앱의 동작을 보존할 기준점을 만든다.

### Tasks

- [ ] `git status --short`로 작업 전 변경사항을 확인한다.
- [ ] 변경 대상 파일을 [ui/streamlit_app.py](../../ui/streamlit_app.py)로 제한한다.
- [ ] 문서만 필요하면 `docs/tasks/ui_kyj/`만 변경한다.
- [ ] `app/` 하위 파일은 읽기만 하고 수정하지 않는다.
- [ ] 기존 저장 run이 있는지 `data/runs/*.json` 존재 여부를 확인한다.
- [ ] Streamlit 버전이 `st.dialog`를 지원하는지 확인한다.

### Acceptance

- 작업자가 수정 금지 파일을 명확히 알고 있다.
- 구현 전 현재 앱이 `streamlit run ui/streamlit_app.py`로 실행 가능한 상태다.

### Risks

- 기존 UI가 큰 단일 파일에 몰려 있어 작은 변경도 영향 범위가 커질 수 있다.
- 기존 함수명을 모두 제거하면 회귀가 커지므로, 우선은 숨김/대체 방식으로 접근한다.

## Phase 1: Shell / Layout

### Goal

현재 히어로/탭/결과 누적형 화면을 채팅 제품 shell로 바꾼다.

### Files

- Modify: [ui/streamlit_app.py](../../ui/streamlit_app.py)
- Do not modify: `app/**`

### Detailed Tasks

#### 1.1 CSS 토큰 주입

- [ ] `render_chat_styles()` 또는 기존 style block 안에 CSS variable을 추가한다.
- [ ] [design_tokens.md](./design_tokens.md)의 기본 색상/spacing/radius/layout token을 반영한다.
- [ ] 캐릭터 border token을 CSS variable로 추가한다.
- [ ] 기존 `.pg-hero`, `.pg-network` 스타일은 즉시 삭제하지 말고 v1에서는 사용하지 않는 상태로 둔다.

Acceptance:

- CSS variable이 한 곳에서 선언된다.
- 사용자/Agent/system bubble에서 동일 토큰을 참조할 수 있다.

#### 1.2 Header 재구성

- [ ] `render_app_header()`를 `render_chat_header()`로 대체하거나 내부 동작을 바꾼다.
- [ ] 좌측에는 `PersonaGraph` 브랜드명만 둔다.
- [ ] 헤더에서 큰 배너 이미지와 긴 설명 문구를 제거한다.
- [ ] 우측에는 API 상태 pill과 `실행 설정` 버튼을 둔다.
- [ ] 버튼 클릭 시 `pg_show_settings_dialog = True`로 설정한다.

Acceptance:

- 첫 viewport에서 큰 히어로 이미지가 보이지 않는다.
- 좌측 브랜드는 작고 일관된 위치에 있다.
- `실행 설정`은 헤더 우측에서 접근된다.

#### 1.3 Main layout 구성

- [ ] 하단의 `st.radio(["새 토론 실행", "저장된 토론 보기"])`를 제거한다.
- [ ] 메인 영역을 header, chat body, composer 순서로 렌더한다.
- [ ] 결과가 아래로 계속 누적되는 `result_slot` 중심 구조를 제거한다.
- [ ] `pg_chat_mode`에 따라 empty/configuring/streaming/completed 렌더를 분기한다.

Acceptance:

- 탭 UI가 없다.
- 같은 화면 안에서 새 대화와 저장 대화가 처리된다.
- 실행 결과가 form 아래에 대시보드처럼 쌓이지 않는다.

### Phase 1 Done When

- 사이드바는 아직 단순해도 되고, 메인 화면에 채팅 shell이 보인다.
- 헤더/채팅 body/composer 영역이 명확히 분리된다.

## Phase 2: Sidebar History

### Goal

저장된 토론 보기를 별도 탭이 아니라 레프트 사이드바 history로 옮긴다.

### Files

- Modify: [ui/streamlit_app.py](../../ui/streamlit_app.py)
- Read only: [app/storage.py](../../app/storage.py)

### Detailed Tasks

#### 2.1 Sidebar 구조 변경

- [ ] `with st.sidebar:` 블록을 실행 설정용이 아니라 history용으로 바꾼다.
- [ ] 상단에 `새 대화` 버튼을 둔다.
- [ ] `새 대화` 클릭 시 `pg_current_response`, `pg_current_run_id`, `pg_pending_problem`, `pg_stream_messages`, `pg_stream_personas`, `pg_active_agent`를 초기화한다.
- [ ] `pg_chat_mode`를 `empty`로 바꾼다.

Acceptance:

- 사이드바에서 새 대화를 시작할 수 있다.
- 기존 실행 설정 slider가 사이드바에서 사라진다.

#### 2.2 History list 렌더

- [ ] `list_runs()`로 최근 run 목록을 가져온다.
- [ ] 각 item label은 문제 preview 중심으로 짧게 표시한다.
- [ ] 보조 정보로 날짜, 평균 점수, `LLM`/`Fallback` 상태 중 필요한 것만 작게 표시한다.
- [ ] 긴 문제 preview는 `trim_summary()` 또는 별도 helper로 자른다.

Acceptance:

- `data/runs/*.json` 파일이 있으면 사이드바 목록에 표시된다.
- 목록이 비어 있으면 빈 상태 문구만 표시된다.

#### 2.3 History selection

- [ ] history item 클릭 시 `load_run(run_id)`를 호출한다.
- [ ] 결과를 `pg_current_response`에 넣는다.
- [ ] `pg_current_run_id`를 선택한 run id로 설정한다.
- [ ] `pg_chat_mode`를 `completed`로 바꾼다.
- [ ] 선택된 item은 시각적으로 구분한다.

Acceptance:

- 저장된 run 클릭 시 메인 영역이 해당 대화 thread로 바뀐다.
- 별도 `저장된 토론 보기` 탭이 필요 없다.

### Risks

- Streamlit button list는 rerun마다 상태가 초기화되므로 selected id를 반드시 session state에 저장해야 한다.
- 많은 run이 있을 때 사이드바가 길어질 수 있으므로 30개 limit은 기존 `list_runs()` 기본값을 그대로 쓴다.

## Phase 3: Empty State / Composer / Settings

### Goal

첫 문제 입력과 후속 의견 입력을 같은 채팅 composer로 통합하고, 첫 실행 전 설정 확인 카드를 채팅 안에서 보여준다.

### Detailed Tasks

#### 3.1 Empty State

- [ ] `render_empty_state()`를 만든다.
- [ ] `pg_chat_mode == "empty"`이고 `pg_current_response is None`일 때만 렌더한다.
- [ ] 중앙에 `어떤 문제를 해결하고 싶으신가요?`를 표시한다.
- [ ] 아래에 `SAMPLE_PROBLEMS` 기반 샘플 버튼 3개를 표시한다.
- [ ] 샘플 버튼 클릭 시 `pg_draft_problem` 또는 `st.session_state["problem_text"]`에만 값을 넣고 실행하지 않는다.

Acceptance:

- 대화가 없을 때만 empty state가 보인다.
- 샘플 클릭 후 바로 Agent가 실행되지 않는다.

#### 3.2 Composer 기본 동작

- [ ] `render_chat_composer()`를 만든다.
- [ ] 첫 입력과 후속 입력이 같은 함수에서 처리된다.
- [ ] 입력값은 `pg_draft_problem`에 연결한다.
- [ ] submit 시 현재 mode에 따라 분기한다.
- [ ] `empty`에서 submit하면 `pg_pending_problem`에 저장하고 `pg_chat_mode = "configuring"`으로 바꾼다.
- [ ] `completed`에서 submit하면 follow-up 입력으로 간주한다.
- [ ] 빈 문자열 submit은 warning만 표시한다.

Acceptance:

- 첫 문제 입력 후 곧바로 `solve_problem_stream()`이 호출되지 않는다.
- 완료된 대화에서 입력하면 후속 의견으로 처리된다.

#### 3.3 Settings defaults

- [ ] `default_settings()` helper를 만든다.
- [ ] 기본값은 현재 앱과 동일하게 유지한다.
  - 참여 Agent 수: `3`
  - 토론 깊이: `1`
  - 후속 답변 Agent 수: `2`
  - 실제 AI 응답 사용: `True`
  - 모델명: `PERSONA_GRAPH_MODEL` env 또는 `gpt-5.4-mini`
  - 답변 변동성: `0.35`
- [ ] `pg_settings`가 없으면 `default_settings()`로 초기화한다.

Acceptance:

- 기존 앱과 동일한 기본 실행값이 유지된다.

#### 3.4 Settings Dialog

- [ ] `render_settings_dialog()`를 만든다.
- [ ] `st.dialog("실행 설정")`를 사용한다.
- [ ] 설정 항목마다 label과 설명을 함께 표시한다.
- [ ] 저장 버튼 클릭 시 `pg_settings`를 업데이트하고 dialog를 닫는다.
- [ ] 취소/닫기 시 기존 설정을 유지한다.

Acceptance:

- 헤더 버튼으로 실행 설정을 열 수 있다.
- 설정 변경 후 첫 실행/후속 실행에 반영된다.

#### 3.5 Inline Configuration Card

- [ ] `render_configuration_card()`를 만든다.
- [ ] `pg_chat_mode == "configuring"`일 때 채팅 영역 안에 표시한다.
- [ ] 사용자가 입력한 문제를 카드 상단에 요약해서 보여준다.
- [ ] 설정 항목을 카드 안에서 수정할 수 있게 한다.
- [ ] `이 설정으로 시작` 버튼을 제공한다.
- [ ] `이번 세션에서는 기본값으로 바로 시작` 옵션을 제공한다.
- [ ] `토론 때마다 묻기` 옵션을 제공한다.
- [ ] 옵션은 `pg_settings_policy`에만 저장한다.
- [ ] `이 설정으로 시작` 클릭 시 `pg_chat_mode = "streaming"`으로 바꾸고 실행을 시작한다.

Acceptance:

- 첫 문제 입력 후 설정 카드가 먼저 보인다.
- 사용자가 설정 의미를 화면 안에서 이해할 수 있다.
- 설정 정책은 현재 Streamlit 세션 안에서만 유지된다.

### Constraints

- 설정 정책은 파일/JSON/API/backend에 저장하지 않는다.
- `pg_settings_policy == "use_session_default"`일 때만 같은 Streamlit 세션에서 설정 카드를 건너뛸 수 있다.

## Phase 4: Chat Rendering

### Goal

결과를 대시보드/카드 묶음이 아니라 일반 채팅 thread로 렌더한다.

### Detailed Tasks

#### 4.1 Message normalization

- [ ] `chat_thread_items(response)` helper를 만든다.
- [ ] `response.personas`에서 intro bubble item을 생성한다.
- [ ] `response.messages`에서 실제 message item을 생성한다.
- [ ] `persona_generation` stage는 기본 채팅 thread에서 숨기거나 system item으로 축약한다.
- [ ] `moderator`, `critic`, `synthesizer`는 system/agent 왼쪽 메시지로 표시한다.
- [ ] `user` stage는 오른쪽 메시지로 표시한다.

Acceptance:

- 저장된 run을 열어도 intro bubble이 재구성된다.
- JSON 저장 내용은 바뀌지 않는다.

#### 4.2 Bubble renderer

- [ ] `render_chat_bubble(item, personas_by_id)`를 만든다.
- [ ] 사용자 메시지는 오른쪽 정렬, max-width `72%`.
- [ ] Agent 메시지는 왼쪽 정렬, avatar + bubble.
- [ ] Agent bubble에는 `character.id` 기반 class를 붙인다.
- [ ] `character.accent_color` 또는 persona border token으로 왼쪽 border를 표시한다.
- [ ] bubble 안에는 이름, 단계 label, 본문을 표시한다.
- [ ] markdown content는 기존 `render_message_content()`를 재사용한다.

Acceptance:

- 사용자/Agent 방향이 명확히 다르다.
- 페르소나별 테두리 차이가 보인다.
- 긴 텍스트가 bubble 밖으로 넘치지 않는다.

#### 4.3 Persona intro bubble

- [ ] intro bubble 문구 helper를 만든다.
- [ ] 문구 구조:
  - `안녕하세요. 저는 {persona.name}입니다.`
  - `{persona.role}로 도와드릴게요.`
  - `{persona.perspective}`는 두 번째 줄 또는 meta로 축약 표시한다.
- [ ] intro bubble은 `source = "ui_derived"` 메타로 내부 item에만 표시한다.
- [ ] intro bubble은 `response.messages`에 append하지 않는다.

Acceptance:

- 페르소나 상세 expander 없이도 각 Agent의 역할을 알 수 있다.
- 저장 JSON에 intro message가 추가되지 않는다.

#### 4.4 Remove dashboard-only sections from main flow

- [ ] `render_agent_network()`는 v1 main thread에서 호출하지 않는다.
- [ ] `render_selected_agent_info()`는 v1 main thread에서 호출하지 않는다.
- [ ] `Agent 상세 정보` expander를 main flow에서 제거한다.
- [ ] `실행 정보 보기`는 header/settings/debug 영역으로 축소하거나 숨긴다.
- [ ] `평가 요약`은 `synthesizer` 이후 system message로 표시하거나 v1에서는 접어둔다.

Acceptance:

- 채팅 thread 중간에 roster/detail dashboard가 끼지 않는다.
- 사용자는 thread만 따라가도 대화 흐름을 이해할 수 있다.

## Phase 5: Streaming / Follow-up / Auto Scroll

### Goal

실시간 생성 흐름과 후속 의견 입력을 채팅 thread 안에서 자연스럽게 보이게 한다.

### Detailed Tasks

#### 5.1 Streaming state renderer

- [ ] `render_streaming_chat_thread()`를 만든다.
- [ ] `consume_live_stream()`의 placeholder 렌더링을 새 chat thread renderer로 바꾼다.
- [ ] `personas_ready` 이벤트 수신 시 `pg_stream_personas`를 업데이트한다.
- [ ] `agent_started` 이벤트 수신 시 `pg_active_agent`를 업데이트한다.
- [ ] `agent_message` 이벤트 수신 시 `pg_stream_messages`에 append한다.
- [ ] `final_response` 이벤트 수신 시 `pg_current_response`를 저장하고 `pg_chat_mode = "completed"`로 바꾼다.

Acceptance:

- streaming 중에도 intro bubble, 기존 메시지, active status가 한 thread에 보인다.
- 전체 페이지 spinner에 의존하지 않는다.

#### 5.2 Active agent status

- [ ] `render_active_agent_status(active_agent, personas_by_id)`를 만든다.
- [ ] 문구는 `{agent_name}가 의견을 정리 중입니다...`로 통일한다.
- [ ] avatar가 있으면 표시한다.
- [ ] `persona_generation` 단계에서는 `페르소나를 구성하고 있습니다...`로 표시한다.

Acceptance:

- 답변 생성이 길어도 현재 누가 말할 차례인지 보인다.

#### 5.3 Follow-up flow

- [ ] `completed` 상태에서 composer submit 시 `continue_discussion_stream()`을 호출한다.
- [ ] follow-up 중에는 `pg_chat_mode = "streaming_followup"`으로 둔다.
- [ ] 사용자 입력 메시지는 즉시 오른쪽 bubble로 표시한다.
- [ ] Agent 응답과 synthesis는 기존 streaming renderer로 이어 붙인다.
- [ ] final_response 수신 시 `save_run(updated)` 결과를 `pg_current_response`로 교체한다.

Acceptance:

- 후속 의견이 같은 thread 안에서 이어진다.
- 같은 run이 업데이트되어 sidebar history에서 다시 열 수 있다.

#### 5.4 Auto scroll

- [ ] `scroll_chat_to_bottom()` helper를 만든다.
- [ ] 채팅 하단에 anchor element를 렌더한다.
- [ ] 메시지 렌더 후 `components.html()`로 JS를 실행한다.
- [ ] 스크롤 대상이 없으면 조용히 실패하게 한다.
- [ ] 자동 스크롤 실패 시 사용자가 수동 스크롤 가능해야 한다.

Acceptance:

- 새 메시지가 추가될 때 마지막 메시지 쪽으로 내려간다.
- JS 실패가 앱 에러로 노출되지 않는다.

### Constraints

- 자동 스크롤은 best effort 기능이다.
- Streamlit DOM이 바뀌면 스크롤 보조 JS가 실패할 수 있다.
- 실패해도 입력, 저장, 렌더링은 정상 동작해야 한다.

## Phase 6: Cleanup / QA

### Goal

불필요한 대시보드 UI를 숨기고, 새 채팅 UI의 핵심 플로우를 검증한다.

### Detailed Tasks

#### 6.1 Remove old entry flow

- [ ] 하단 `view = st.radio(...)` 탭 구조를 제거한다.
- [ ] `새 토론 실행` / `저장된 토론 보기` 분기를 제거한다.
- [ ] 기존 sidebar 실행 설정 slider를 제거한다.
- [ ] `render_response()`가 main entry에서 직접 호출되지 않도록 한다.

Acceptance:

- 메인 화면에 탭 UI가 없다.
- 저장된 토론은 sidebar history에서만 접근한다.

#### 6.2 Keep old helpers only if still used

- [ ] `render_message_content()`, `message_avatar()`, `chat_stage_label()` 같은 공용 helper는 재사용한다.
- [ ] `render_message_timeline()` 등 새 UI에서 쓰지 않는 함수는 즉시 삭제하지 않아도 된다.
- [ ] 단, main entry에서 호출되지 않게 한다.

Acceptance:

- 사용하지 않는 큰 UI 블록이 화면에 나타나지 않는다.
- 코드 삭제로 인한 회귀를 최소화한다.

#### 6.3 Verification commands

- [ ] Python syntax check:

```bash
.venv/bin/python -m py_compile ui/streamlit_app.py
```

- [ ] Streamlit 실행:

```bash
.venv/bin/streamlit run ui/streamlit_app.py
```

- [ ] 서버 응답 확인:

```bash
curl -I http://127.0.0.1:8501/
```

### Manual QA Checklist

- [ ] API 키 없는 fallback 모드에서 첫 대화 생성
- [ ] 샘플 시나리오 클릭 시 입력창만 채워짐
- [ ] 첫 문제 submit 후 설정 카드 표시
- [ ] 설정 카드에서 Agent 수/토론 깊이 변경
- [ ] `이 설정으로 시작` 후 streaming thread 표시
- [ ] 페르소나 intro bubble 표시
- [ ] 현재 발화 Agent 상태 표시
- [ ] 사용자 메시지는 오른쪽 bubble
- [ ] Agent 메시지는 왼쪽 bubble
- [ ] 캐릭터별 border 색상 표시
- [ ] 최종 결과 저장 확인
- [ ] 사이드바에서 저장된 대화 재로드
- [ ] 후속 의견 입력 후 같은 thread에 이어짐
- [ ] 후속 의견 후 같은 run 업데이트
- [ ] 자동 스크롤이 마지막 메시지 근처로 이동
- [ ] 모바일 폭에서 메시지 버블 텍스트가 넘치지 않음

## Implementation Order

1. Phase 0 guardrails 확인
2. CSS token 추가
3. header shell 구현
4. sidebar history 구현
5. session state 초기화 helper 구현
6. empty state 구현
7. composer 구현
8. settings dialog 구현
9. inline configuration card 구현
10. chat item normalization 구현
11. chat bubble renderer 구현
12. persona intro bubble 구현
13. streaming renderer 교체
14. follow-up flow 연결
15. auto scroll 추가
16. old tab/sidebar entry 제거
17. syntax/runtime 검증

## Non-goals

- Agent 생성 방식 변경
- 페르소나 실제 message 저장
- JSON schema 변경
- API endpoint 변경
- 저장 run 영구 설정 추가
- 실제 ChatGPT 비공개 디자인 토큰 복제
