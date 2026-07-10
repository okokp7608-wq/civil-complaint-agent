"""패턴 간 공유 로직 (ADR-0003) — 병렬 리서치(fan-out/fan-in)와 bounded 작성↔검수 루프.
`fanout_fanin`/`hierarchical`이 리서치 헬퍼를, `generate_verify`/`hierarchical`이 작성-검수 루프를 공용한다.
"""
from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Optional

from ..agents import drafter, researcher, reviewer
from ..envelope import Run

RESEARCH_FOCUSES = [
    ("law", "관련 법령을 조사하라."),
    ("precedent", "과거 유사 민원에 대한 답변 사례를 조사하라."),
    ("case", "유사 사례를 조사하라."),
]


def run_parallel_research(
    complaint_body: str,
    category: str,
    llm_client,
    envelope: Run,
    workspace: Path,
    stage_index: int,
    input_ref: str,
    parent_step_id: Optional[str] = None,
) -> tuple[str, int, str]:
    """3개 조사 초점을 실제로 동시 호출(ThreadPoolExecutor)한 뒤 결정적으로 병합한다.
    반환: (병합된 조사 근거, 갱신된 stage_index, 병합 홉의 step_id)
    """
    base_input = f"{complaint_body}\n\n[분류]: {category}"

    def call(focus_name: str, instruction: str):
        agent = researcher.build()
        return focus_name, agent.run(llm_client, f"{base_input}\n\n[조사 지시]: {instruction}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(RESEARCH_FOCUSES)) as executor:
        futures = [executor.submit(call, name, instr) for name, instr in RESEARCH_FOCUSES]
        results = [f.result() for f in futures]

    step_ids: list[str] = []
    notes: list[str] = []
    for focus_name, result in results:
        stage_index += 1
        step_id = f"{stage_index:02d}"
        status = "ok" if result.status == "ok" else "skipped"
        hop = envelope.add_hop(
            step_id, f"researcher_{focus_name}", result.model_used, "handoff", input_ref,
            result.text if status == "ok" else None, status, result.tokens_in, result.tokens_out,
            parent_step_id=parent_step_id,
        )
        envelope.save_stage(workspace, stage_index, f"research_{focus_name}", hop)
        step_ids.append(step_id)
        if hop.output:
            notes.append(f"[{focus_name}] {hop.output}")

    # fan-in: LLM 호출 없이 결정적으로 병합 — 병합 단계에서 불필요한 비용을 만들지 않는다.
    stage_index += 1
    merge_step_id = f"{stage_index:02d}"
    merged = "\n".join(notes) if notes else "(병렬 조사가 모두 실패/스킵됨 — 근거 자료 없이 진행)"
    merge_hop = envelope.add_hop(
        merge_step_id, "research_merger", "n/a", "handoff", ",".join(step_ids),
        merged, "ok" if notes else "skipped", 0, 0,
        parent_step_id=step_ids[0] if step_ids else parent_step_id,
    )
    envelope.save_stage(workspace, stage_index, "research_merged", merge_hop)

    return merged, stage_index, merge_step_id


def run_draft_review_loop(
    complaint_body: str,
    category: str,
    research_notes: str,
    llm_client,
    envelope: Run,
    workspace: Path,
    stage_index: int,
    rework_limit: int,
    input_ref: str,
) -> tuple[Optional[str], int, str]:
    """작성 -> 검수를 최대 rework_limit회 반복한다. 델리게이트 엣지는 검수->재작성 구간뿐이다.
    반환: (최종 초안 텍스트 또는 None, 갱신된 stage_index, 최종상태: ok|flagged|halted_error|halted_budget)
    """
    prev_review_step_id: Optional[str] = None
    feedback = ""
    draft_text: Optional[str] = None

    for rework in range(rework_limit):
        if envelope.budget_exceeded() or envelope.hops_exceeded():
            return draft_text, stage_index, "halted_budget"

        stage_index += 1
        draft_step_id = f"{stage_index:02d}"
        draft_input = f"{complaint_body}\n\n[분류]: {category}\n[조사 근거]: {research_notes}"
        if feedback:
            draft_input += f"\n\n[검수 피드백 — 반영해서 수정]: {feedback}"

        result = drafter.build().run(llm_client, draft_input)
        handoff_type = "delegate" if rework > 0 else "handoff"
        ref = prev_review_step_id if rework > 0 else input_ref
        hop = envelope.add_hop(
            draft_step_id, "drafter", result.model_used, handoff_type, ref,
            result.text, "ok" if result.status == "ok" else "failed",
            result.tokens_in, result.tokens_out,
            parent_step_id=prev_review_step_id if rework > 0 else None,
        )
        envelope.save_stage(workspace, stage_index, f"draft_v{rework + 1}", hop)
        if hop.status == "failed":
            return None, stage_index, "halted_error"
        draft_text = hop.output

        if envelope.budget_exceeded() or envelope.hops_exceeded():
            return draft_text, stage_index, "halted_budget"

        stage_index += 1
        review_step_id = f"{stage_index:02d}"
        result = reviewer.build().run(llm_client, f"[민원]\n{complaint_body}\n\n[답변 초안]\n{draft_text}")
        hop = envelope.add_hop(
            review_step_id, "reviewer", result.model_used, "handoff", draft_step_id,
            result.text, "ok" if result.status == "ok" else "failed",
            result.tokens_in, result.tokens_out, parent_step_id=draft_step_id,
        )
        envelope.save_stage(workspace, stage_index, f"review_v{rework + 1}", hop)
        prev_review_step_id = review_step_id
        if hop.status == "failed":
            return draft_text, stage_index, "halted_error"

        if "승인" in (hop.output or ""):
            return draft_text, stage_index, "ok"
        feedback = hop.output

    return draft_text, stage_index, "flagged"
