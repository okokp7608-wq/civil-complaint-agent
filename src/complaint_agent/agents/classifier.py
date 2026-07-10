"""분류 에이전트 — 8개 고정 카테고리 중 하나로만 분류한다(ADR-0004).
카테고리 체계는 `specialists.py`의 라우팅 키워드, `data/sample_complaints.json`의 category_hint와 동일하다.
"""
from .base import Agent

CATEGORIES = [
    "복무·휴가", "보수·수당", "인사·복무", "채용",
    "복무규정", "교육훈련", "주택·복지", "세무", "기타",
]

PERSONA = (
    "너는 공무원 민원 분류 담당자다. 민원 제목과 본문을 읽고, 다음 카테고리 중 "
    "가장 알맞은 하나만 정확히 그 표기대로 답하라(다른 말 덧붙이지 마라): "
    + ", ".join(CATEGORIES)
    + ". 애매하면 '기타'로 답하라. 최종 답변 작성이나 근거 판단은 하지 않는다."
)


def build(model: str | None = None) -> Agent:
    return Agent(name="classifier", persona=PERSONA, model=model)
