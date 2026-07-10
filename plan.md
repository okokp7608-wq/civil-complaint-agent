# 민원 초안 생성 멀티 에이전트 — plan

## 목표
- 민원(번호·제목·본문) → 답변 초안 자동 생성
- `82-report-generator` 하네스 컨벤션을 계승해, 6종 멀티에이전트 아키텍처 패턴을 지원하는 재사용 가능한 프레임워크로 고도화

## 범위
- 분류 → 검색(예시 도구) → 작성 → 검수, 6종 패턴(pipeline/fan-out-fan-in/expert-pool/generate-verify/supervisor/hierarchical)으로 조립 가능
- Progressive Disclosure 스킬 자동 생성, 오케스트레이션(핸드오프/에러핸들링/비용 서킷브레이커), 검증체계(트리거/드라이런/with-without 비교)
- 모델: OpenRouter의 슬림(저가) 모델, `.env`로 설정
- 산출물: 실행 가능한 Python 앱(`src/complaint_agent/`) + Claude Code 하네스(`.claude/`) 병행

## 단계 (각 단계 = ADR 작성 → 구현 → 사용자 승인)
1. 스캐폴딩 + 코어 프레임워크 + pipeline/generate-verify 워킹 스켈레톤 — ADR-0001, 0002
2. 나머지 4개 패턴(fan-out/fan-in, expert-pool, supervisor, hierarchical) + CLI — ADR-0003
3. 실제 도메인 에이전트 4종 확정 + Claude Code 하네스(.claude/agents, skills) — ADR-0004
4. Progressive Disclosure 스킬 자동 생성기 + 도메인 전문 스킬 생성 — ADR-0005
5. 검증체계(트리거 검증/드라이런/with-vs-without-skill 비교) — ADR-0006
6. 실제 OpenRouter 연동 실행 + 비용·품질 리포트 + 최종 정리 — ADR-0007

## 완료 기준
- 민원 1건을 6개 패턴 중 아무거나로 실행하면 답변 초안 1건과 `runs/<run-id>/`에 단계별 산출물·`cost_log`가 남는다 ✅
- `--dry-run`으로 API 비용 없이 전체 배선을 검증할 수 있다 ✅
- with-skill / without-skill 비교 리포트가 산출된다 ✅ (실측: ADR-0007)

## 변경 이력
- 2026-07-09: 프로젝트 시작. Plan 에이전트 검토를 반영해 dry-run/트리거 테스트 스켈레톤을 1단계로 앞당김(원래는 5단계 예정) — 이유: 6개 패턴 구현 전에 배선을 먼저 검증해야 뒷단계 디버깅 비용이 줄어듦.
- 2026-07-09: 실제 민원 예제 40건 파일이 없어, 인사혁신처 스타일 합성 샘플 8건으로 대체(`data/sample_complaints.json`) — 이유: 사용자 확인, 실제 파일 확보 전까지 개발 진행 필요.
- 2026-07-10: `Run.would_exceed_hops()`를 추가하고 `hierarchical`/`fanout_fanin`이 `run_parallel_research`(4홉 블록)를 호출하기 전 헤드룸을 미리 확인하도록 수정 — 이유: 드라이런 검증 스위트에서 `hierarchical`이 `max_hops`를 12→16으로 넘어서는 것을 발견함(서킷브레이커가 블록 단위 홉 추가를 사전에 예측하지 못했던 설계 공백). 수정 후 정확히 `max_hops` 경계에서 정지함을 재확인.
- 2026-07-10: CLI 출력에서 Windows cp949 콘솔이 em-dash(—) 등을 인코딩하지 못해 `UnicodeEncodeError`로 죽는 문제 발견 → `cli.py` 진입점에서 stdout/stderr를 UTF-8로 강제 reconfigure — 이유: 트리거 테스트 실행 중 실제로 크래시가 재현됨.
- 2026-07-10: 6단계 완료. `OPENROUTER_MODEL_DEFAULT/FALLBACK`을 `openai/gpt-4o-mini`로 확정하고 실제 API로 pipeline/expert-pool/generate-verify 및 3건 ablation을 실행 — 분류·라우팅이 실제 LLM 출력에서도 설계대로 동작했고, generate-verify 1회 실행 비용이 pipeline의 약 2.4배(토큰 스노볼 실측)임을 확인. 상세는 ADR-0007.
