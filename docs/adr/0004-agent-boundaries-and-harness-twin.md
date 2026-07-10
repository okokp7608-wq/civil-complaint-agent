# 0004. 에이전트 책임 경계·핸드오프 규칙 확정, Claude Code 하네스 트윈 작성

* Status: accepted
* Date: 2026-07-10

## Context and Problem Statement

1~2단계는 4개 에이전트를 배선 검증용 스텁(한두 문장 페르소나)으로만 두었다. 실제 민원 답변 품질을 내려면 각 에이전트의 책임 경계, 분류 체계, 산출물 포맷을 확정해야 한다. 동시에 ADR-0001에서 결정한 대로 이 설계를 `82-report-generator`/`62-adr-writer` 컨벤션을 따르는 Claude Code 하네스(`.claude/agents/*.md`, `.claude/skills/civil-complaint-drafter/skill.md`)로도 문서화해야 한다.

## Decision Drivers

* `expert-pool` 패턴(2단계에서 구현)의 라우팅이 분류 카테고리 문자열의 키워드 매칭에 의존하므로, 분류 체계를 고정하지 않으면 라우팅이 불안정해진다.
* Harness-100 품질 기준: "트리거 경계 — should-trigger + NOT-trigger 명시"를 오케스트레이터 스킬에 반드시 포함해야 한다.
* 두 표현(Python 앱의 persona 문자열 vs `.claude/agents/*.md`)이 어긋나면 "고도화"라는 하네스 계승 취지가 무색해진다 — 같은 책임 경계를 두 형태로 동시에 기술한다.

## Decision Outcome

### 분류 체계 (classifier ↔ expert-pool 라우팅 공유)

`agents/specialists.py`의 라우팅 키워드와 1:1 대응하는 8개 고정 카테고리를 classifier의 출력 어휘로 못박는다:
`복무·휴가 | 보수·수당 | 인사·복무 | 채용 | 복무규정 | 교육훈련 | 주택·복지 | 세무` (+ 애매하면 `기타`).
이는 `data/sample_complaints.json`의 `category_hint`와도 동일해, Phase 5의 with/without-skill 비교·트리거 테스트에서 정답 레이블로 재사용할 수 있다.

### 에이전트 책임 경계

| 에이전트 | 책임 | 하지 않는 것 |
|---|---|---|
| classifier | 8개 고정 카테고리 중 하나로 분류만 | 답변 작성, 법령 판단 |
| researcher | 관련 근거(법령/과거답변/유사사례) 조사만 | 최종 문구 확정, 승인 여부 판단 |
| drafter | 근거를 반영해 공문체 답변 초안 작성 | 근거 조사, 자기 검수 |
| reviewer | 근거 오류·어투·누락·개인정보 노출 점검, 승인/반려만 | 초안 재작성(피드백만 반환, 수정은 drafter 몫) |

### 핸드오프 vs 델리게이트 규칙 (ADR-0002/0003 재확인)

- researcher/classifier → 다음 단계: 항상 핸드오프(되돌아오지 않음)
- reviewer → drafter로 돌아가는 경로만 델리게이트(재작업 위임) — reviewer가 직접 초안을 고치지 않는다(책임 분리 유지)

### Claude Code 하네스 트윈

`82-report-generator` 컨벤션을 그대로 따른다:
- `.claude/agents/{classifier,researcher,drafter,reviewer}.md` — frontmatter(name/description) + 핵심역할/작업원칙/산출물포맷/팀통신프로토콜/에러핸들링
- `.claude/skills/civil-complaint-drafter/skill.md` — 오케스트레이터: 에이전트팀 구성표, 6개 패턴 트리거 매핑, **should-trigger/NOT-trigger 명시**, 데이터 전달 프로토콜, 에러 핸들링표, 테스트 시나리오 3종(정상/기존파일/에러)
- Python 쪽 persona 문자열(`agents/*.py`)과 `.claude/agents/*.md`는 같은 책임 경계·분류체계·톤을 공유하되, 전자는 실행 코드용 간결 프롬프트, 후자는 Claude Code 서브에이전트용 상세 문서로 표현 형식만 다르다.

## Consequences

* 좋음: 분류 체계 고정으로 expert-pool 라우팅과 Phase 5 검증(정답 레이블 비교)이 안정적으로 연결된다.
* 좋음: reviewer가 직접 수정하지 않는 규칙 덕분에 generate-verify/hierarchical의 델리게이트 루프 의미(재작업은 항상 drafter 담당)가 코드와 문서 양쪽에서 일관된다.
* 나쁨: 8개 고정 카테고리 밖의 실제 민원(다부처 복합 민원 등)은 "기타"로만 처리되어 다소 거칠다 — 실제 배치 전에는 카테고리 확장이 필요하다(향후 과제로 남김).
