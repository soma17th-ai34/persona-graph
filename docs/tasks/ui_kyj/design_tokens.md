# UI Design Tokens

## 방향

PersonaGraph의 다음 UI는 캐릭터/배너 중심의 데모 화면이 아니라, 사용자가 문제를 입력하고 여러 Agent 응답을 따라가는 채팅 제품 화면을 기준으로 한다. ChatGPT/Gemini 같은 익숙한 LLM 서비스의 정보 구조를 참고하되, 특정 서비스의 토큰을 그대로 복제하지 않고 중립적인 자체 토큰으로 정의한다.

## Principles

- **Chat First**: 화면의 중심은 입력창과 대화 흐름이다. 페르소나 상세 정보는 별도 카드가 아니라 메시지 맥락 안에서 노출한다.
- **Low Chrome**: 장식적 히어로, 큰 배너, 과한 카드 장식을 제거한다.
- **Readable Debate**: Agent가 많아져도 발화 주체, 단계, 상태가 즉시 구분되어야 한다.
- **UI-only First**: 우선은 `ui/streamlit_app.py`만 변경해 구현 가능한 토큰으로 제한한다.

## Color Tokens

| Token | Value | Usage |
| --- | --- | --- |
| `--pg-bg-app` | `#ffffff` | 메인 앱 배경 |
| `--pg-bg-sidebar` | `#f7f7f8` | 레프트 사이드바 배경 |
| `--pg-bg-surface` | `#ffffff` | 헤더, 설정 모달, 기본 패널 |
| `--pg-bg-surface-muted` | `#f4f4f5` | 빈 상태 샘플, 비활성 영역 |
| `--pg-bg-user` | `#f3f4f6` | 사용자 메시지 버블 |
| `--pg-bg-agent` | `#ffffff` | Agent 메시지 버블 |
| `--pg-bg-system` | `#f8fafc` | 설정 카드, 진행 상태 |
| `--pg-text-primary` | `#111827` | 본문 주요 텍스트 |
| `--pg-text-secondary` | `#4b5563` | 설명 텍스트 |
| `--pg-text-muted` | `#6b7280` | 메타, 시간, 보조 정보 |
| `--pg-border-default` | `#e5e7eb` | 기본 구분선 |
| `--pg-border-strong` | `#d1d5db` | 사이드바/입력창 강조선 |
| `--pg-accent` | `#2563eb` | 주요 액션, 포커스 |
| `--pg-accent-soft` | `#eff6ff` | 선택 상태 배경 |
| `--pg-danger` | `#dc2626` | 오류 상태 |
| `--pg-success` | `#16a34a` | 완료 상태 |

## Persona Accent Tokens

페르소나별 차이는 버블 전체 색상이 아니라 좌측 테두리/작은 칩/아바타 링 정도로 제한한다.

| Source | Token | Usage |
| --- | --- | --- |
| `character.accent_color` | `--pg-persona-accent` | Agent 버블 왼쪽 border |
| `character.color` | `--pg-persona-soft` | Agent hover/intro 배경 |
| `character.name` | display value | 아바타 대체 텍스트 |

주의: 여기서 "페르소나별"은 LLM이 생성한 역할 이름이 아니라, UI에 배정된 `character.id` 기준이다. 페르소나 역할은 매번 달라질 수 있고, 캐릭터 풀은 고정이므로 채팅 버블 테두리는 캐릭터 토큰을 기준으로 적용한다.

## Persona Border Tokens

| Character ID | Name | Border Token | Value | Soft Token | Value |
| --- | --- | --- | --- | --- | --- |
| `nori` | 노리 | `--pg-persona-nori-border` | `#F97316` | `--pg-persona-nori-soft` | `#FFF7ED` |
| `orbit` | 오르빗 | `--pg-persona-orbit-border` | `#4F46E5` | `--pg-persona-orbit-soft` | `#EEF2FF` |
| `milmil` | 밀밀 | `--pg-persona-milmil-border` | `#D97706` | `--pg-persona-milmil-soft` | `#FEF3C7` |
| `sori` | 소리 | `--pg-persona-sori-border` | `#E11D48` | `--pg-persona-sori-soft` | `#FFF1F2` |
| `mori` | 모리 | `--pg-persona-mori-border` | `#57534E` | `--pg-persona-mori-soft` | `#F5F5F4` |
| `gyeol` | 결 | `--pg-persona-gyeol-border` | `#7C3AED` | `--pg-persona-gyeol-soft` | `#F5F3FF` |
| `jari` | 자리 | `--pg-persona-jari-border` | `#059669` | `--pg-persona-jari-soft` | `#ECFDF5` |
| `sallycore` | 샐리 | `--pg-persona-sallycore-border` | `#2F80ED` | `--pg-persona-sallycore-soft` | `#EAF6FF` |
| `lumi` | 루미 | `--pg-persona-lumi-border` | `#0891B2` | `--pg-persona-lumi-soft` | `#ECFEFF` |
| `haneul` | 하늘 | `--pg-persona-haneul-border` | `#A855F7` | `--pg-persona-haneul-soft` | `#F5F3FF` |

