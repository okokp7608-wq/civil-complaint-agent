# 민원 초안 생성 멀티 에이전트 하네스

> **Civil Complaint Draft Generator**  
> 민원 내용을 입력하면 여러 AI Agent가 분류·조사·초안 작성·검증을 협업하고, 사람의 승인을 거쳐 최종 민원 답변 초안을 생성하는 멀티 에이전트 하네스입니다.

GitHub: https://github.com/okokp7608-wq/civil-complaint-agent

---

## 1. 하네스 주제

이 프로젝트의 주제는 **공공기관 민원 답변 초안 생성 업무를 위한 멀티 에이전트 팀 설계**입니다.

단일 LLM에 모든 업무를 맡기지 않고, 업무를 역할별 Agent로 분리하여 다음 흐름으로 처리합니다.

```text
[입력: 민원 번호·제목·본문]
              ↓
[분류 Agent: 민원 유형·위험도·담당 분야 판단]
              ↓
[조사 Agent / 분야별 전문가 Agent: 근거와 참고사항 수집]
              ↓
[작성 Agent: 민원 답변 초안 생성]
              ↓
[검증 Agent: 사실성·논리성·표현·개인정보·근거 검토]
              ↓
[사용자 승인 또는 재작성]
              ↓
[출력: 검증된 민원 답변 초안 + 단계별 실행 기록]
```

핵심은 단순한 문장 생성이 아니라, **AI Agent가 업무를 나누어 처리하고 결과를 상호 검증하는 구조**를 설계하는 것입니다.

---

## 2. 구성 목적

이 프로젝트는 `82-report-generator`의 하네스 개념을 민원 업무에 적용하여 다음 목적을 달성합니다.

1. 민원 초안 생성 업무를 여러 전문 Agent로 분리합니다.
2. Agent 사이의 입력과 출력을 표준 데이터 구조로 전달합니다.
3. 한 Agent의 오류가 전체 프로세스를 중단시키지 않도록 재시도·폴백·안전 정지를 지원합니다.
4. 여러 멀티 에이전트 아키텍처를 동일한 업무에 비교 적용할 수 있게 합니다.
5. 생성 결과를 검증 Agent와 사람의 승인 절차로 통제합니다.
6. 모든 주요 설계 결정을 ADR로 남겨 변경 이유와 영향을 추적합니다.
7. OpenRouter의 슬림·저비용 모델을 사용해 비용을 관리합니다.

---

## 3. 전체 구조

```text
civil-complaint-agent/
├── README.md                         # 프로젝트 설명·사용법·실행 예시
├── plan.md                           # 단계별 개발 계획과 승인 기준
├── requirements.txt                 # Python 의존성
├── .env.example                     # OpenRouter 및 안전 한도 설정 예시
│
├── data/
│   └── sample_complaints.json        # 테스트용 합성 민원 데이터
│
├── docs/adr/                         # Architecture Decision Record
│   ├── 0001-overall-architecture.md
│   ├── 0002-envelope-and-error-handling.md
│   ├── 0003-six-pattern-taxonomy.md
│   ├── 0004-agent-boundaries-and-harness-twin.md
│   ├── 0005-skill-generation-strategy.md
│   ├── 0006-validation-strategy.md
│   └── 0007-model-selection-and-measured-results.md
│
├── src/complaint_agent/
│   ├── agents/                       # 역할별 AI Agent
│   │   ├── classifier.py             # 민원 분류
│   │   ├── researcher.py             # 근거·참고사항 조사
│   │   ├── drafter.py                # 답변 초안 작성
│   │   ├── reviewer.py               # 결과 검증
│   │   ├── specialists.py            # 분야별 전문가 풀
│   │   └── supervisor.py             # 팀 감독 및 작업 배정
│   │
│   ├── patterns/                     # 6가지 멀티 에이전트 패턴
│   │   ├── pipeline.py
│   │   ├── fanout_fanin.py
│   │   ├── expert_pool.py
│   │   ├── generate_verify.py
│   │   ├── supervisor.py
│   │   └── hierarchical.py
│   │
│   ├── skills/
│   │   └── generator.py              # Progressive Disclosure 스킬 생성
│   │
│   ├── validation/
│   │   ├── trigger_tests.py           # 스킬·Agent 트리거 검증
│   │   ├── dry_run.py                # API 없이 전체 흐름 검증
│   │   └── skill_ablation.py         # With-skill vs Without-skill 비교
│   │
│   ├── envelope.py                   # Agent 간 공통 데이터 전달 규격
│   ├── llm_client.py                 # OpenRouter 호출·재시도·폴백
│   ├── config.py                     # 환경 변수 로딩
│   └── cli.py                        # 명령행 실행 인터페이스
│
├── skills_generated/                 # 자동 생성된 분야별 스킬
├── .claude/                          # Claude Code용 하네스 트윈
└── runs/                             # 단계별 실행 결과와 비용 기록
```

