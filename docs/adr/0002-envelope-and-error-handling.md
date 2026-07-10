# 0002. 핸드오프(Envelope) 데이터 스키마 및 에러 핸들링·비용 서킷브레이커 정책

* Status: accepted
* Date: 2026-07-09

## Context and Problem Statement

강의 7부는 멀티 에이전트의 최대 단점이 "토큰 스노볼"(홉마다 입력+추론+출력이 누적되어 비용이 비선형으로 증가)이라고 경고한다. 6종 아키텍처 패턴(파이프라인/팬아웃-팬인/전문가풀/생성-검증/감독자/계층형)이 에이전트 간 데이터를 어떻게 주고받는지, 실패했을 때 무엇을 하는지, 비용이 얼마나 쌓였는지를 공통된 방식으로 기록하지 않으면 패턴 간 비교도, 비용 통제도 불가능하다.

## Decision Drivers

* generate-verify/supervisor/hierarchical 패턴은 되돌아오는(delegate) 호출이 있어 무한 루프·비용 폭주 위험이 있다.
* `82-report-generator`의 안정성 정책(재시도, 누락시 진행, 검증 재작업)을 계승하되, 실제 비용 상한을 코드로 강제해야 한다.
* `runs/<run-id>/`에 파일로 남겨야 재실행(resume) 및 사후 분석(어느 홉에서 비용이 튀었는지)이 가능하다.

## Considered Options

1. 단순 `output` 필드만 있는 최소 스키마
2. `output` + 단일 `cost_tokens` 누적값
3. `output` + 홉별 `cost_log` 리스트 + run 레벨 예산/서킷브레이커 + handoff_type/parent_step_id

## Decision Outcome

**옵션 3 채택.**

### Envelope 스키마 (`src/complaint_agent/envelope.py`)

```
Hop:
  step_id, agent, model
  handoff_type: "handoff" | "delegate"
  parent_step_id: str | None      # delegate 복귀 지점 추적
  input_ref: str                  # 참조한 이전 산출물 경로
  output: str | None
  status: "ok" | "retry" | "failed" | "skipped"
  tokens_in, tokens_out: int
  cumulative_tokens: int          # 이 홉까지 누적 (스노볼 실측용)
  timestamp: str

Run:
  run_id, pattern, complaint_id
  max_tokens_total, max_hops       # 서킷브레이커 상한
  hops: list[Hop]
  final_status: "ok" | "halted_budget" | "halted_error" | "flagged"
```

`runs/<run-id>/NN_stage.json` 파일로 매 홉마다 저장. 이미 파일이 존재하면 재실행 시 스킵(resume).

### 에러 핸들링 정책

1. API 실패 → 지수 백오프 재시도 최대 3회
2. 3회 실패 → 폴백 모델로 1회 전환 시도
3. 그래도 실패:
   - **비핵심 단계(검색/research)**: 스킵-진행 + `status=skipped` 플래그, 파이프라인 계속
   - **핵심 단계(작성/검수)**: 중단(halt) + `final_status=halted_error`, 사람 확인 요청
4. delegate 루프(generate-verify/supervisor/hierarchical): `max_hops` 도달 시 강제 종료, `final_status=halted_budget`
5. `cumulative_tokens > max_tokens_total` 도달 시 즉시 halt (진행 중 단계 완료 후 다음 홉 차단)

## Consequences

* 좋음: 토큰 스노볼을 그래프로 그릴 수 있는 실측 데이터가 남는다 (Phase 6 비용 리포트의 기반).
* 좋음: `handoff_type`/`parent_step_id`로 delegate 패턴의 콜그래프를 복원할 수 있어 Phase 2의 supervisor/hierarchical 구현·디버깅이 쉬워진다.
* 나쁨: 단순 파이프라인만 필요한 경우에도 스키마가 다소 무겁다 — 그러나 6패턴을 동일 인터페이스로 비교해야 하는 요구상 불가피한 트레이드오프로 판단.
