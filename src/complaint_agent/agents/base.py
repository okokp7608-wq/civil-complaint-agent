"""에이전트 기본 클래스 — 페르소나 + (선택) 도구 + 모델을 묶는다.
강의 핵심: "페르소나만 주면 챗봇, 도구까지 줘야 에이전트" — tools는 실제 검색/조회 콜백 리스트.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..llm_client import LLMClient, LLMResult


@dataclass
class Agent:
    name: str
    persona: str  # system prompt
    model: Optional[str] = None  # None이면 config.model_default 사용
    tools: list[Callable[[str], str]] = field(default_factory=list)

    def run(self, llm_client: LLMClient, user_content: str) -> LLMResult:
        tool_notes = ""
        if self.tools:
            tool_notes = "\n\n[도구 결과]\n" + "\n".join(tool(user_content) for tool in self.tools)
        return llm_client.complete(system=self.persona, user=user_content + tool_notes, model=self.model)