---

## 4. AI Agent 팀 구성

| Agent | 주요 역할 | 입력 | 출력 |
|---|---|---|---|
| Classifier | 민원 유형·위험도·담당 분야 분류 | 민원 원문 | 분류 결과, 라우팅 정보 |
| Researcher | 관련 근거와 확인사항 정리 | 민원 원문, 분류 결과 | 근거·주의사항 목록 |
| Specialist | 분야별 전문 관점 제공 | 분류된 민원 | 분야별 검토 의견 |
| Drafter | 기관 답변 형식으로 초안 작성 | 민원·근거·전문가 의견 | 민원 답변 초안 |
| Reviewer | 사실성·논리성·표현·개인정보 검증 | 답변 초안 | 승인, 보완 요구, 검증 의견 |
| Supervisor | Agent 선택·작업 위임·중단 판단 | 전체 실행 상태 | 다음 작업 지시 또는 종료 결정 |

### 공통 데이터 전달 규격

Agent 사이의 데이터는 `Envelope` 구조로 전달됩니다.

```text
민원 원문
+ 현재 처리 단계
+ 분류 및 조사 결과
+ 생성된 초안
+ 검증 의견
+ 오류 및 재시도 정보
+ 사용 토큰·비용 기록
+ 최종 상태
```

이 구조를 사용하면 Agent가 바뀌더라도 동일한 인터페이스로 협업할 수 있습니다.

---

## 5. 지원하는 6가지 멀티 에이전트 아키텍처

### 5.1 Pipeline

Agent를 정해진 순서로 실행합니다.

```text
분류 → 조사 → 작성 → 검증
```

- 가장 단순하고 이해하기 쉬운 기본 구조
- 단계별 책임과 결과 추적이 명확함
- 표준 민원 처리에 적합

### 5.2 Fan-out / Fan-in

하나의 민원을 여러 Agent가 동시에 분석한 뒤 결과를 통합합니다.

```text
                  ┌→ 법·제도 관점 ─┐
민원 → 분류/분산 ├→ 업무 관점 ───┼→ 결과 통합 → 작성 → 검증
                  └→ 표현 관점 ───┘
```

- 다양한 관점을 빠르게 수집
- 병렬 처리로 전체 시간을 줄일 수 있음
- 결과 통합 기준이 중요함

### 5.3 Expert Pool

민원 분류 결과에 따라 적절한 분야별 전문가 Agent를 선택합니다.

```text
민원 → 분류 → 전문가 라우터 → 인사/채용/주택/세무 등 전문가 → 작성 → 검증
```

- 업무 분야별 전문성을 강화
- 모든 민원에 모든 전문가를 호출하지 않아 비용 절감
- Progressive Disclosure 스킬과 결합

### 5.4 Generate–Verify

초안을 생성하고 검증하며, 기준 미달이면 다시 작성합니다.

```text
초안 생성 → 검증 ── 승인 → 출력
              └─ 보완 요구 → 재작성 → 재검증
```

