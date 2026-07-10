"""전문가 풀(expert-pool) 패턴용 도메인 전문가 페르소나 및 라우팅.
Phase 4에서 이 페르소나들은 Progressive Disclosure 스킬(`skills_generated/`)로 자동 생성되어
대체/확장될 예정이다 — 지금은 인라인 정의로 배선만 검증한다.
"""
from .base import Agent

# 이름 -> (페르소나, 라우팅 키워드). general_hr은 키워드가 없어 항상 fallback으로 쓰인다.
_SPECIALISTS: dict[str, tuple[str, list[str]]] = {
    "housing": (
        "너는 공무원 주택·부동산 복지 제도(주택자금 대출, 관사 등) 전문가다. "
        "관련 제도를 근거로 정중한 민원 답변 초안을 작성하라.",
        ["주택", "부동산", "관사", "대출"],
    ),
    "tax": (
        "너는 공무원 보수·세무(연말정산, 원천징수, 각종 수당) 전문가다. "
        "관련 규정을 근거로 정중한 민원 답변 초안을 작성하라.",
        ["세무", "연말정산", "원천징수", "수당", "보수"],
    ),
    "education": (
        "너는 공무원 교육훈련 제도(이수 의무시간, 사이버교육 등) 전문가다. "
        "관련 규정을 근거로 정중한 민원 답변 초안을 작성하라.",
        ["교육", "훈련", "연수"],
    ),
    "recruitment": (
        "너는 공무원 채용시험(응시자격, 가산점 등) 전문가다. "
        "관련 규정을 근거로 정중한 민원 답변 초안을 작성하라.",
        ["채용", "시험", "응시", "가산점"],
    ),
    "general_hr": (
        "너는 공무원 일반 인사·복무(휴가, 복무규정, 육아휴직 등) 전문가다. "
        "관련 규정을 근거로 정중한 민원 답변 초안을 작성하라.",
        [],
    ),
}


def all_domains() -> dict[str, tuple[str, list[str]]]:
    """스킬 자동 생성기(Phase 4)가 참조하는 공개 접근자 — 내부 딕셔너리를 직접 노출하지 않는다."""
    return dict(_SPECIALISTS)


def route(category_text: str) -> str:
    text = category_text or ""
    for name, (_, keywords) in _SPECIALISTS.items():
        if keywords and any(kw in text for kw in keywords):
            return name
    return "general_hr"


def build(name: str, model: str | None = None) -> Agent:
    persona, _ = _SPECIALISTS.get(name, _SPECIALISTS["general_hr"])
    return Agent(name=f"specialist_{name}", persona=persona, model=model)
