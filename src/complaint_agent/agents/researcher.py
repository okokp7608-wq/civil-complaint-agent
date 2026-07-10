"""검색 에이전트 — 관련 법령/과거답변/유사사례 조사만 담당한다(ADR-0004).
실제 법령 API 대신 "예시 도구"로 대체한다(강의 4부 지침: 검색·법령 API는 예시 도구로 대체해도 됨).
"""
from .base import Agent

PERSONA = (
    "너는 공무원 민원 답변을 위한 근거 조사 담당자다. 주어진 민원과 분류를 보고 관련 법령·규정과 "
    "과거 유사 민원에 대한 답변 사례를 간단히 요약해 근거로 제시하라. 최종 답변 문구나 승인 여부는 "
    "판단하지 않는다."
)


def _example_tool(_: str) -> str:
    """예시 도구 — 실제 법령/판례 DB 연동은 범위 밖(강의 지침). 참고용 플레이스홀더."""
    return (
        "(예시 도구) 참고 근거 후보: 국가공무원법, 국가공무원 복무규정, 공무원보수규정, "
        "공무원 인사기록·통계 및 인사사무 처리 규정 등 — 실제 조문 대조는 담당 부서 확인 필요."
    )


def build(model: str | None = None) -> Agent:
    return Agent(name="researcher", persona=PERSONA, model=model, tools=[_example_tool])
