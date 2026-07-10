# 0007. 최종 모델 선정 및 실측 결과

* Status: accepted
* Date: 2026-07-10

## Context and Problem Statement

1~5단계는 전부 mock LLM(dry-run)으로 배선만 검증했다. 강의 4부의 실습 취지("값싼 모델로도 되는지 미리
체감")를 만족하려면 실제 OpenRouter 호출로 비용과 품질을 실측해야 한다.

## Decision Drivers

* 사용자가 `.env`에 실제 OpenRouter API 키를 준비했고, 모델로 `openai/gpt-4o-mini`를 지정했다.
* 비용을 통제하기 위해 8건 전체 × 6패턴(48회) 실행 대신, 대표성 있는 부분집합만 실제 호출했다.

## Decision Outcome

**모델**: `OPENROUTER_MODEL_DEFAULT=OPENROUTER_MODEL_FALLBACK=openai/gpt-4o-mini`로 확정(`.env`, `.env.example`).

### 실측 1 — 패턴별 비용 (pipeline vs generate-verify, 토큰 스노볼 검증)

| 패턴 | 케이스 | 홉 수 | 최종 누적 토큰 | 결과 |
|---|---|---|---|---|
| pipeline | 1 (연차휴가) | 4 | 2,396 | flagged (근거·개인정보 지적) |
| expert-pool | 7 (주택자금대출) | 4 | 1,309 | flagged, **라우팅 실측 성공**: classifier→"주택·복지"→router가 `housing` 전문가로 정확히 핸드오프 |
| generate-verify | 2 (초과근무수당) | 8 | 5,659 | flagged (REWORK_LIMIT 3회 소진) |

generate-verify의 홉별 누적 토큰(211→823→1,652→2,261→3,286→3,949→4,975→5,659)을 보면 재작성마다
drafter의 `tokens_in`이 594→742→747로 늘어난다 — 이전 검수 피드백이 누적 입력에 그대로 쌓이기 때문이다.
**강의 7부의 "토큰 스노볼" 경고가 실측으로 확인됨**: generate-verify 1회 실행 비용(5,659토큰)이 단순
pipeline(2,396토큰)의 약 2.4배다.

### 실측 2 — With-skill vs Without-skill Ablation (3건, judge 점수 3~15)

| 민원ID | 분류 | 라우팅된 전문가 | with 토큰 | without 토큰 | with 점수 | without 점수 |
|---|---|---|---|---|---|---|
| 1 | 복무·휴가 | general_hr | 642 | 604 | 14 | 13 |
| 4 | 채용 | recruitment | 705 | 584 | 13 | 13 |
| 7 | 주택·복지 | housing | 721 | 584 | 12 | 12 |

세 건 모두 분류 결과가 ADR-0004의 8개 고정 카테고리와 정확히 일치했고, expert-pool 라우팅도 의도한
전문가로 정확히 연결됐다. with-skill 쪽이 토큰을 약 15~20% 더 쓰지만 품질 점수는 같거나 근소하게 높다
— **표본이 3건뿐이라 통계적으로 유의미하다고 주장할 수는 없으나, 방향성은 "도메인 스킬이 비용 대비
손해는 아니다"에 부합**한다. 전체 8건 × judge 반복 채점으로 확장하면 더 신뢰도 높은 결론을 낼 수 있다
(향후 과제).

## Consequences

* 좋음: mock으로만 검증했던 5단계까지의 설계(핸드오프/델리게이트 구분, 비용 서킷브레이커, 분류-라우팅
  연동)가 실제 LLM 호출에서도 그대로 성립함을 확인했다.
* 좋음: generate-verify/hierarchical처럼 델리게이트 루프가 있는 패턴을 실제 운영에 쓸 때는 반드시
  `MAX_HOPS`/`MAX_TOKENS_TOTAL` 서킷브레이커를 활성 상태로 둬야 한다는 근거가 실측으로 확보됐다.
* 나쁨: ablation 표본이 작아(3건) with-skill의 품질 우위를 확정할 수 없다 — 전체 8건 실측 확장은 이후
  과제로 남긴다.
