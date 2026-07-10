# 0003. 6종 멀티에이전트 아키텍처 패턴 분류 기준 및 구현 방식

* Status: accepted
* Date: 2026-07-09

## Context and Problem Statement

사용자가 요구한 6종 패턴(pipeline/fan-out-fan-in/expert-pool/generate-verify/supervisor/hierarchical)은 일반적인 멀티에이전트 설계 문헌의 이름이며, 강의자료가 가르친 6종(싱글/네트워크/슈퍼바이저/슈퍼바이저as툴/계층형/커스텀)과는 다른 분류다. 아무 기준 없이 구현하면 supervisor·expert-pool·hierarchical 세 패턴이 전부 "LLM이 다음 할 일을 정한다"로 수렴해 실질적으로 구분되지 않는 위험이 있다(Plan 에이전트 검토에서 지적됨).

## Decision Drivers

* 강의가 명시적으로 가르친 **핸드오프(되돌아오지 않음) vs 델리게이트(재작업 위임)** 구분을 그대로 판별 축으로 쓰면 자연스럽게 구분된다.
* "계층 단수"(supervisor는 1단계, hierarchical은 ≥2단계) 축을 추가하면 세 패턴이 확실히 갈라진다.
* 6개를 매번 처음부터 구현하면 중복이 크므로(병렬 리서치, bounded 작성-검수 루프는 여러 패턴에서 재사용됨), 공유 헬퍼로 추출한다.

## Considered Options

패턴별로 구분 축을 어떻게 둘지 각각 검토했고, 최종적으로 아래 표로 확정했다.

## Decision Outcome

| 패턴 | 핸드오프/델리게이트 | 계층 단수 | 구현 |
|---|---|---|---|
| **pipeline** | 전부 핸드오프 | 없음(선형) | `patterns/pipeline.py` — 분류→검색→작성→검수 고정 순서 |
| **fan-out/fan-in** | 전부 핸드오프 | 없음(선형+병렬 분기) | `patterns/fanout_fanin.py` — 검색을 법령/과거답변/유사사례 3개 스레드로 병렬 실행 후 병합(fan-in), 이후 순차 |
| **expert-pool** | 1회 동적 핸드오프, 되돌아오지 않음 | 없음 | `patterns/expert_pool.py` — 분류 결과로 도메인 전문가(주택/세무/교육/채용/일반) 중 하나를 순수 로직으로 라우팅(비용 0) 후 1회 핸드오프 |
| **generate-verify** | 작성↔검수 델리게이트 루프 | 1단계 | `patterns/generate_verify.py` — `REWORK_LIMIT=3`으로 bounded |
| **supervisor** | 슈퍼바이저가 4단계 중 판단에 따라 위임(재위임 가능) | 1단계 | `patterns/supervisor.py` — 매 턴 상태를 보고 CLASSIFY/RESEARCH/DRAFT/REVIEW/DONE 중 하나를 판단, `MAX_SUPERVISOR_TURNS=8`로 bounded |
| **hierarchical** | 최상위가 팀장(리서치팀장/작성팀장)에게 위임, 팀장이 다시 워커에게 위임 | 2단계 | `patterns/hierarchical.py` — 최상위 슈퍼바이저가 "리서치팀"(병렬 서브 리서처)과 "작성팀"(작성↔검수 루프)에 각각 위임, 작성팀이 승인을 못 받으면 최상위가 리서치팀에 재위임(`TOP_MAX_CYCLES=2`) |

### 공유 헬퍼 (`patterns/_shared.py`)

중복을 피하기 위해 두 개의 공유 로직을 추출한다:
- `run_parallel_research(...)`: 법령/과거답변/유사사례 3개 조사를 `ThreadPoolExecutor`로 실제 동시 호출 후 결정적으로(LLM 호출 없이) 병합 — `fan-out/fan-in`과 `hierarchical`의 리서치팀에서 공용.
- `run_draft_review_loop(...)`: bounded 작성↔검수 델리게이트 루프 — `generate-verify`와 `hierarchical`의 작성팀에서 공용.

`generate_verify.py`도 이 공유 헬퍼를 쓰도록 리팩터링한다(1단계에서 만든 개별 구현은 이 헬퍼로 흡수).

### Mock 응답 하에서의 견고성

`supervisor`/`hierarchical`은 LLM이 특정 키워드(CLASSIFY/RESEARCH/DRAFT/REVIEW/DONE)로 답하길 기대하는데, dry-run mock 응답은 이 키워드를 포함하지 않는다. 파싱 실패 시 "아직 수행하지 않은 단계를 기본 순서(분류→검색→작성→검수)대로 진행"하는 폴백을 둬서, mock 모드에서도 배선이 끝까지 진행되도록 한다. 실제 LLM 연동 시(6단계)에는 진짜 판단이 반영된다.

## Consequences

* 좋음: 세 "판단형" 패턴(expert-pool/supervisor/hierarchical)이 핸드오프-델리게이트 축과 계층 축으로 명확히 구분되어, 검증체계(5단계)에서 패턴별 차이를 의미 있게 비교할 수 있다.
* 좋음: 공유 헬퍼 추출로 `hierarchical.py`가 `fanout_fanin`/`generate_verify`의 로직을 그대로 재사용해 중복 없이 "2단계 계층"만 얹는 형태로 구현된다.
* 나쁨: `supervisor`/`hierarchical`의 라우팅 판단을 저비용 모델에게 맡기면 키워드 프로토콜을 안 지킬 위험이 실제로 있다 — 폴백 로직으로 완화하되, 6단계 실측 시 재확인 필요(ADR-0007에서 다룸).