- 결과 품질을 높이는 데 유리
- 반복 횟수 증가 시 토큰과 비용이 커질 수 있음
- `MAX_HOPS`, `MAX_TOKENS_TOTAL`로 반복을 제한

### 5.5 Supervisor

감독 Agent가 현재 상태를 보고 다음에 호출할 Agent를 결정합니다.

```text
민원 → Supervisor → 필요한 Agent 선택·호출 → 상태 확인 → 다음 작업 결정
```

- 고정 순서가 아닌 동적 업무 배정 가능
- 복잡하거나 예외가 많은 민원에 적합
- 감독자의 판단 기준과 종료 조건이 중요함

### 5.6 Hierarchical Delegation

상위 감독자가 하위 팀 또는 전문 Agent에게 단계적으로 업무를 위임합니다.

```text
총괄 Supervisor
      ↓
분야별 Team Lead
      ↓
조사·작성·검증 Agent
      ↓
상위 단계 보고 및 최종 통합
```

- 조직 구조와 유사한 계층형 협업
- 복잡한 업무를 세부 과제로 나누기 쉬움
- 호출 단계가 많아 비용·홉 수 관리가 필요함

---

## 6. Progressive Disclosure 기반 스킬 자동 생성

분야별 지식을 항상 프롬프트에 모두 넣으면 컨텍스트가 커지고 비용이 증가합니다. 이 프로젝트는 필요한 정보만 단계적으로 공개하는 **Progressive Disclosure** 패턴을 사용합니다.

```text
1단계: 스킬 이름·설명·트리거만 노출
2단계: 해당 민원에 스킬이 필요할 때 핵심 지침 로딩
3단계: 세부 근거나 예시가 필요할 때 reference 문서 추가 로딩
```

자동 생성 결과 예시:

```text
skills_generated/
├── general_hr/SKILL.md
├── recruitment/SKILL.md
├── housing/SKILL.md
├── education/SKILL.md
└── tax/SKILL.md
```

효과:

- 불필요한 컨텍스트 사용 감소
- 분야별 전문 지침 재사용
- Agent 트리거 조건 명확화
- 스킬 유무에 따른 품질 차이 측정 가능

---

## 7. 오케스트레이션과 안전장치

### Agent 간 데이터 전달

각 Agent는 앞 단계 결과를 `Envelope`로 전달받아 필요한 필드만 갱신합니다. 단계별 결과는 `runs/<run-id>/`에 JSON으로 저장됩니다.

### 에러 핸들링

- OpenRouter 호출 실패 시 재시도
- 기본 모델 실패 시 폴백 모델 사용
- Agent 오류를 Envelope에 기록
- 최대 홉 수 초과 시 안전 정지
- 최대 토큰 한도 초과 시 안전 정지
- 드라이런에서는 실제 API 호출 없이 mock 응답 사용

### 팀 조율 프로토콜

```text
1. Orchestrator가 현재 상태와 목표를 확인한다.
2. 실행할 Agent와 패턴을 선택한다.
3. Agent는 공통 Envelope를 입력받는다.
4. Agent 결과와 오류를 Envelope에 기록한다.
5. Reviewer 또는 Supervisor가 다음 단계를 판단한다.
6. 승인 기준을 충족하면 종료하고, 미달이면 제한 범위에서 재시도한다.
```

---

## 8. ADR과 단계별 사용자 승인

ADR은 **Architecture Decision Record**, 즉 주요 설계 결정과 그 이유를 기록하는 문서입니다.

이 프로젝트는 중요한 변경을 다음 순서로 진행하는 것을 원칙으로 합니다.

```text
요구사항 확인
    ↓
ADR 초안 작성
    ↓
선택지·장점·단점·영향 설명
    ↓
사용자 승인
    ↓
구현
    ↓
테스트 결과 제시
    ↓
사용자 최종 승인
    ↓
ADR 상태를 accepted로 변경
```

### 승인 게이트

