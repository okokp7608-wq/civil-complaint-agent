# 0006. 검증체계 — 트리거 검증·드라이런·With-vs-Without-skill 비교

* Status: accepted
* Date: 2026-07-10

## Context and Problem Statement

1~4단계에서 배선 검증(dry-run)과 트리거 경계 문서화(skill.md의 should/NOT-trigger)를 각각 만들었지만
임시방편으로 수동 실행·수동 확인에 그쳤다. 회귀가 생겨도 잡아낼 수 없다. 또한 "왜 도메인 전문가 스킬
(expert-pool)이 유의미한가"를 실측 없이 주장만 하고 있었다.

## Decision Drivers

* Harness-100 품질 기준의 "트리거 경계" 문서(skill.md)가 실제로 지켜지는지 코드로 재현 가능한 형태로
  회귀 테스트해야 의미가 있다 — 문서만 있고 테스트가 없으면 다음 수정에서 조용히 어긋난다.
* Claude Code의 실제 의미 기반 트리거 판단(LLM이 description을 보고 판단)은 Python에서 직접 재현할 수
  없다 — 완전히 동일하게 흉내내는 대신, skill.md에 적힌 경계 근거(키워드·타 하네스 영역)를 **휴리스틱**으로
  옮겨 "문서와 실제 동작이 어긋나지 않는지"를 최소한으로 감시한다.
* mock LLM로는 답변 "품질"을 채점할 수 없다(모든 mock 출력이 구조적으로 동일한 placeholder이므로) — 품질
  점수는 실제 LLM 판정(judge) 호출이 필요하며, 이는 Phase 6(실제 OpenRouter 연동)에서만 의미 있는 숫자가
  나온다는 것을 명시한다.

## Considered Options

1. 검증을 계속 수동 실행에 의존
2. 자동화된 3종 검증(트리거/드라이런/ablation)을 코드화하되, 품질 채점은 mock에서 항상 통과(가짜)로 처리
3. **자동화된 3종 검증을 코드화하고, mock 모드에서는 메커니즘만 검증(품질 점수는 None으로 명시), 실제
   점수는 Phase 6에서만 산출**

## Decision Outcome

**옵션 3 채택.**

### 트리거 검증 (`validation/trigger_tests.py`)

`skill.md`의 should-trigger/NOT-trigger 목록에서 그대로 가져온 예시 문장에 대해, 같은 문서의 NOT-trigger
근거(보고서 요청→report-generator 영역, 판례 심층해석→법률자문 아님, ADR→adr-writer 영역, 맞춤법만→
reviewer 단독)를 휴리스틱 규칙으로 옮겨 `predict_trigger(text)`가 문서와 일치하는 예/아니오를 내는지
회귀 테스트한다.

### 드라이런 스위트 (`validation/dry_run.py`)

1~4단계에서 수동으로 했던 검증(예외 없음, `final_status`가 알려진 값 중 하나, `hops ≤ max_hops`,
`cumulative_tokens` 단조 증가, run 파일 저장됨)을 6개 패턴 전부에 대해 자동 실행하는 스위트로 공식화한다.

### With-vs-Without-skill Ablation (`validation/skill_ablation.py`)

같은 민원에 대해 (a) `expert-pool`의 도메인 전문가 페르소나(with-skill), (b) 범용 drafter 페르소나
(without-skill)로 각각 답변을 생성해 **토큰 비용**을 비교하고, LLM judge(3개 기준 합산 1~15점)로
**품질 점수**를 비교한다. mock 모드에서는 judge가 점수를 못 뽑아 `None`으로 표시되며, 리포트에 "실제 점수는
`--dry-run` 없이 실행 시에만 산출됨"을 명시한다(Phase 6에서 실측).

## Consequences

* 좋음: 세 검증 모두 `python -m complaint_agent validate --trigger-tests|--dry-run-suite|--ablation`로
  재실행 가능해, 이후 패턴/에이전트를 고쳐도 회귀를 즉시 감지한다.
* 좋음: ablation 리포트 포맷을 미리 고정해둬서 Phase 6에서 실제 키를 넣고 재실행하면 바로 실측 비교표가
  나온다.
* 나쁨: 트리거 휴리스틱은 Claude Code의 실제 의미 기반 판단을 근사할 뿐 완전히 같지 않다 — 문서(skill.md)와
  코드(휴리스틱)가 각각 따로 어긋날 수 있으므로, skill.md의 NOT-trigger 항목을 바꿀 때 이 파일도 함께
  갱신해야 한다는 점을 README에 남긴다.