## Persona Border Application

Agent 버블은 기본 border와 캐릭터 accent rail을 함께 쓴다. 전체 테두리를 강한 색으로 두르면 채팅 목록이 산만해지므로, 기본 상태는 왼쪽 rail만 강조하고 hover/active 상태에서만 전체 border를 살짝 강조한다.

```css
.pg-chat-bubble-agent {
  --pg-persona-border: var(--pg-border-default);
  --pg-persona-soft: var(--pg-bg-agent);

  background: var(--pg-bg-agent);
  border: 1px solid var(--pg-border-default);
  border-left: 3px solid var(--pg-persona-border);
}

.pg-chat-bubble-agent:hover {
  border-color: var(--pg-persona-border);
  background: color-mix(in srgb, var(--pg-persona-soft) 34%, #ffffff);
}

.pg-chat-bubble-agent[data-character="nori"] {
  --pg-persona-border: var(--pg-persona-nori-border);
  --pg-persona-soft: var(--pg-persona-nori-soft);
}

.pg-chat-bubble-agent[data-character="orbit"] {
  --pg-persona-border: var(--pg-persona-orbit-border);
  --pg-persona-soft: var(--pg-persona-orbit-soft);
}
```

Streamlit에서 `data-character` 속성 적용이 번거로우면 class 방식으로 대체한다.

```html
<div class="pg-chat-bubble-agent pg-character-nori">...</div>
```

```css
.pg-character-nori {
  --pg-persona-border: var(--pg-persona-nori-border);
  --pg-persona-soft: var(--pg-persona-nori-soft);
}
```

## Typography Tokens

| Token | Value | Usage |
| --- | --- | --- |
| `--pg-font-sans` | system sans-serif | 전체 UI |
| `--pg-font-size-xs` | `0.75rem` | 메타 정보 |
| `--pg-font-size-sm` | `0.875rem` | 버튼, 칩, 설명 |
| `--pg-font-size-md` | `0.95rem` | 채팅 본문 |
| `--pg-font-size-lg` | `1.125rem` | 빈 상태 보조 헤드라인 |
| `--pg-font-size-xl` | `1.5rem` | 빈 상태 메인 질문 |
| `--pg-line-chat` | `1.55` | 메시지 본문 줄간격 |
| `--pg-weight-regular` | `400` | 본문 |
| `--pg-weight-medium` | `600` | 버튼/메타 강조 |
| `--pg-weight-bold` | `700` | 브랜드/섹션 제목 |

## Spacing Tokens

| Token | Value | Usage |
| --- | --- | --- |
| `--pg-space-1` | `0.25rem` | 작은 gap |
| `--pg-space-2` | `0.5rem` | 칩/메타 간격 |
| `--pg-space-3` | `0.75rem` | 버블 내부 작은 padding |
| `--pg-space-4` | `1rem` | 기본 패널 padding |
| `--pg-space-5` | `1.25rem` | 채팅 row 간격 |
| `--pg-space-6` | `1.5rem` | 섹션 간격 |
| `--pg-space-8` | `2rem` | 빈 상태 상하 여백 |

## Radius Tokens

| Token | Value | Usage |
| --- | --- | --- |
| `--pg-radius-sm` | `6px` | 칩, 작은 버튼 |
| `--pg-radius-md` | `10px` | 입력창, 리스트 item |
| `--pg-radius-lg` | `16px` | 메시지 버블 |
| `--pg-radius-xl` | `20px` | 컴포저 wrapper |
| `--pg-radius-full` | `999px` | 아바타, pill |

## Layout Tokens

