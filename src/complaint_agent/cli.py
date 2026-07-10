"""엔트리포인트: python -m complaint_agent run --pattern pipeline --case 1 [--dry-run]"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

# Windows 콘솔의 기본 코드페이지(cp949 등)는 em-dash 등 일부 한국어 텍스트를 인코딩하지 못해
# UnicodeEncodeError로 죽는다 — 콘솔 코드페이지와 무관하게 항상 UTF-8로 출력하도록 강제한다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from .agents.specialists import all_domains
from .config import Config
from .llm_client import LLMClient
from .patterns import expert_pool, fanout_fanin, generate_verify, hierarchical, pipeline, supervisor
from .skills.generator import generate_all, generate_skill
from .validation import dry_run as dry_run_suite
from .validation import skill_ablation
from .validation import trigger_tests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATTERNS = {
    pipeline.PATTERN_NAME: pipeline.run,
    fanout_fanin.PATTERN_NAME: fanout_fanin.run,
    expert_pool.PATTERN_NAME: expert_pool.run,
    generate_verify.PATTERN_NAME: generate_verify.run,
    supervisor.PATTERN_NAME: supervisor.run,
    hierarchical.PATTERN_NAME: hierarchical.run,
}


def load_complaints() -> list[dict]:
    path = PROJECT_ROOT / "data" / "sample_complaints.json"
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_run(args: argparse.Namespace) -> None:
    complaints = load_complaints()
    complaint = next((c for c in complaints if c["id"] == args.case), None)
    if complaint is None:
        raise SystemExit(f"case id {args.case}를 data/sample_complaints.json에서 찾을 수 없습니다.")

    if args.pattern not in PATTERNS:
        raise SystemExit(f"지원하지 않는 패턴: {args.pattern} (사용 가능: {list(PATTERNS)})")

    config = Config.load(mock_override=args.dry_run)
    llm_client = LLMClient(config)
    run_id = args.run_id or f"{args.pattern}_{complaint['id']}_{uuid.uuid4().hex[:8]}"
    workspace_root = PROJECT_ROOT / "runs"

    envelope = PATTERNS[args.pattern](complaint, llm_client, config, workspace_root, run_id)

    print(f"run_id={envelope.run_id} pattern={envelope.pattern} final_status={envelope.final_status}")
    print(f"hops={len(envelope.hops)} cumulative_tokens={envelope.cumulative_tokens}")
    print(f"결과 저장 위치: runs/{run_id}/")
    final_output = envelope.last_ok_output()
    if final_output:
        print("\n--- 최종 산출물(가장 최근 성공 홉) ---")
        print(final_output)


def cmd_generate_skills(args: argparse.Namespace) -> None:
    config = Config.load(mock_override=args.dry_run)
    llm_client = LLMClient(config)
    output_root = PROJECT_ROOT / "skills_generated"

    if args.domain:
        paths = [generate_skill(args.domain, llm_client, output_root)]
    else:
        paths = generate_all(llm_client, output_root)

    for path in paths:
        print(f"생성됨: {path.relative_to(PROJECT_ROOT)}")


def cmd_validate(args: argparse.Namespace) -> None:
    ran_any = False

    if args.trigger_tests:
        ran_any = True
        print("=== 트리거 경계 테스트 ===")
        for line in trigger_tests.run_trigger_tests():
            print(line)

    if args.dry_run_suite:
        ran_any = True
        complaints = load_complaints()
        complaint = next((c for c in complaints if c["id"] == args.case), None)
        if complaint is None:
            raise SystemExit(f"case id {args.case}를 data/sample_complaints.json에서 찾을 수 없습니다.")
        print(f"\n=== 드라이런 배선 검증 스위트 (case={args.case}) ===")
        for line in dry_run_suite.run_suite(complaint, PROJECT_ROOT / "runs"):
            print(line)

    if args.ablation:
        ran_any = True
        complaints = load_complaints()
        config = Config.load(mock_override=args.dry_run)
        llm_client = LLMClient(config)
        print("\n=== With-skill vs Without-skill 비교 ===")
        results = skill_ablation.run_ablation_suite(complaints, llm_client)
        print(skill_ablation.format_report(results))

    if not ran_any:
        raise SystemExit("--trigger-tests, --dry-run-suite, --ablation 중 하나 이상을 지정하십시오.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="complaint_agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="민원 1건에 대해 지정한 패턴을 실행한다.")
    run_parser.add_argument("--pattern", required=True, choices=list(PATTERNS))
    run_parser.add_argument("--case", required=True, type=int, help="data/sample_complaints.json의 id")
    run_parser.add_argument("--dry-run", action="store_true", help="mock LLM로 실행(API 비용 없음)")
    run_parser.add_argument("--run-id", default=None)
    run_parser.set_defaults(func=cmd_run)

    gen_parser = sub.add_parser("generate-skills", help="expert-pool 도메인 전문가 스킬을 자동 생성한다.")
    gen_parser.add_argument("--domain", choices=list(all_domains()), default=None,
                             help="생략하면 모든 도메인을 생성한다.")
    gen_parser.add_argument("--dry-run", action="store_true", help="mock LLM로 본문 초안 생성(API 비용 없음)")
    gen_parser.set_defaults(func=cmd_generate_skills)

    val_parser = sub.add_parser("validate", help="검증체계(트리거/드라이런/ablation)를 실행한다.")
    val_parser.add_argument("--trigger-tests", action="store_true")
    val_parser.add_argument("--dry-run-suite", action="store_true")
    val_parser.add_argument("--ablation", action="store_true")
    val_parser.add_argument("--case", type=int, default=1, help="--dry-run-suite에서 사용할 case id")
    val_parser.add_argument("--dry-run", action="store_true", help="--ablation을 mock LLM로 실행")
    val_parser.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