| 단계 | 승인 대상 | 승인 전 수행하지 않는 작업 |
|---|---|---|
| Gate 1 | 전체 아키텍처 | 핵심 구조 구현 |
| Gate 2 | Agent 역할과 경계 | Agent 프롬프트·클래스 확정 |
| Gate 3 | 패턴 선택과 실행 순서 | 오케스트레이션 확정 |
| Gate 4 | 스킬 구조와 트리거 | 스킬 대량 생성 |
| Gate 5 | 검증 기준 | 품질 평가 결과 확정 |
| Gate 6 | 모델·비용·운영 한도 | 실제 운영 배포 |

현재 프로젝트의 설계 근거는 `docs/adr/0001`부터 `0007`까지 기록되어 있습니다. 새로운 변경을 할 때는 기존 ADR을 임의로 덮어쓰지 않고 새 ADR을 추가합니다.

---

## 9. LLM 설정: OpenRouter 슬림 모델

이 프로젝트는 OpenRouter API를 사용하며, `.env`에서 저비용 슬림 모델을 선택할 수 있습니다.

```env
OPENROUTER_API_KEY=sk-or-v1-본인키
OPENROUTER_MODEL_DEFAULT=openai/gpt-4o-mini
OPENROUTER_MODEL_FALLBACK=openai/gpt-4o-mini

MAX_RETRIES=3
MAX_HOPS=12
MAX_TOKENS_TOTAL=200000
MOCK_LLM=0
```

`openai/gpt-4o-mini`는 이 프로젝트에서 실제 검증에 사용한 기본 예시입니다. OpenRouter에서 이용 가능한 다른 슬림 모델을 사용하려면 두 모델 ID를 변경하면 됩니다.

> API 키가 포함된 `.env`는 Git에 커밋하지 마십시오.

---

## 10. 설치 방법

### 공통

```bash
git clone https://github.com/okokp7608-wq/civil-complaint-agent.git
cd civil-complaint-agent
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
Copy-Item .env.example .env
$env:PYTHONPATH="src"
python -m complaint_agent --help
```

### macOS / Linux

```bash
cp .env.example .env
export PYTHONPATH=src
python -m complaint_agent --help
```

`.env` 파일에 OpenRouter API 키와 사용할 모델을 설정합니다.

---

## 11. 사용 방법

### 11.1 API 비용 없이 전체 흐름 확인

```bash
PYTHONPATH=src python -m complaint_agent run --pattern pipeline --case 1 --dry-run
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m complaint_agent run --pattern pipeline --case 1 --dry-run
```

### 11.2 실제 OpenRouter 모델로 실행

```bash
PYTHONPATH=src python -m complaint_agent run --pattern pipeline --case 1
```

### 11.3 다른 아키텍처 패턴 실행

```bash
PYTHONPATH=src python -m complaint_agent run --pattern fanout_fanin --case 1 --dry-run
PYTHONPATH=src python -m complaint_agent run --pattern expert_pool --case 7 --dry-run
PYTHONPATH=src python -m complaint_agent run --pattern generate_verify --case 2 --dry-run
PYTHONPATH=src python -m complaint_agent run --pattern supervisor --case 4 --dry-run
PYTHONPATH=src python -m complaint_agent run --pattern hierarchical --case 3 --dry-run
```

지원 패턴:

```text
pipeline
fanout_fanin
expert_pool
generate_verify
supervisor
hierarchical
```

### 11.4 분야별 스킬 자동 생성

```bash
# API 호출 없이 스킬 구조 확인
PYTHONPATH=src python -m complaint_agent generate-skills --dry-run

# 특정 분야 스킬 생성
PYTHONPATH=src python -m complaint_agent generate-skills --domain housing
```

### 11.5 검증 실행

```bash
# 스킬 및 Agent 트리거 검증
PYTHONPATH=src python -m complaint_agent validate --trigger-tests

# 6개 패턴의 전체 배선 검증
PYTHONPATH=src python -m complaint_agent validate --dry-run-suite --case 1

# 스킬 적용 전후 비교
PYTHONPATH=src python -m complaint_agent validate --ablation --dry-run
```

