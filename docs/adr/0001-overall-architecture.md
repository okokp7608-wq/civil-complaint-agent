# 0001. 전체 아키텍처 — 하이브리드 (실행 가능한 OpenRouter 앱 + Claude Code 하네스)

* Status: accepted
* Date: 2026-07-09

## Context and Problem Statement

행안부 고급인증과정 8주차 과제는 "민원 초안 생성 멀티 에이전트"를 OpenRouter의 값싼 모델로 직접 만들어보는 실습이다(강의자료 4부). 동시에 이 프로젝트는 `82-report-generator` 하네스(오케스트레이터 스킬 + 도메인 확장 스킬 + 에이전트의 3계층 구조)를 참고해 "고도화"하라는 요구도 받았다. 두 요구는 표현 형식이 다르다 — 전자는 실제로 동작하는 코드(과금·API 호출이 실재해야 증명 가능), 후자는 Claude Code의 서브에이전트/스킬 문서 컨벤션이다. 어느 하나만 만들면 다른 쪽 요구를 충족하지 못한다.

## Decision Drivers

* 과제 제출물은 "실행해서 결과가 나오는 것"이어야 한다(강의 마무리 과제: GitHub 업로드 + 어느 정도 동작).
* `82-report-generator`/`62-adr-writer` 컨벤션을 이 프로젝트의 뼈대로 명시적으로 계승해야 "고도화"라는 요구를 충족한다.
* 강의 취지상 LangGraph 등 기성 프레임워크에 기대지 않고 직접 이해하며 구현해야 한다.

## Considered Options

1. Claude Code 하네스만 제작 (.claude/agents + skills)
2. 실행 가능한 OpenRouter Python 앱만 제작
3. 둘을 병행 — 같은 설계를 두 형태로 표현 (하네스는 설계 문서 + Claude Code 내 서브에이전트 실행 경로, 앱은 실제 OpenRouter 호출 경로)

## Decision Outcome

**옵션 3 채택.** `src/complaint_agent/`에 프레임워크 자체(에이전트/패턴/스킬생성/검증)를 순수 Python으로 구현하고, `.claude/`에는 동일한 에이전트 4종·오케스트레이터 스킬을 Claude Code 컨벤션으로 문서화한다. 두 표현은 같은 개념 모델(Envelope, 4단계 에이전트, 6종 패턴)을 공유하므로 유지보수 이중화 부담이 적다.

### 디렉토리 구조

```
civil-complaint-agent/
├── plan.md, README.md, requirements.txt, .env.example, .gitignore
├── data/sample_complaints.json
├── docs/adr/000X-*.md
├── src/complaint_agent/{llm_client,envelope,config}.py, agents/, patterns/, skills/, validation/, cli.py
├── skills_generated/<domain>/SKILL.md
├── .claude/{CLAUDE.md, agents/*.md, skills/civil-complaint-drafter/skill.md}
└── runs/<run-id>/
```

## Consequences

* 좋음: 강의 과제(실동작 앱)와 하네스 컨벤션 준수(설계 문서화)를 동시에 만족.
* 좋음: `runs/<run-id>/`가 `82-report-generator`의 `_workspace/` 파일 기반 협업을 계승 — 단계별 산출물을 파일로 남겨 디버깅·복기가 쉬움.
* 나쁨: 두 표현(코드 vs .claude 문서)의 내용이 어긋나지 않도록 각 단계마다 함께 갱신해야 하는 부담이 생김 → Phase 3에서 두 표현을 같은 단계로 묶어 작성하여 완화.
