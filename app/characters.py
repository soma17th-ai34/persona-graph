import random

from app.schemas import Character, Persona


CHARACTER_POOL = [
    Character(
        id="lumi",
        name="루미",
        archetype="차분한 안내자",
        tagline="복잡한 문제를 작은 빛으로 나누어 보여줍니다.",
        visual="둥근 흰색 바디에 은은한 하늘색 라이트가 들어오는 작은 데스크 오브제",
        speech_style="부드럽지만 결론을 먼저 말하고, 다음 행동을 짧게 제안합니다.",
        color="#EAF6FF",
        accent_color="#2F80ED",
        symbol="빛",
    ),
    Character(
        id="naru",
        name="나루",
        archetype="MVP 정리자",
        tagline="큰 아이디어를 발표 가능한 첫 버전으로 줄입니다.",
        visual="작은 노트 패널과 방향 표시등을 가진 미니 스테이션 형태",
        speech_style="현실적인 범위 조절과 우선순위를 단호하게 말합니다.",
        color="#F1F8E9",
        accent_color="#43A047",
        symbol="나침반",
    ),
    Character(
        id="orbit",
        name="오르빗",
        archetype="시스템 설계자",
        tagline="흐름, 상태, 실패 지점을 안정적인 궤도로 정리합니다.",
        visual="회로 패턴이 얇게 흐르는 짙은 남색 코어와 작은 상태등",
        speech_style="구조, 의존성, 테스트 기준을 차근차근 짚습니다.",
        color="#EEF2FF",
        accent_color="#4F46E5",
        symbol="궤도",
    ),
    Character(
        id="mori",
        name="모리",
        archetype="비판적 관찰자",
        tagline="놓친 가정과 숨은 리스크를 조용히 찾아냅니다.",
        visual="작은 렌즈와 체크 표시등이 있는 무광 회색 분석 모듈",
        speech_style="감정적으로 몰아붙이지 않고, 근거와 위험을 분리해 말합니다.",
        color="#F5F5F4",
        accent_color="#57534E",
        symbol="렌즈",
    ),
    Character(
        id="sori",
        name="소리",
        archetype="발표 연출가",
        tagline="기술 결과를 사람들이 기억하는 장면으로 바꿉니다.",
        visual="작은 스피커 링과 화면 없는 표정 라이트를 가진 발표용 오브제",
        speech_style="청중이 보는 순서, 첫 장면, 마지막 한 문장을 중요하게 봅니다.",
        color="#FFF1F2",
        accent_color="#E11D48",
        symbol="파형",
    ),
    Character(
        id="gyeol",
        name="결",
        archetype="종합 설계자",
        tagline="서로 다른 의견을 하나의 실행 계획으로 묶습니다.",
        visual="얇은 레이어가 겹쳐진 투명한 큐브 형태의 사고 정리 장치",
        speech_style="충돌한 의견을 정리하고 선택한 이유를 분명히 남깁니다.",
        color="#F7F0FF",
        accent_color="#7C3AED",
        symbol="결정",
    ),
    Character(
        id="dami",
        name="다미",
        archetype="사용자 공감가",
        tagline="기능보다 사용자가 느끼는 순간을 먼저 봅니다.",
        visual="손바닥 크기의 부드러운 흰색 쉘과 따뜻한 살구색 표시등",
        speech_style="사용자 경험, 감정선, 첫 인상을 생활 언어로 풀어냅니다.",
        color="#FFF7ED",
        accent_color="#F97316",
        symbol="온기",
    ),
    Character(
        id="juno",
        name="주노",
        archetype="실험 설계자",
        tagline="좋은 아이디어를 검증 가능한 실험으로 바꿉니다.",
        visual="작은 실험대처럼 보이는 모듈형 받침과 초록색 진행 표시등",
        speech_style="가설, 측정 지표, 실패 기준을 명확히 나눠 말합니다.",
        color="#ECFDF5",
        accent_color="#059669",
        symbol="실험",
    ),
]


def assign_characters(personas: list[Persona]) -> list[Persona]:
    if not personas:
        return []

    if len(personas) <= len(CHARACTER_POOL):
        characters = random.sample(CHARACTER_POOL, len(personas))
    else:
        characters = [random.choice(CHARACTER_POOL) for _ in personas]

    return [
        persona.model_copy(update={"character": character})
        for persona, character in zip(personas, characters)
    ]
