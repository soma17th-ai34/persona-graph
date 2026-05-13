from __future__ import annotations


SEARCH_QUERY_REWRITE_EXAMPLES = """
예시 1
사용자 입력: 저예산으로 Physical AI 프로젝트를 시작하고 싶다. 하드웨어 구매 전에 시뮬레이션과 소프트웨어 MVP로 검증할 방법을 찾아줘.
검색어: ["low budget Physical AI MVP robotics simulation validation", "robotics simulation before hardware purchase MVP", "embodied AI prototype simulator software MVP"]

예시 2
사용자 입력: 요즘 AI agent 프레임워크 추천해줘.
검색어: ["2026 AI agent framework comparison", "LangGraph CrewAI AutoGen comparison 2026", "AI agent framework trends API"]
"""


SYNTHESIS_CANDIDATE_EXAMPLES = """
예시
후보 제목: 가장 작은 검증 루프
후보 답변: 결론은 하드웨어 구매 전에 시뮬레이터와 로그가 남는 소프트웨어 루프를 먼저 만드는 것입니다.
이유는 실제 로봇 없이도 사용자의 의도 파악, 계획 생성, 실패 조건을 검증할 수 있기 때문입니다.
실행은 시나리오 1개, 상태 전이 5개, 성공/실패 로그, 데모 화면 순서로 묶으면 됩니다.
주의할 점은 센서와 이동 제어를 흉내만 내되 실제 기능처럼 과장하지 않는 것입니다.
바로 할 일은 대표 사용자 요청 3개와 실패 케이스 2개를 정해 시뮬레이션 입력으로 고정하는 것입니다.
"""


SYNTHESIS_SELECTION_EXAMPLES = """
예시 선택 기준
- 사용자 질문의 핵심 제약을 가장 직접적으로 반영한 후보를 고릅니다.
- 토론에서 나온 근거 없이 새 주제를 추가한 후보는 낮게 평가합니다.
- 발표 화면에서 바로 읽히는 구체적인 실행 순서를 가진 후보를 높게 평가합니다.
"""
