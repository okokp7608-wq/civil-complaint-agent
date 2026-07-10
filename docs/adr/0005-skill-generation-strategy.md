# 0005. Progressive Disclosure 스킬 자동 생성 전략

* Status: accepted
* Date: 2026-07-10

## Context and Problem Statement

`expert-pool` 패턴(2단계)은 `agents/specialists.py`에 도메인 전문가 페르소나를 인라인 문자열로 하드코딩해 두었다.
도메인이 늘어날 때마다(주택→세무→교육→…) 사람이 매번 스킬 문서를 손으로 쓰면 확장성이 없다. 사용자가 요구한
"Progressive Disclosure 패턴으로 컨텍스트를 효율 관리하는 스킬 자동 생성"을 만족하려면, Claude Code 스킬의
3단계 공개(메타데이터 상시 로드 → 본문은 트리거 시 로드 → 참조 파일은 필요할 때만 로드) 구조를 실제로 자동 생성
파이프라인에 반영해야 한다.

## Decision Drivers

* 트리거 품질(should/NOT-trigger 판별)은 frontmatter의 `description`이 좌우한다 — 이 필드가 매번 LLM 창작에
  좌우되면 트리거 테스트(5단계)가 불안정해진다.
* 본문의 도메인 지식(어떤 근거를 인용하는지, 어떤 어투를 쓰는지)은 사람이 일일이 쓰기보다 LLM이 초안을
  작성하고 사람이 검수하는 편이 확장성이 좋다.
* 3단계 공개 중 세 번째 계층(`reference/*.md`)은 실제로 "무거울 때만" 존재해야 한다 — 항상 만들면 3단계
  공개라는 개념 자체가 무의미해진다(Plan 에이전트 검토에서 지적됨).

## Considered Options

1. frontmatter + 본문 모두 LLM이 생성
2. frontmatter + 본문 모두 결정적 템플릿(LLM 미사용)
3. **frontmatter는 결정적 템플릿, 본문만 LLM 초안, reference/는 본문이 임계 크기를 넘을 때만 조건부 생성**

## Decision Outcome

**옵션 3 채택.**

### 생성 파이프라인 (`src/complaint_agent/skills/generator.py`)

1. **frontmatter (결정적)**: `agents/specialists.py`에 이미 있는 도메인별 `(persona, keywords)`에서
   `name: <domain>-specialist`, `description: "<domain> 도메인 민원 전문가 스킬. 관련 키워드: ... expert-pool
   패턴의 전문가 라우팅 대상."`을 템플릿으로 조립한다. LLM을 거치지 않으므로 트리거 테스트에서 항상 같은
   입력에 같은 결과가 나온다.
2. **본문 (LLM 초안)**: 도메인 페르소나·키워드를 LLM에 전달해 `82-report-generator` 컨벤션(핵심역할/작업원칙/
   산출물포맷/팀통신프로토콜/에러핸들링)을 따르는 본문을 초안 작성시킨다. 실패 시 "본문 생성 실패 — 수동 작성
   필요" placeholder로 대체하고 중단하지 않는다(비핵심 생성 작업이므로 halt하지 않음).
3. **reference/ (조건부)**: 본문이 `REFERENCE_THRESHOLD`(1500자)를 넘으면 마지막 문단 경계에서 잘라 앞부분은
   `SKILL.md`에 남기고 포인터(`> 세부 내용은 reference/details.md를 참고하라`)를 붙이며, 뒷부분은
   `reference/details.md`로 분리한다. 넘지 않으면 `reference/`를 아예 만들지 않는다.

### 산출 위치

`skills_generated/<domain>/SKILL.md` (+ 조건부 `reference/details.md`). `expert-pool` 패턴은 현재
`agents/specialists.py`의 인라인 페르소나를 계속 쓰되(런타임 의존성 최소화), 자동 생성된 스킬 문서는 검수·확장용
산출물로 별도 보관한다. 스킬 본문 로직을 직접 실행에 자동 연결하는 것은 이번 단계 범위 밖으로 둔다(향후 과제).

## Consequences

* 좋음: description이 결정적이므로 5단계 트리거 테스트가 도메인 스킬 추가/삭제와 무관하게 안정적으로 동작한다.
* 좋음: 새 도메인을 늘릴 때 `agents/specialists.py`에 `(persona, keywords)` 한 줄만 추가하면
  `generate_all()`로 스킬 문서를 재생성할 수 있어 확장 비용이 낮다.
* 나쁨: LLM이 초안한 본문은 사람 검수 없이 바로 배포하기엔 품질 편차가 있을 수 있다 — 현재는 "자동 생성 산출물"로만
  다루고 실제 라우팅 실행 경로에는 연결하지 않는다.
