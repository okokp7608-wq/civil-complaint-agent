# Civil Complaint Drafter Harness

민원(번호·제목·본문)의 분류→검색→작성→검수를 에이전트 팀이 협업해 답변 초안을 생성하는 하네스.
`82-report-generator` 하네스의 3계층 구조(오케스트레이터 스킬 / 도메인 확장 스킬 / 에이전트)를 계승했다.

이 하네스는 `src/complaint_agent/`에 있는 실행 가능한 OpenRouter Python 앱과 **같은 설계**를 Claude Code
컨벤션으로 표현한 것이다(ADR-0001). 두 표현이 공유하는 것: 4개 에이전트의 책임 경계(ADR-0004), 8개 고정
분류 체계, 6종 아키텍처 패턴(pipeline/fan-out-fan-in/expert-pool/generate-verify/supervisor/hierarchical),
핸드오프-델리게이트 규칙.

## 구조

```
.claude/
├── agents/
│   ├── classifier.md      — 8개 고정 카테고리 분류
│   ├── researcher.md      — 법령/과거답변/유사사례 조사 (예시 도구)
│   ├── drafter.md         — 답변 초안 작성 (검수 피드백 반영해 재작성)
│   └── reviewer.md        — 근거·어투·누락·개인정보 검수 (승인/반려만, 직접 수정 안 함)
├── skills/
│   └── civil-complaint-drafter/
│       └── skill.md       — 오케스트레이터 (6개 패턴 트리거, 워크플로우, 에러 핸들링)
└── CLAUDE.md               — 이 파일
```

## 사용법

`/civil-complaint-drafter` 스킬을 트리거하거나, "민원 답변 초안 만들어줘" 같은 자연어로 요청한다.

## 산출물

Python 앱과 동일하게 `runs/<run-id>/`에 단계별 JSON과 `run_<run-id>.json`(Envelope, cost_log 포함)으로 저장된다.
Claude Code 내에서 실행할 경우 동일한 규칙을 따라 `runs/<run-id>/NN_stage.md`로 저장한다.

## 참고 문서 (`docs/adr/`)

- 0001: 하이브리드(앱+하네스) 구조
- 0002: 핸드오프 스키마·에러 핸들링·비용 서킷브레이커
- 0003: 6종 패턴 분류 기준
- 0004: 에이전트 책임 경계·분류 체계
- 0005: 스킬 자동 생성 전략
- 0006: 검증체계 기준
- 0007: 최종 모델 선정(`openai/gpt-4o-mini`)과 실측 결과
