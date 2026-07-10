# 민원 초안 생성 멀티 에이전트 (Civil Complaint Draft Generator)

GitHub: https://github.com/okokp7608-wq/civil-complaint-agent

민원(번호·제목·본문)을 입력받아 분류→검색→작성→검수 단계를 거쳐 답변 초안을 생성하는 멀티 에이전트 시스템.
`82-report-generator` 하네스의 3계층 구조(오케스트레이터/도메인 스킬/에이전트)를 계승하고, 6종 멀티에이전트
아키텍처 패턴을 지원하도록 설계했다. 상세 설계 배경은 `docs/adr/`의 ADR 문서와 `plan.md`를 참고.

> **진행 상태**: 전 6단계 완료. 6종 패턴 · 4개 도메인 에이전트 · Claude Code 하네스 트윈 · Progressive
> Disclosure 스킬 자동생성기 · 검증체계(트리거/드라이런/ablation)에 이어, `openai/gpt-4o-mini`로 실제
> OpenRouter 호출까지 검증 완료(`docs/adr/0007-model-selection-and-measured-results.md`).

## 설치

```bash
cd civil-complaint-agent
pip install -r requirements.txt
cp .env.example .env   # OPENROUTER_API_KEY 등을 채운다
```

## 실행

```bash
# API 비용 없이 배선만 검증 (mock LLM). --pattern은 아래 6종 중 선택:
#   pipeline | fanout_fanin | expert_pool | generate_verify | supervisor | hierarchical
PYTHONPATH=src python -m complaint_agent run --pattern pipeline --case 1 --dry-run
PYTHONPATH=src python -m complaint_agent run --pattern hierarchical --case 3 --dry-run

# 실제 OpenRouter 호출
PYTHONPATH=src python -m complaint_agent run --pattern pipeline --case 1

# expert-pool용 도메인 전문가 스킬을 Progressive Disclosure로 자동 생성 (skills_generated/)
PYTHONPATH=src python -m complaint_agent generate-skills --dry-run   # mock 초안, 비용 없음
PYTHONPATH=src python -m complaint_agent generate-skills --domain housing

# 검증체계
PYTHONPATH=src python -m complaint_agent validate --trigger-tests
PYTHONPATH=src python -m complaint_agent validate --dry-run-suite --case 1
PYTHONPATH=src python -m complaint_agent validate --ablation --dry-run   # 실제 점수는 --dry-run 없이(Phase 6)
```

> `hierarchical`처럼 홉 수가 많은 패턴은 기본 `MAX_HOPS=12`를 넘으면 `halted_budget`으로 안전 정지한다
> (서킷브레이커 정상 동작 — ADR-0002). 필요하면 `.env`의 `MAX_HOPS`를 올린다.

(Windows PowerShell에서는 `$env:PYTHONPATH="src"; python -m complaint_agent run ...` 형태로 실행)

실행 결과는 `runs/<run-id>/`에 단계별 JSON 파일과 `run_<run-id>.json`(전체 Envelope, `cost_log` 포함)으로 저장된다.

## 구조

```
civil-complaint-agent/
├── plan.md, docs/adr/                 — 강의 권장 plan.md + MADR 포맷 ADR
├── data/sample_complaints.json        — 합성 샘플 민원 8건 (인사혁신처 스타일)
├── src/complaint_agent/
│   ├── envelope.py                    — 핸드오프 데이터 스키마 (ADR-0002)
│   ├── llm_client.py                  — OpenRouter 클라이언트 (재시도/폴백/mock)
│   ├── config.py                      — .env 로더
│   ├── agents/                        — classifier/researcher/drafter/reviewer/specialists/supervisor
│   ├── patterns/                      — 6종 아키텍처 패턴 전부 구현 + _shared.py(공유 헬퍼)
│   ├── skills/generator.py            — Progressive Disclosure 스킬 자동 생성기
│   ├── validation/                    — trigger_tests, dry_run 스위트, skill_ablation
│   └── cli.py
├── skills_generated/<domain>/SKILL.md (+ reference/details.md, 본문이 길 때만)
├── .claude/                            — Claude Code 하네스 트윈 (agents 4종 + 오케스트레이터 skill.md)
└── runs/<run-id>/                      — 실행별 산출물 (git 추적 제외)
```

## 참고 문서
- `docs/adr/0001-overall-architecture.md` — 하이브리드(앱+하네스) 구조 선정 이유
- `docs/adr/0002-envelope-and-error-handling.md` — 핸드오프 스키마·에러 핸들링·비용 서킷브레이커
- `docs/adr/0003-six-pattern-taxonomy.md` — 6종 패턴 분류 기준(핸드오프 vs 델리게이트, 계층 단수)
- `docs/adr/0004-agent-boundaries-and-harness-twin.md` — 에이전트 책임 경계·분류 체계·하네스 트윈
- `docs/adr/0005-skill-generation-strategy.md` — 스킬 자동 생성 전략(메타데이터/본문/참조 계층 분리)
- `docs/adr/0006-validation-strategy.md` — 검증체계(트리거/드라이런/ablation) 기준
- `docs/adr/0007-model-selection-and-measured-results.md` — 최종 모델(`openai/gpt-4o-mini`) 선정과 실측 비용·품질 결과
