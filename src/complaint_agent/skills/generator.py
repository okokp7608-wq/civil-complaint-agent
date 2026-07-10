"""Progressive Disclosure 스킬 자동 생성기 (ADR-0005).
frontmatter(name/description)는 결정적 템플릿, 본문은 LLM 초안, reference/*.md는 본문이
REFERENCE_THRESHOLD를 넘을 때만 조건부로 생성한다 — Claude Code 스킬의 3단계 공개를 그대로 따른다.
"""
from __future__ import annotations

from pathlib import Path

from ..agents.specialists import all_domains
from ..llm_client import LLMClient

REFERENCE_THRESHOLD = 1500

_BODY_DRAFT_SYSTEM = (
    "너는 Claude Code 스킬 문서(SKILL.md) 작성자다. 아래 도메인 전문가의 민원 답변 역할에 맞춰, "
    "다음 5개 섹션(핵심 역할 / 작업 원칙 / 산출물 포맷 / 팀 통신 프로토콜 / 에러 핸들링)을 갖춘 "
    "한국어 마크다운 스킬 본문을 작성하라. frontmatter(---로 감싼 부분)는 쓰지 말고 본문만 작성하라."
)


def _deterministic_frontmatter(domain: str, keywords: list[str]) -> str:
    kw = ", ".join(keywords) if keywords else "일반 인사·복무 전반(다른 도메인에 해당하지 않는 경우의 기본값)"
    description = f"{domain} 도메인 민원 전문가 스킬. 관련 키워드: {kw}. expert-pool 패턴의 전문가 라우팅 대상."
    return f'---\nname: {domain}-specialist\ndescription: "{description}"\n---\n'


def _split_reference(body: str, threshold: int) -> tuple[str, str | None]:
    """본문이 threshold를 넘으면 마지막 문단 경계에서 잘라 뒷부분을 reference로 분리한다."""
    if len(body) <= threshold:
        return body, None
    split_at = body.rfind("\n\n", 0, threshold)
    if split_at <= 0:
        split_at = threshold
    head, tail = body[:split_at].rstrip(), body[split_at:].strip()
    head_with_pointer = head + "\n\n> 세부 내용은 `reference/details.md`를 참고하라.\n"
    return head_with_pointer, tail


def generate_skill(domain: str, llm_client: LLMClient, output_root: Path) -> Path:
    domains = all_domains()
    if domain not in domains:
        raise ValueError(f"알 수 없는 도메인: {domain} (사용 가능: {list(domains)})")
    persona, keywords = domains[domain]

    frontmatter = _deterministic_frontmatter(domain, keywords)

    user_prompt = (
        f"도메인: {domain}\n페르소나: {persona}\n"
        f"라우팅 키워드: {', '.join(keywords) or '(없음 — 기본 fallback 전문가)'}"
    )
    result = llm_client.complete(system=_BODY_DRAFT_SYSTEM, user=user_prompt)
    body = result.text if result.status == "ok" else f"# {domain} 전문가 스킬\n\n(본문 생성 실패 — 수동 작성 필요)"

    body, reference_content = _split_reference(body, REFERENCE_THRESHOLD)

    skill_dir = output_root / domain
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(frontmatter + "\n" + body + "\n", encoding="utf-8")

    if reference_content:
        ref_dir = skill_dir / "reference"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "details.md").write_text(reference_content + "\n", encoding="utf-8")

    return skill_path


def generate_all(llm_client: LLMClient, output_root: Path) -> list[Path]:
    return [generate_skill(domain, llm_client, output_root) for domain in all_domains()]
