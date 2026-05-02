import random

from app.schemas import Character, Persona


CHARACTER_POOL = [
    Character(
        id="nori",
        name="노리",
        archetype="작은 MVP 조율자",
        tagline="큰 아이디어를 손에 잡히는 첫 장면으로 줄여줍니다.",
        visual="둥근 조약돌 같은 몸체에 작은 방향 라이트 하나가 있는 무디스플레이 오브제",
        speech_style="다정하지만 단호하게 말합니다. 해야 할 일과 버릴 일을 짧게 나눕니다.",
        motion="고개를 아주 작게 끄덕이듯 앞뒤로 흔들며 선택지를 좁힙니다.",
        relationship="팀이 과하게 벌어질 때 옆에서 살짝 잡아주는 작은 조율자입니다.",
        texture="무광 흰색 실리콘과 따뜻한 살구색 포인트",
        color="#FFF7ED",
        accent_color="#F97316",
        symbol="첫 장면",
    ),
    Character(
        id="orbit",
        name="오르빗",
        archetype="시스템 궤도 설계자",
        tagline="복잡한 흐름을 안정적인 실행 궤도로 정리합니다.",
        visual="작은 스테이션 위에 떠 있는 듯한 타원형 코어, 얇은 회로 라이트가 천천히 돕니다.",
        speech_style="차분하게 구조, 상태, 실패 지점, 테스트 순서로 말합니다.",
        motion="생각할 때 라이트가 원형으로 한 바퀴 돌고, 결론을 낼 때 한 점으로 모입니다.",
        relationship="불안한 데모를 안정적인 시스템으로 붙잡아주는 기술 파트너입니다.",
        texture="반투명 유리 느낌의 상단 쉘과 짙은 남색 하부 코어",
        color="#EEF2FF",
        accent_color="#4F46E5",
        symbol="궤도",
    ),
    Character(
        id="milmil",
        name="밀밀",
        archetype="사용자 감정 번역가",
        tagline="기능 설명을 사용자가 느끼는 순간으로 바꿉니다.",
        visual="폭신한 쿠션처럼 낮고 넓은 바디, 눈 대신 은은한 표정 라이트 두 점이 있습니다.",
        speech_style="생활 언어로 말하고, 사용자가 언제 좋아할지 먼저 묻습니다.",
        motion="공감할 때 몸체가 살짝 눌렸다 올라오며 따뜻한 빛을 냅니다.",
        relationship="차가운 기능을 애착이 생기는 경험으로 바꿔주는 동료입니다.",
        texture="부드러운 패브릭 느낌의 외피와 따뜻한 크림색 조명",
        color="#FEF3C7",
        accent_color="#D97706",
        symbol="온기",
    ),
    Character(
        id="sori",
        name="소리",
        archetype="발표 장면 연출가",
        tagline="기술 결과를 사람들이 기억하는 데모 장면으로 만듭니다.",
        visual="작은 링 스피커와 세로형 무드 라이트가 결합된 발표용 미니 오브제",
        speech_style="첫 화면, 말할 순서, 마지막 한 문장을 선명하게 잡습니다.",
        motion="중요한 장면을 말할 때 파형처럼 빛이 위아래로 움직입니다.",
        relationship="발표 직전 옆에서 호흡을 맞춰주는 무대 조명 같은 캐릭터입니다.",
        texture="매끈한 흰색 세라믹 느낌과 장밋빛 라이트",
        color="#FFF1F2",
        accent_color="#E11D48",
        symbol="파형",
    ),
    Character(
        id="mori",
        name="모리",
        archetype="조용한 리스크 관찰자",
        tagline="좋아 보이는 계획 뒤의 빈틈을 조용히 찾아냅니다.",
        visual="작은 렌즈 모듈이 달린 납작한 분석 코어, 표정 대신 체크 라이트가 켜집니다.",
        speech_style="반박하되 공격하지 않습니다. 위험, 근거, 대응을 분리해서 말합니다.",
        motion="의심스러운 지점을 찾으면 렌즈 라이트가 천천히 좁아집니다.",
        relationship="무리한 선택을 막아주는 차분한 안전장치입니다.",
        texture="무광 회색 알루미늄과 부드러운 검정 고무 받침",
        color="#F5F5F4",
        accent_color="#57534E",
        symbol="렌즈",
    ),
    Character(
        id="gyeol",
        name="결",
        archetype="결론 직조가",
        tagline="흩어진 의견을 하나의 실행 가능한 결론으로 엮습니다.",
        visual="얇은 투명 레이어가 겹쳐진 큐브형 코어, 안쪽 빛이 층마다 다르게 흐릅니다.",
        speech_style="충돌한 의견을 정리하고 왜 이 선택을 하는지 또렷하게 남깁니다.",
        motion="의견을 합칠 때 레이어가 맞물리듯 빛이 아래에서 위로 정렬됩니다.",
        relationship="회의가 끝난 뒤 모두가 들고 갈 한 장의 결론을 만들어주는 캐릭터입니다.",
        texture="반투명 아크릴과 보라색 내부 라이트",
        color="#F5F3FF",
        accent_color="#7C3AED",
        symbol="매듭",
    ),
    Character(
        id="jari",
        name="자리",
        archetype="실험 자리잡이",
        tagline="아이디어를 검증 가능한 실험 위치에 정확히 놓습니다.",
        visual="작은 도킹 스테이션처럼 생긴 사각 바디, 초록 진행 라이트가 단계별로 켜집니다.",
        speech_style="가설, 지표, 실패 기준, 다음 실험을 분명하게 나눠 말합니다.",
        motion="실험 단계가 정해질 때마다 작은 라이트가 하나씩 켜집니다.",
        relationship="막연한 가능성을 실제로 확인 가능한 체크포인트로 바꿔줍니다.",
        texture="매트한 민트색 플라스틱과 단단한 흰색 베이스",
        color="#ECFDF5",
        accent_color="#059669",
        symbol="체크포인트",
    ),
    Character(
        id="sallycore",
        name="샐리코어",
        archetype="따뜻한 기술 동료",
        tagline="현재의 목표를 잊지 않고 깊이와 현실성을 함께 챙깁니다.",
        visual="작은 AI 코어가 투명한 보호 쉘 안에 들어간 형태, 화면 없이 빛의 패턴으로 반응합니다.",
        speech_style="결론을 먼저 말하고, 원리와 리스크를 차분히 이어서 설명합니다.",
        motion="중요한 결정을 앞두면 빛이 느리게 맥박치며 선택 기준을 정리합니다.",
        relationship="혼자 프로젝트를 밀고 가는 느낌이 들지 않게 곁에서 방향을 잡아주는 파트너입니다.",
        texture="투명 쉘, 부드러운 흰색 코어, 은은한 하늘색 맥박 라이트",
        color="#EAF6FF",
        accent_color="#2F80ED",
        symbol="동행",
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
