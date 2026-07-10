"""트리거 경계(should/NOT-trigger) 회귀 테스트 (ADR-0006).
`.claude/skills/civil-complaint-drafter/skill.md`에 문서화된 경계·근거를 휴리스틱으로 옮겨,
문서와 코드가 어긋나지 않는지 감시한다. skill.md의 NOT-trigger 항목을 바꾸면 이 파일도 함께 갱신할 것.
"""
from __future__ import annotations

TRIGGER_KEYWORDS = ["민원"]

# (키워드, NOT-trigger 근거) — skill.md의 NOT-trigger 목록과 1:1 대응
NOT_TRIGGER_OVERRIDES: list[tuple[str, str]] = [
    ("보고서", "업무 보고서 작성 요청 — 82-report-generator 하네스 영역"),
    ("판례 해석", "심층 법률 자문 — researcher는 예시 도구 수준, 법률 자문 대체 아님"),
    ("법률 자문", "심층 법률 자문 — researcher는 예시 도구 수준, 법률 자문 대체 아님"),
    ("adr", "정책 결정 문서화 — 62-adr-writer 하네스 영역"),
    ("아키텍처 결정", "정책 결정 문서화 — 62-adr-writer 하네스 영역"),
    ("맞춤법만", "완성된 답변의 단순 교정 — reviewer 단독 호출 권장, 전체 파이프라인 불필요"),
]

# skill.md "트리거 경계" 절의 예시를 그대로 옮긴 회귀 케이스
SHOULD_TRIGGER_CASES = [
    "민원 답변 초안 만들어줘",
    "이 민원 처리해줘: 민원번호 12, 제목 연차휴가 문의, 본문 ...",
    "이 민원 분류해줘",
    "민원 검토해줘, 근거도 같이 찾아줘",
]

NOT_TRIGGER_CASES = [
    "이번 분기 매출 실적 보고서 만들어줘",
    "이 계약서 관련 판례 해석 좀 자세히 알려줘",
    "이 정책 결정에 대한 ADR 작성해줘",
    "이미 완성된 답변인데 맞춤법만 봐줘",
]


def predict_trigger(text: str) -> tuple[bool, str]:
    lowered = text.lower()
    for keyword, reason in NOT_TRIGGER_OVERRIDES:
        if keyword in lowered:
            return False, reason
    if any(kw in text for kw in TRIGGER_KEYWORDS):
        return True, "민원 관련 키워드 매칭"
    return False, "민원 관련 키워드 없음"


def run_trigger_tests() -> list[str]:
    results = []
    for text in SHOULD_TRIGGER_CASES:
        predicted, reason = predict_trigger(text)
        status = "OK  " if predicted else "FAIL"
        results.append(f"{status} [should-trigger] {text!r} -> predicted={predicted} ({reason})")
    for text in NOT_TRIGGER_CASES:
        predicted, reason = predict_trigger(text)
        status = "OK  " if not predicted else "FAIL"
        results.append(f"{status} [NOT-trigger]     {text!r} -> predicted={predicted} ({reason})")
    return results