---

## 12. 실행 예시

### 입력 예시

```json
{
  "id": 7,
  "title": "공무원 주택자금대출 지원 대상 문의",
  "body": "무주택 공무원이 이용할 수 있는 주택자금대출의 지원 조건과 신청 절차를 알려 주세요."
}
```

### Expert Pool 처리 예시

```text
1. Classifier
   - 민원 분야: 주택·복지
   - 권장 전문가: housing

2. Router
   - housing 전문 Agent 선택

3. Housing Specialist
   - 지원 대상, 확인 필요 서류, 유의사항 정리

4. Drafter
   - 공식 민원 답변 형식으로 초안 작성

5. Reviewer
   - 단정적 표현, 근거 부족, 개인정보 포함 여부 검토

6. Output
   - 검증 상태와 함께 최종 초안 저장
```

### 출력 예시

```text
안녕하십니까. 귀하께서 문의하신 주택자금대출 지원 대상 및 신청 절차에 대해 다음과 같이 안내드립니다.

지원 가능 여부는 재직 상태, 무주택 여부, 소득 및 대출 기준 등 관계 규정과 해당 기관의 운영 기준에 따라 달라질 수 있습니다. 정확한 대상 여부와 제출 서류는 소속 기관의 복지 담당 부서 또는 해당 대출 운영기관을 통해 확인하시기 바랍니다.

추가로 확인이 필요한 사항이 있는 경우 담당 부서에 문의해 주시면 안내드리겠습니다. 감사합니다.
```

실제 결과에는 초안뿐 아니라 분류 결과, 조사 내용, 검증 의견, 사용 토큰, 오류 기록이 함께 저장됩니다.

---

## 13. 실행 결과 저장 구조

```text
runs/<pattern>_<case>_<run-id>/
├── 01_classification.json
├── 02_research_or_routing.json
├── 03_draft.json
├── 04_review.json
└── run_<run-id>.json
```

`run_<run-id>.json`에는 다음 정보가 포함됩니다.

- 원본 민원
- 선택된 아키텍처 패턴
- Agent별 입력과 출력
- 현재 상태와 최종 상태
- 오류 및 재시도 내역
- 누적 홉 수
- 토큰 및 비용 로그
- 검증 결과

---

## 14. 검증 체계

### 14.1 트리거 검증

올바른 민원 분야에서 올바른 Agent 또는 스킬이 호출되는지 확인합니다.

예:

```text
주택자금대출 문의 → housing 스킬 호출
채용시험 문의 → recruitment 스킬 호출
연가·휴가 문의 → general_hr 스킬 호출
```

### 14.2 드라이런 테스트

실제 API 비용 없이 mock LLM으로 다음 항목을 검증합니다.

- 6개 패턴의 실행 가능 여부
- Agent 간 Envelope 전달
- 결과 파일 생성
- 최대 홉 수 안전 정지
- 오류 처리와 재시도 흐름

### 14.3 With-skill vs Without-skill 비교

같은 민원을 다음 두 조건으로 실행해 결과를 비교합니다.

```text
A. 도메인 스킬을 적용한 Agent
B. 도메인 스킬을 적용하지 않은 Agent
```

비교 항목:

- 사실성과 구체성
- 민원 분야 적합성
- 표현의 명확성
- 검증 통과율
- 토큰 사용량
- 예상 비용

### 14.4 생성–검증 품질 기준

Reviewer는 최소한 다음 항목을 확인합니다.

- 민원 질문에 직접 답했는가
- 확인되지 않은 내용을 사실처럼 단정하지 않았는가
- 필요한 근거와 확인 경로가 포함되었는가
- 개인정보나 민감정보를 불필요하게 포함하지 않았는가
- 공공기관 답변에 적절한 문체인가
- 내부 모순이나 누락이 없는가

---

## 15. 바이브 코딩 적용 방식