| Token | Value | Usage |
| --- | --- | --- |
| `--pg-sidebar-width` | `280px` | 펼친 사이드바 |
| `--pg-sidebar-collapsed` | `56px` | 접힌 사이드바 |
| `--pg-header-height` | `56px` | 상단 헤더 |
| `--pg-chat-max-width` | `780px` | 채팅 메시지 영역 |
| `--pg-composer-max-width` | `820px` | 하단 입력창 영역 |
| `--pg-composer-min-height` | `52px` | 입력창 기본 높이 |
| `--pg-avatar-size` | `36px` | Agent 아바타 |
| `--pg-message-max-width` | `72%` | 메시지 버블 최대 폭 |

## Component Tokens

### Sidebar

- 배경: `--pg-bg-sidebar`
- 너비: `--pg-sidebar-width`
- 채팅 내역 item 높이: `40px`
- 선택된 item 배경: `--pg-bg-surface-muted`
- 접힘 상태는 Streamlit 기본 sidebar 토글을 우선 사용한다.

### Header

- 높이: `--pg-header-height`
- 좌측: `PersonaGraph` 텍스트만 표시
- 우측: API 상태, 실행 설정 버튼
- 구분선: `1px solid --pg-border-default`

### Empty State

- 중앙 질문: `어떤 문제를 해결하고 싶으신가요?`
- 질문 폰트: `--pg-font-size-xl`
- 샘플 시나리오: 작은 pill/card 버튼 3개
- 배너 이미지는 기본 UI에서 제거한다.

### Message Bubble

- 사용자 메시지: 우측 정렬, `--pg-bg-user`
- Agent 메시지: 좌측 정렬, `--pg-bg-agent`, 왼쪽 border에 persona accent 적용
- 시스템/설정 메시지: 중앙 또는 좌측 정렬, `--pg-bg-system`
- 긴 메시지는 전문 펼치기보다 기본 채팅 흐름 안에서 읽히게 한다.

### Composer

- 화면 하단 고정 또는 채팅 컨테이너 하단 배치
- submit 버튼은 아이콘형 또는 짧은 텍스트 버튼
- 첫 입력 후에는 바로 실행하지 않고 설정 확인 카드를 띄울 수 있다.

### Settings Dialog

- 기존 사이드바 설정을 모달로 이동한다.
- 기본 섹션: 참여 Agent 수, 토론 깊이, 후속 답변 Agent 수
- 고급 섹션: 실제 AI 응답 사용, 모델명, 답변 변동성, API 키 상태

## CSS Variable Draft

```css
:root {
  --pg-bg-app: #ffffff;
  --pg-bg-sidebar: #f7f7f8;
  --pg-bg-surface: #ffffff;
  --pg-bg-surface-muted: #f4f4f5;
  --pg-bg-user: #f3f4f6;
  --pg-bg-agent: #ffffff;
  --pg-bg-system: #f8fafc;

  --pg-text-primary: #111827;
  --pg-text-secondary: #4b5563;
  --pg-text-muted: #6b7280;

  --pg-border-default: #e5e7eb;
  --pg-border-strong: #d1d5db;
  --pg-accent: #2563eb;
  --pg-accent-soft: #eff6ff;

  --pg-persona-nori-border: #F97316;
  --pg-persona-nori-soft: #FFF7ED;
  --pg-persona-orbit-border: #4F46E5;
  --pg-persona-orbit-soft: #EEF2FF;
  --pg-persona-milmil-border: #D97706;
  --pg-persona-milmil-soft: #FEF3C7;
  --pg-persona-sori-border: #E11D48;
  --pg-persona-sori-soft: #FFF1F2;
  --pg-persona-mori-border: #57534E;
  --pg-persona-mori-soft: #F5F5F4;
  --pg-persona-gyeol-border: #7C3AED;
  --pg-persona-gyeol-soft: #F5F3FF;
  --pg-persona-jari-border: #059669;
  --pg-persona-jari-soft: #ECFDF5;
  --pg-persona-sallycore-border: #2F80ED;
  --pg-persona-sallycore-soft: #EAF6FF;
  --pg-persona-lumi-border: #0891B2;
  --pg-persona-lumi-soft: #ECFEFF;
  --pg-persona-haneul-border: #A855F7;
  --pg-persona-haneul-soft: #F5F3FF;

  --pg-sidebar-width: 280px;
  --pg-sidebar-collapsed: 56px;
  --pg-header-height: 56px;
  --pg-chat-max-width: 780px;
  --pg-composer-max-width: 820px;

  --pg-radius-sm: 6px;
  --pg-radius-md: 10px;
  --pg-radius-lg: 16px;
  --pg-radius-xl: 20px;
  --pg-radius-full: 999px;
}
```
