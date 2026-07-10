"""생성-검증 패턴 — 작성↔검수 2역할 델리게이트 루프, 최대 REWORK_LIMIT회로 bounded.
강의 7부 "토큰 스노볼" 경고를 코드로 강제하는 사례: 루프는 반드시 유한하게 끝난다.
루프 자체는 ADR-0003에 따라 `_shared.run_draft_review_loop`를 재사용한다(hierarchical 패턴과 공용).
"""
from __future__ import annotations

from pathlib import Path

from ..agents import classifier, researcher
from ..config import Config
from ..envelope import Run
from ..llm_client import LLMClient
from ._shared import run_draft_review_loop

PATTERN_NAME = "generate_verify"
REWORK_LIMIT = 3


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

    # 2. 검색 (핸드오프, 비핵심 — 실패 시 스킵-진행)
    result = researcher.build().run(llm_client, f"{body}\n\n[분류]: {category}")
    status = "ok" if result.status == "ok" else "skipped"
    hop = envelope.add_hop("02", "researcher", result.model_used, "handoff", "01_classification.json",
                            result.text if status == "ok" else None, status, result.tokens_in, result.tokens_out)
    envelope.save_stage(workspace, 2, "research", hop)
    research_notes = hop.output or "(검색 단계 스킵됨 — 근거 자료 없이 진행)"

    # 3. 작성 ↔ 검수 델리게이트 루프 (공유 헬퍼)
    _, _, final_status = run_draft_review_loop(
        body, category, research_notes, llm_client, envelope, workspace,
        stage_index=2, rework_limit=REWORK_LIMIT, input_ref="02_research.json",
    )
    envelope.final_status = final_status
    envelope.save(workspace)
    return envelope