이 프로젝트는 자연어 요구사항을 기반으로 빠르게 구조를 만들고, 실행 결과를 보며 반복 개선하는 바이브 코딩 방식을 적용했습니다.

```text
요구사항 작성
    ↓
AI와 아키텍처 초안 생성
    ↓
ADR로 설계 결정 기록
    ↓
최소 실행 구조 구현
    ↓
드라이런으로 빠르게 검증
    ↓
오류와 품질 문제 수정
    ↓
실제 슬림 모델로 비용·품질 측정
    ↓
사용자 승인 후 다음 단계 진행
```

바이브 코딩을 사용하더라도 다음 원칙을 유지합니다.

- AI가 생성한 코드를 검증 없이 운영에 사용하지 않음
- 주요 결정은 ADR에 기록
- 작은 단위로 실행하고 결과 확인
- 실제 API 호출 전 드라이런 수행
- 토큰·홉·재시도 한도 설정
- 최종 민원 답변은 담당자의 검토와 승인 후 사용

---

## 16. 현재 구현 및 측정 결과

- 6가지 멀티 에이전트 패턴 구현 완료
- Classifier, Researcher, Drafter, Reviewer, Specialist, Supervisor 구현 완료
- Claude Code 하네스 트윈 구성 완료
- Progressive Disclosure 스킬 생성기 구현 완료
- 트리거·드라이런·스킬 비교 검증 구현 완료
- OpenRouter 실제 호출 검증 완료
- 단계별 JSON 실행 기록 및 비용 로그 저장 완료

실측에서는 Generate–Verify가 단순 Pipeline보다 더 많은 토큰을 사용했습니다. 반복 검증은 품질 향상에 도움이 될 수 있지만 비용이 증가하므로 반드시 최대 홉과 토큰 한도를 설정해야 합니다. 자세한 결과는 `docs/adr/0007-model-selection-and-measured-results.md`를 참고하십시오.

---

## 17. 운영 시 주의사항

1. 생성 결과는 **민원 답변 초안**이며 자동 확정 답변이 아닙니다.
2. 법령·규정·기관 내부 기준은 담당자가 최신 내용을 확인해야 합니다.
3. 실제 민원 데이터 사용 시 개인정보 비식별화와 접근 통제가 필요합니다.
4. OpenRouter 모델과 가격은 운영 시점에 다시 확인해야 합니다.
5. Generate–Verify와 Hierarchical 패턴은 비용 증가 가능성이 높습니다.
6. `.env`, API 키, 실제 민원 원문, 실행 로그를 공개 저장소에 커밋하지 마십시오.
7. 최종 출력 전 Reviewer 검증과 사람의 승인을 모두 거치는 것을 권장합니다.

---

## 18. 참고 ADR

- `ADR-0001` — 전체 하이브리드 아키텍처
- `ADR-0002` — Envelope, 재시도, 오류 처리, 비용 서킷브레이커
- `ADR-0003` — 6가지 멀티 에이전트 패턴 분류
- `ADR-0004` — Agent 역할 경계와 Claude Code 하네스 트윈
- `ADR-0005` — Progressive Disclosure 스킬 생성 전략
- `ADR-0006` — 트리거·드라이런·스킬 비교 검증 전략
- `ADR-0007` — OpenRouter 모델 선택 및 실제 비용·품질 측정

---

## 19. 핵심 요약

```text
입력
  민원 번호·제목·본문
    ↓
처리
  분류 → 조사/전문가 분석 → 초안 작성
    ↓
검증
  사실성·논리성·표현·개인정보·근거 검토
    ↓
승인
  기준 미달 시 재작성, 기준 충족 시 사용자 승인
    ↓
출력
  민원 답변 초안 + 단계별 JSON + 비용·오류·검증 기록
```

이 프로젝트의 핵심은 **좋은 문장을 한 번 생성하는 것**이 아니라, **전문 Agent가 역할을 나누고, 결과를 검증하며, 사람이 통제할 수 있는 민원 업무 처리 구조를 만드는 것**입니다.
