"""파이프라인 패턴 — 분류→검색→작성→검수 고정 순서, 전부 핸드오프(되돌아오지 않음)."""
from __future__ import annotations

from pathlib import Path

from ..agents import classifier, drafter, researcher, reviewer
from ..config import Config
from ..envelope import Run
from ..llm_client import LLMClient

PATTERN_NAME = "pipeline"


def run(complaint: dict, llm_client: LLMClient, config: Config, workspace_root: Path, run_id: str) -> Run:
    workspace = workspace_root / run_id
    envelope = Run(
        run_id=run_id,
        pattern=PATTERN_NAME,
        complaint_id=str(complaint["id"]),
        max_tokens_total=config.max_tokens_total,
        max_hops=config.max_hops,
    )

    body = f"[{complaint['title']}]\n{complaint['body']}"

    # 1. 분류
    result = classifier.build().run(llm_client, body)
    hop = envelope.add_hop("01", "classifier", result.model_used, "handoff", "input", result.text,
                            "ok" if result.status == "ok" else "failed", result.tokens_in, result.tokens_out)
    envelope.save_stage(workspace, 1, "classification", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
        envelope.save(workspace)
        return envelope
    category = hop.output

    # 2. 검색 (비핵심 단계 — 실패해도 스킵-진행)
    research_input = f"{body}\n\n[분류]: {category}"
    result = researcher.build().run(llm_client, research_input)
    status = "ok" if result.status == "ok" else "skipped"
    hop = envelope.add_hop("02", "researcher", result.model_used, "handoff", "01_classification.json",
                            result.text if status == "ok" else None, status, result.tokens_in, result.tokens_out)
    envelope.save_stage(workspace, 2, "research", hop)
    research_notes = hop.output or "(검색 단계 스킵됨 — 근거 자료 없이 진행)"

    if envelope.budget_exceeded() or envelope.hops_exceeded():
        envelope.final_status = "halted_budget"
        envelope.save(workspace)
        return envelope

    # 3. 작성 (핵심 단계)
    draft_input = f"{body}\n\n[분류]: {category}\n[조사 근거]: {research_notes}"
    result = drafter.build().run(llm_client, draft_input)
    hop = envelope.add_hop("03", "drafter", result.model_used, "handoff", "02_research.json",
                            result.text, "ok" if result.status == "ok" else "failed",
                            result.tokens_in, result.tokens_out)
    envelope.save_stage(workspace, 3, "draft", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
        envelope.save(workspace)
        return envelope
    draft_text = hop.output

    if envelope.budget_exceeded() or envelope.hops_exceeded():
        envelope.final_status = "halted_budget"
        envelope.save(workspace)
        return envelope

    # 4. 검수 (핵심 단계)
    review_input = f"[민원]\n{body}\n\n[답변 초안]\n{draft_text}"
    result = reviewer.build().run(llm_client, review_input)
    hop = envelope.add_hop("04", "reviewer", result.model_used, "handoff", "03_draft.json",
                            result.text, "ok" if result.status == "ok" else "failed",
                            result.tokens_in, result.tokens_out)
    envelope.save_stage(workspace, 4, "review", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
    else:
        envelope.final_status = "ok" if "승인" in (hop.output or "") else "flagged"

    envelope.save(workspace)
    return envelope
