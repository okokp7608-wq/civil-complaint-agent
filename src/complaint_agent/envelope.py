"""핸드오프(Envelope) 데이터 스키마. ADR-0002 참고."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Optional

HandoffType = Literal["handoff", "delegate"]
HopStatus = Literal["ok", "retry", "failed", "skipped"]
FinalStatus = Literal["ok", "halted_budget", "halted_error", "flagged"]


@dataclass
class Hop:
    step_id: str
    agent: str
    model: str
    handoff_type: HandoffType
    input_ref: str
    output: Optional[str] = None
    status: HopStatus = "ok"
    parent_step_id: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cumulative_tokens: int = 0
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))


@dataclass
class Run:
    run_id: str
    pattern: str
    complaint_id: str
    max_tokens_total: int = 200_000
    max_hops: int = 12
    hops: list[Hop] = field(default_factory=list)
    final_status: FinalStatus = "ok"

    @property
    def cumulative_tokens(self) -> int:
        return self.hops[-1].cumulative_tokens if self.hops else 0

    def budget_exceeded(self) -> bool:
        return self.cumulative_tokens >= self.max_tokens_total

    def hops_exceeded(self) -> bool:
        return len(self.hops) >= self.max_hops

    def would_exceed_hops(self, additional: int) -> bool:
        """호출 하나가 여러 홉을 한 번에 추가하는 블록(예: 병렬 리서치)을 시작하기 전,
        그 블록을 끝까지 실행했을 때 max_hops를 넘는지 미리 확인한다."""
        return len(self.hops) + additional > self.max_hops

    def add_hop(
        self,
        step_id: str,
        agent: str,
        model: str,
        handoff_type: HandoffType,
        input_ref: str,
        output: Optional[str],
        status: HopStatus,
        tokens_in: int,
        tokens_out: int,
        parent_step_id: Optional[str] = None,
    ) -> Hop:
        prev_cum = self.cumulative_tokens
        hop = Hop(
            step_id=step_id,
            agent=agent,
            model=model,
            handoff_type=handoff_type,
            input_ref=input_ref,
            output=output,
            status=status,
            parent_step_id=parent_step_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cumulative_tokens=prev_cum + tokens_in + tokens_out,
        )
        self.hops.append(hop)
        return hop

    def last_ok_output(self) -> Optional[str]:
        for hop in reversed(self.hops):
            if hop.status == "ok" and hop.output is not None:
                return hop.output
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def save(self, workspace_dir: Path) -> Path:
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = workspace_dir / f"run_{self.run_id}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def save_stage(self, workspace_dir: Path, stage_index: int, stage_name: str, hop: Hop) -> Path:
        """report-generator의 _workspace/NN_*.md 파일 기반 협업 계승 — 단계별 산출물을 개별 파일로도 남긴다."""
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = workspace_dir / f"{stage_index:02d}_{stage_name}.json"
        if path.exists():
            return path  # resume: 이미 존재하면 재작성하지 않음
        path.write_text(json.dumps(asdict(hop), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def load(path: Path) -> "Run":
        data = json.loads(path.read_text(encoding="utf-8"))
        hops = [Hop(**h) for h in data.pop("hops")]
        run = Run(hops=hops, **data)
        return run
