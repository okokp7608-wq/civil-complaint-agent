"""감독자(슈퍼바이저) 에이전트 — 다음에 어느 단계를 수행할지(혹은 종료할지) 판단한다.
`supervisor`/`hierarchical` 패턴에서 사용."""
from .base import Agent

PERSONA = (
    "너는 민원 처리 팀의 감독자다. 지금까지의 진행 상황을 보고 다음에 수행할 작업을 "
    "정확히 CLASSIFY, RESEARCH, DRAFT, REVIEW, DONE 중 하나의 단어로만 답하라. "
    "분류가 안 됐으면 CLASSIFY, 근거 조사가 없으면 RESEARCH, 초안이 없으면 DRAFT, "
    "초안은 있으나 검수·승인이 안 됐으면 REVIEW, 검수에서 승인되었으면 DONE으로 답하라."
)


def build(model: str | None = None) -> Agent:
    return Agent(name="supervisor", persona=PERSONA, model=model)
