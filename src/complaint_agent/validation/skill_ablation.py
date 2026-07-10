"""With-skill vs Without-skill 비교 (ADR-0006).
동일 민원을 (a) expert-pool 도메인 전문가 페르소나(with-skill), (b) 범용 drafter 페르소나(without-skill)로
각각 실행해 토큰 비용과 LLM judge 품질 점수를 비교한다. mock 모드에서는 품질 점수를 낼 수 없으므로 None으로
표시하고, 실제 점수는 Phase 6(실제 OpenRouter 연동)에서만 유효하다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..agents import classifier, specialists
from ..agents.base import Agent
from ..agents.drafter import PERSONA as GENERIC_DRAFTER_PERSONA
from ..llm_client import LLMClient

_JUDGE_SYSTEM = (
    "너는 민원 답변 품질 평가자다. 아래 민원과 답변 초안을 보고 근거 활용/구체성/어투 세 기준 각각 "
    "1~5점을 매기고, 마지막 줄에 '총점: N' 형식(N=3~15)으로만 총점을 답하라."
)


@dataclass
class AblationResult:
    complaint_id: str
    category: str
    specialist_used: str
    with_skill_tokens: int
    without_skill_tokens: int
    with_skill_score: int | None
    without_skill_score: int | None


def _generic_drafter() -> Agent:
    return Agent(name="drafter_generic", persona=GENERIC_DRAFTER_PERSONA)


def _judge(complaint_body: str, draft: str, llm_client: LLMClient) -> int | None:
    result = llm_client.complete(_JUDGE_SYSTEM, f"[민원]\n{complaint_body}\n\n[답변 초안]\n{draft}")
    if result.status != "ok":
        return None
    match = re.search(r"총점\s*[:：]\s*(\d+)", result.text)
    return int(match.group(1)) if match else None


def run_ablation(complaint: dict, llm_client: LLMClient) -> AblationResult:
    body = f"[{complaint['title']}]\n{complaint['body']}"

    cls_result = classifier.build().run(llm_client, body)
    category = cls_result.text

    specialist_name = specialists.route(category)
    with_result = specialists.build(specialist_name).run(llm_client, f"{body}\n\n[분류]: {category}")
    without_result = _generic_drafter().run(llm_client, f"{body}\n\n[분류]: {category}")

    cls_tokens = cls_result.tokens_in + cls_result.tokens_out
    with_tokens = cls_tokens + with_result.tokens_in + with_result.tokens_out
    without_tokens = cls_tokens + without_result.tokens_in + without_result.tokens_out

    return AblationResult(
        complaint_id=str(complaint["id"]),
        category=category,
        specialist_used=specialist_name,
        with_skill_tokens=with_tokens,
        without_skill_tokens=without_tokens,
        with_skill_score=_judge(body, with_result.text, llm_client),
        without_skill_score=_judge(body, without_result.text, llm_client),
    )


def run_ablation_suite(complaints: list[dict], llm_client: LLMClient) -> list[AblationResult]:
    return [run_ablation(c, llm_client) for c in complaints]


def format_report(results: list[AblationResult]) -> str:
    lines = [
        "| 민원ID | 분류 | 전문가 | with 토큰 | without 토큰 | with 점수 | without 점수 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        with_score = r.with_skill_score if r.with_skill_score is not None else "-"
        without_score = r.without_skill_score if r.without_skill_score is not None else "-"
        lines.append(
            f"| {r.complaint_id} | {r.category} | {r.specialist_used} | "
            f"{r.with_skill_tokens} | {r.without_skill_tokens} | {with_score} | {without_score} |"
        )
    if all(r.with_skill_score is None for r in results):
        lines.append("\n> 품질 점수가 모두 비어 있음 — mock(dry-run) 모드에서는 judge 채점 불가. "
                     "실제 점수는 `--dry-run` 없이 실행 시(Phase 6)에만 산출된다.")
    return "\n".join(lines)
