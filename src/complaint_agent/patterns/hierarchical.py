"""계층형(hierarchical) 패턴 — 슈퍼바이저의 슈퍼바이저(≥2단계).
최상위 슈퍼바이저가 "리서치팀장"(병렬 서브 리서처 관리)과 "작성팀장"(작성↔검수 관리)에게
각각 위임한다. 작성팀이 승인을 못 받으면 최상위가 리서치팀에 재위임한다(TOP_MAX_CYCLES로 bounded).
`supervisor` 패턴(1단계)과 달리 여기서는 팀장 계층이 하나 더 있다(ADR-0003)."""
from __future__ import annotations

from pathlib import Path

from ..agents import classifier
from ..config import Config
from ..envelope import Run
from ..llm_client import LLMClient
from ._shared import run_draft_review_loop, run_parallel_research

PATTERN_NAME = "hierarchical"
TOP_MAX_CYCLES = 2
WRITING_REWORK_LIMIT = 2


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

    # 계층 0: 최상위 직속 분류
    result = classifier.build().run(llm_client, body)
    hop = envelope.add_hop("01", "classifier", result.model_used, "handoff", "input", result.text,
                            "ok" if result.status == "ok" else "failed", result.tokens_in, result.tokens_out)
    envelope.save_stage(workspace, 1, "classification", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
        envelope.save(workspace)
        return envelope
    category = hop.output

    stage_index = 1
    final_status = "flagged"

    for cycle in range(TOP_MAX_CYCLES):
        if envelope.budget_exceeded() or envelope.hops_exceeded():
            envelope.final_status = "halted_budget"
            envelope.save(workspace)
            return envelope

        # 계층 1: 최상위 -> 리서치팀장 위임 (2회차부터는 재위임)
        stage_index += 1
        research_delegate_id = f"{stage_index:02d}"
        research_delegate_hop = envelope.add_hop(
            research_delegate_id, "top_supervisor", "n/a", "delegate" if cycle > 0 else "handoff",
            "01_classification.json", f"리서치팀 위임 (cycle {cycle + 1})", "ok", 0, 0, parent_step_id="01",
        )
        envelope.save_stage(workspace, stage_index, f"top_delegate_research_{cycle + 1}", research_delegate_hop)

        # run_parallel_research는 한 번 호출되면 4홉(리서처 3 + 병합 1)을 한 블록으로 추가한다.
        # 블록 도중에 max_hops를 넘기지 않도록, 시작 전에 4홉만큼의 여유가 있는지 미리 확인한다.
        if envelope.would_exceed_hops(4) or envelope.budget_exceeded():
            envelope.final_status = "halted_budget"
            envelope.save(workspace)
            return envelope

        # 계층 2: 리서치팀장이 관리하는 병렬 서브 리서처들 (fan-out/fan-in 재사용)
        research_notes, stage_index, merge_step_id = run_parallel_research(
            body, category, llm_client, envelope, workspace, stage_index,
            input_ref=research_delegate_id, parent_step_id=research_delegate_id,
        )

        if envelope.budget_exceeded() or envelope.hops_exceeded():
            envelope.final_status = "halted_budget"
            envelope.save(workspace)
            return envelope

        # 계층 1: 최상위 -> 작성팀장 위임
        stage_index += 1
        writing_delegate_id = f"{stage_index:02d}"
        writing_delegate_hop = envelope.add_hop(
            writing_delegate_id, "top_supervisor", "n/a", "delegate", merge_step_id,
            "작성팀 위임", "ok", 0, 0, parent_step_id=merge_step_id,
        )
        envelope.save_stage(workspace, stage_index, f"top_delegate_writing_{cycle + 1}", writing_delegate_hop)

        # 계층 2: 작성팀장이 관리하는 작성↔검수 bounded 루프 (generate-verify 재사용)
        _, stage_index, final_status = run_draft_review_loop(
            body, category, research_notes, llm_client, envelope, workspace, stage_index,
            WRITING_REWORK_LIMIT, input_ref=writing_delegate_id,
        )

        if final_status in ("ok", "halted_error", "halted_budget"):
            break
        # final_status == "flagged" -> 작성팀이 승인을 못 받음 -> 최상위가 리서치팀에 재위임(다음 cycle)

    envelope.final_status = final_status
    envelope.save(workspace)
    return envelope
