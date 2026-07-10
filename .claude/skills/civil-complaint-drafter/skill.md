---
name: civil-complaint-drafter
description: "민원(번호·제목·본문)을 분류-검색-작성-검수 에이전트 팀으로 처리해 답변 초안을 생성하는 오케스트레이터 스킬. 6종 멀티에이전트 아키텍처 패턴(pipeline/fan-out-fan-in/expert-pool/generate-verify/supervisor/hierarchical) 중 하나를 선택해 실행한다."
---

# Civil Complaint Drafter — 민원 초안 생성 오케스트레이터

민원 답변 초안을 4개 에이전트(classifier → researcher → drafter → reviewer)의 협업으로 생성합니다.
같은 설계가 `src/complaint_agent/`에 실행 가능한 OpenRouter Python 앱으로도 구현되어 있습니다(ADR-0001).
Claude Code 내에서는 서브에이전트 팀으로, 실제 비용이 드는 대량 처리에는 Python CLI로 실행하십시오.

## 실행 방식

```bash
# Python 앱 (OpenRouter 실제 호출)
PYTHONPATH=src python -m complaint_agent run --pattern <6종 중 하나> --case <id>

# Claude Code 내에서는 이 스킬을 트리거하거나 자연어로 요청
```

## 에이전트 팀 구성 및 역할

| 에이전트 | 역할 | 산출물 |
|---|---|---|
| **classifier** | 8개 고정 카테고리 분류 | `01_classification.md` |
| **researcher** | 법령/과거답변/유사사례 조사(예시 도구) | `02_research.md` |
| **drafter** | 답변 초안 작성, 검수 피드백 반영 재작성 | `03_draft_vN.md` |
| **reviewer** | 근거·어투·누락·개인정보 검수, 승인/반려 판정 | `04_review_vN.md` |

## 6종 아키텍처 패턴 트리거 매핑 (ADR-0003)

| 사용자 요청 예 | 패턴 | 특징 |
|---|---|---|
| "민원 답변 초안 만들어줘" (기본) | **pipeline** | 고정 순서, 전부 핸드오프 |
| "근거를 여러 곳에서 찾아서 답변해줘" | **fan-out/fan-in** | 법령/과거답변/유사사례 병렬 조사 후 병합 |
| "이 민원은 전문 부서 담당자처럼 답변해줘" | **expert-pool** | 분류 결과로 도메인 전문가(주택/세무/교육/채용/일반)에 1회 동적 핸드오프 |
| "검수까지 꼼꼼하게, 반려되면 다시 써줘" | **generate-verify** | 작성↔검수 bounded 델리게이트 루프(최대 3회) |
| "전체 진행을 알아서 판단하며 처리해줘" | **supervisor** | 감독자가 매 턴 다음 단계 판단(재위임 가능) |
| "팀장 체계로 꼼꼼히, 리서치팀/작성팀 나눠서" | **hierarchical** | 최상위→리서치팀/작성팀 2단계 위임, 미승인 시 재위임 |

## 트리거 경계

**should-trigger** (이 스킬을 사용해야 하는 경우):
- "민원 답변(초안) 작성해줘", "이 민원 처리해줘", "민원 분류/검토해줘" 같은 요청
- 번호·제목·본문 형식(또는 이에 준하는 정보)을 가진 민원 텍스트가 주어졌을 때
- `data/sample_complaints.json`의 특정 케이스를 지정해 실행해달라는 요청

**NOT-trigger** (이 스킬을 사용하면 안 되는 경우):
- 일반적인 업무 보고서 작성 요청 → `82-report-generator` 하네스 영역
- 법령 조문 자체에 대한 심층 법률 자문(판례 해석 등) → 이 하네스의 researcher는 "예시 도구" 수준이며
  실제 법률 자문을 대체하지 않는다
- 민원 응대가 아닌 내부 정책 결정/ADR 작성 요청 → `62-adr-writer` 하네스 영역
- 이미 완성된 민원 답변의 맞춤법 교정만 필요한 경우 → 전체 파이프라인 대신 reviewer 단독 호출을 권장

## 데이터 전달 프로토콜

| 전략 | 방식 | 용도 |
|---|---|---|
| 파일 기반 | `runs/<run-id>/NN_stage.*` | 단계별 산출물 저장·재실행(resume) |
| Envelope | `run_<run-id>.json` | 전체 콜그래프·`cost_log`·최종 상태 |
| 메시지 기반 | SendMessage(Claude Code 내) | 실시간 델리게이트(수정 요청) 전달 |

파일명 컨벤션: `{순번}_{산출물}.{확장자}` (Python 앱 기준, ADR-0002).

## 에러 핸들링 (ADR-0002)

| 에러 유형 | 전략 |
|---|---|
| API 실패 | 지수 백오프 재시도 최대 3회 → 폴백 모델 1회 → 그래도 실패 시 아래 정책 |
| 근거 조사(researcher) 실패 | 비핵심 단계 — 스킵-진행, "근거 미확보" 명시 |
| 작성/검수(drafter·reviewer) 실패 | 핵심 단계 — 중단, 사람 확인 요청 |
| 재작업 한도 소진 (generate-verify/supervisor/hierarchical) | 최종 초안을 "사람 확인 필요"로 플래그하고 반환 |
| 비용 상한(`max_tokens_total`)/홉 상한(`max_hops`) 도달 | 즉시 halt (`halted_budget`) — 토큰 스노볼 방지 |

## 테스트 시나리오

### 정상 흐름
**프롬프트**: "이 민원에 대한 답변 초안을 pipeline으로 만들어줘" + 민원 1건 제공
**기대 결과**: classifier(카테고리 1개) → researcher(근거 요약) → drafter(4단 구성 초안) → reviewer(승인/반려)
가 순서대로 실행되고, `runs/<run-id>/`에 4개 산출물과 `run_<run-id>.json`(cost_log 포함)이 남는다.

### 기존 파일 활용 흐름
**프롬프트**: "이 분류 결과(`01_classification.md`)를 활용해서 나머지만 진행해줘"
**기대 결과**: classifier 단계를 건너뛰고 researcher부터 재개(Envelope의 resume 로직, ADR-0002).

### 에러 흐름
**프롬프트**: "이 민원 답변해줘" (근거 자료 전혀 없음, researcher 실패 상황)
**기대 결과**: researcher가 "근거 미확보"로 스킵-진행 표시 → drafter는 일반 절차 안내 수준으로 작성하고
"정확한 사항은 담당 부서 확인 필요"를 명시 → reviewer가 이를 반려 사유로 삼지 않고 정상 검수.

## 에이전트별 확장 스킬

| 확장 스킬 | 경로 | 대상 에이전트 | 역할 |
|---|---|---|---|
| (도메인 전문 스킬, 예: 주택/세무/교육/채용) | `skills_generated/<domain>/SKILL.md` | expert-pool의 specialist | Progressive Disclosure로 자동 생성(Phase 4, ADR-0005) — 현재는 `agents/specialists.py`에 인라인 정의됨 |
