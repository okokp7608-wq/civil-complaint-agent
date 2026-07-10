"""팬아웃/팬인 패턴 — 검색 단계를 법령/과거답변/유사사례 3갈래로 병렬 실행 후 병합, 이후 작성/검수는 순차."""
from __future__ import annotations

from pathlib import Path

from ..agents import classifier, drafter, reviewer
from ..config import Config
from ..envelope import Run
from ..llm_client import LLMClient
from ._shared import run_parallel_research

PATTERN_NAME = "fanout_fanin"


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

    # 1. 분류 (핸드오프)
    result = classifier.build().run(llm_client, body)
    hop = envelope.add_hop("01", "classifier", result.model_used, "handoff", "input", result.text,
                            "ok" if result.status == "ok" else "failed", result.tokens_in, result.tokens_out)
    envelope.save_stage(workspace, 1, "classification", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
        envelope.save(workspace)
        return envelope
    category = hop.output

    # run_parallel_research는 4홉(리서처 3 + 병합 1)을 한 블록으로 추가하므로, 시작 전에
    # 그만큼의 여유가 있는지 미리 확인한다(hierarchical 패턴과 동일한 이유 — ADR-0002).
    if envelope.would_exceed_hops(4) or envelope.budget_exceeded():
        envelope.final_status = "halted_budget"
        envelope.save(workspace)
        return envelope

    # 2. 팬아웃(병렬 조사) -> 팬인(병합)
    research_notes, stage_index, merge_step_id = run_parallel_research(
        body, category, llm_client, envelope, workspace,
        stage_index=1, input_ref="01_classification.json", parent_step_id="01",
    )

    if envelope.budget_exceeded() or envelope.hops_exceeded():
        envelope.final_status = "halted_budget"
        envelope.save(workspace)
        return envelope

    # 3. 작성 (핸드오프, 핵심 단계)
    stage_index += 1
    draft_step_id = f"{stage_index:02d}"
    result = drafter.build().run(llm_client, f"{body}\n\n[분류]: {category}\n[조사 근거]: {research_notes}")
    hop = envelope.add_hop(draft_step_id, "drafter", result.model_used, "handoff", merge_step_id,
                            result.text, "ok" if result.status == "ok" else "failed",
                            result.tokens_in, result.tokens_out, parent_step_id=merge_step_id)
    envelope.save_stage(workspace, stage_index, "draft", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
        envelope.save(workspace)
        return envelope
    draft_text = hop.output

    if envelope.budget_exceeded() or envelope.hops_exceeded():
        envelope.final_status = "halted_budget"
        envelope.save(workspace)
        return envelope

    # 4. 검수 (핸드오프, 핵심 단계)
    stage_index += 1
    review_step_id = f"{stage_index:02d}"
    result = reviewer.build().run(llm_client, f"[민원]\n{body}\n\n[답변 초안]\n{draft_text}")
    hop = envelope.add_hop(review_step_id, "reviewer", result.model_used, "handoff", draft_step_id,
                            result.text, "ok" if result.status == "ok" else "failed",
                            result.tokens_in, result.tokens_out, parent_step_id=draft_step_id)
    envelope.save_stage(workspace, stage_index, "review", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
    else:
        envelope.final_status = "ok" if "승인" in (hop.output or "") else "flagged"

    envelope.save(workspace)
    return envelope
