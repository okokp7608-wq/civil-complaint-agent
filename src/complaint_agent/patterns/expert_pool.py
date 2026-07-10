"""전문가 풀 패턴 — 분류 에이전트가 도메인 전문 에이전트(주택/세무/교육/채용/일반) 중
하나로 1회 동적 핸드오프한다. 라우팅은 순수 로직(비용 0)이며, 되돌아오지 않는다."""
from __future__ import annotations

from pathlib import Path

from ..agents import classifier, reviewer, specialists
from ..config import Config
from ..envelope import Run
from ..llm_client import LLMClient

PATTERN_NAME = "expert_pool"


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

    # 2. 라우팅 (LLM 호출 없음 — 순수 로직, 비용 0)
    specialist_name = specialists.route(category)
    hop = envelope.add_hop("02", "router", "n/a", "handoff", "01_classification.json",
                            specialist_name, "ok", 0, 0, parent_step_id="01")
    envelope.save_stage(workspace, 2, "routing", hop)

    if envelope.budget_exceeded() or envelope.hops_exceeded():
        envelope.final_status = "halted_budget"
        envelope.save(workspace)
        return envelope

    # 3. 전문가로 1회 동적 핸드오프 (되돌아오지 않음)
    result = specialists.build(specialist_name).run(llm_client, f"{body}\n\n[분류]: {category}")
    hop = envelope.add_hop("03", f"specialist_{specialist_name}", result.model_used, "handoff",
                            "02_routing.json", result.text, "ok" if result.status == "ok" else "failed",
                            result.tokens_in, result.tokens_out, parent_step_id="02")
    envelope.save_stage(workspace, 3, "specialist_draft", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
        envelope.save(workspace)
        return envelope
    draft_text = hop.output

    if envelope.budget_exceeded() or envelope.hops_exceeded():
        envelope.final_status = "halted_budget"
        envelope.save(workspace)
        return envelope

    # 4. 검수 (핸드오프)
    result = reviewer.build().run(llm_client, f"[민원]\n{body}\n\n[답변 초안]\n{draft_text}")
    hop = envelope.add_hop("04", "reviewer", result.model_used, "handoff", "03_specialist_draft.json",
                            result.text, "ok" if result.status == "ok" else "failed",
                            result.tokens_in, result.tokens_out, parent_step_id="03")
    envelope.save_stage(workspace, 4, "review", hop)
    if hop.status == "failed":
        envelope.final_status = "halted_error"
    else:
        envelope.final_status = "ok" if "승인" in (hop.output or "") else "flagged"

    envelope.save(workspace)
    return envelope
