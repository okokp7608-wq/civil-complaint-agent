"""드라이런 배선 검증 스위트 (ADR-0006) — mock LLM로 6개 패턴 전부를 실행해
예외 없음/final_status 유효성/홉 상한 준수/비용 단조 증가/파일 저장을 자동으로 확인한다.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..envelope import Run
from ..llm_client import LLMClient
from ..patterns import expert_pool, fanout_fanin, generate_verify, hierarchical, pipeline, supervisor

ALL_PATTERNS = {
    pipeline.PATTERN_NAME: pipeline.run,
    fanout_fanin.PATTERN_NAME: fanout_fanin.run,
    expert_pool.PATTERN_NAME: expert_pool.run,
    generate_verify.PATTERN_NAME: generate_verify.run,
    supervisor.PATTERN_NAME: supervisor.run,
    hierarchical.PATTERN_NAME: hierarchical.run,
}

VALID_FINAL_STATUSES = {"ok", "flagged", "halted_budget", "halted_error"}


class DryRunFailure(Exception):
    pass


def _check_monotonic_cost(envelope: Run) -> None:
    prev = 0
    for hop in envelope.hops:
        if hop.cumulative_tokens < prev:
            raise DryRunFailure(f"cumulative_tokens가 감소함(스노볼 로그 무결성 위반): {hop.step_id}")
        prev = hop.cumulative_tokens


def check_pattern(name: str, run_fn, complaint: dict, workspace_root: Path) -> str:
    config = Config.load(mock_override=True)
    llm_client = LLMClient(config)
    run_id = f"dryrun_{name}_{complaint['id']}"
    envelope = run_fn(complaint, llm_client, config, workspace_root, run_id)

    if envelope.final_status not in VALID_FINAL_STATUSES:
        raise DryRunFailure(f"알 수 없는 final_status={envelope.final_status}")
    if len(envelope.hops) > envelope.max_hops:
        raise DryRunFailure(f"hops({len(envelope.hops)}) > max_hops({envelope.max_hops})")
    _check_monotonic_cost(envelope)

    saved_path = workspace_root / run_id / f"run_{run_id}.json"
    if not saved_path.exists():
        raise DryRunFailure("run 파일이 저장되지 않음")

    return (f"OK   {name:16s} hops={len(envelope.hops):2d} "
            f"tokens={envelope.cumulative_tokens:5d} final={envelope.final_status}")


def run_suite(complaint: dict, workspace_root: Path) -> list[str]:
    results = []
    for name, run_fn in ALL_PATTERNS.items():
        try:
            results.append(check_pattern(name, run_fn, complaint, workspace_root))
        except DryRunFailure as exc:
            results.append(f"FAIL {name:16s} {exc}")
    return results
