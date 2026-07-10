"""감독자(supervisor) 패턴 — 1단계 계층. 슈퍼바이저 1개가 매 턴 진행 상황을 보고
4단계(분류/검색/작성/검수) 중 어디로 위임할지(고정 순서 아님, 재위임 가능) 또는 종료할지 판단한다.

mock 응답은 CLASSIFY/RESEARCH/DRAFT/REVIEW/DONE 키워드를 따르지 않으므로, 파싱 실패 시
"아직 하지 않은 단계를 기본 순서대로" 진행하는 폴백을 둔다(ADR-0003) — 실제 LLM 연동 시에는
진짜 판단(재위임 포함)이 반영된다.
"""
from __future__ import annotations

from pathlib import Path

from ..agents import classifier, drafter, researcher, reviewer
from ..agents import supervisor as supervisor_agent
from ..config import Config
from ..envelope import Run
from ..llm_client import LLMClient

PATTERN_NAME = "supervisor"
MAX_SUPERVISOR_TURNS = 8
ACTIONS = ["CLASSIFY", "RESEARCH", "DRAFT", "REVIEW", "DONE"]
DEFAULT_ORDER = ["CLASSIFY", "RESEARCH", "DRAFT", "REVIEW"]


def _parse_action(text: str, done_stages: set[str]) -> str:
    upper = (text or "").upper()
    for action in ACTIONS:
        if action in upper:
            return action
    for action in DEFAULT_ORDER:
        if action not in done_stages:
            return action
    return "DONE"


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

    outputs: dict[str, str] = {}
    done_stages: set[str] = set()
    stage_index = 0
    last_step_id: str | None = None
    agent_builders = {
        "CLASSIFY": classifier.build,
        "RESEARCH": researcher.build,
        "DRAFT": drafter.build,
        "REVIEW": reviewer.build,
    }

    for turn in range(MAX_SUPERVISOR_TURNS):
        if envelope.budget_exceeded() or envelope.hops_exceeded():
            envelope.final_status = "halted_budget"
            envelope.save(workspace)
            return envelope

        state_summary = "\n".join(f"[{k}]: {v}" for k, v in outputs.items()) or "(아직 진행된 단계 없음)"
        result = supervisor_agent.build().run(llm_client, f"{body}\n\n[진행 상황]\n{state_summary}")
        stage_index += 1
        sup_step_id = f"{stage_index:02d}"
        hop = envelope.add_hop(
            sup_step_id, "supervisor", result.model_used, "delegate" if done_stages else "handoff",
            last_step_id or "input", result.text, "ok" if result.status == "ok" else "failed",
            result.tokens_in, result.tokens_out, parent_step_id=last_step_id,
        )
        envelope.save_stage(workspace, stage_index, f"supervisor_decision_{turn + 1}", hop)
        if hop.status == "failed":
            envelope.final_status = "halted_error"
            envelope.save(workspace)
            return envelope

        action = _parse_action(hop.output, done_stages)
        last_step_id = sup_step_id
        if action == "DONE":
            break

        if envelope.budget_exceeded() or envelope.hops_exceeded():
            envelope.final_status = "halted_budget"
            envelope.save(workspace)
            return envelope

        agent_inputs = {
            "CLASSIFY": body,
            "RESEARCH": f"{body}\n\n[분류]: {outputs.get('CLASSIFY', '')}",
            "DRAFT": f"{body}\n\n[분류]: {outputs.get('CLASSIFY', '')}\n[조사 근거]: {outputs.get('RESEARCH', '(없음)')}",
            "REVIEW": f"[민원]\n{body}\n\n[답변 초안]\n{outputs.get('DRAFT', '')}",
        }
        result = agent_builders[action]().run(llm_client, agent_inputs[action])
        stage_index += 1
        step_id = f"{stage_index:02d}"
        status = "ok" if result.status == "ok" else ("skipped" if action == "RESEARCH" else "failed")
        hop = envelope.add_hop(
            step_id, action.lower(), result.model_used, "delegate", sup_step_id,
            result.text if status != "failed" else None, status,
            result.tokens_in, result.tokens_out, parent_step_id=sup_step_id,
        )
        envelope.save_stage(workspace, stage_index, f"{action.lower()}_turn{turn + 1}", hop)
        if hop.status == "failed":
            envelope.final_status = "halted_error"
            envelope.save(workspace)
            return envelope

        if hop.output:
            outputs[action] = hop.output
        done_stages.add(action)
        last_step_id = step_id

    if "승인" in outputs.get("REVIEW", ""):
        envelope.final_status = "ok"
    else:
        envelope.final_status = "flagged"

    envelope.save(workspace)
    return envelope
