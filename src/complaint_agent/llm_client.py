"""OpenRouter 클라이언트 래퍼. 재시도, 폴백 모델, mock(dry-run) 모드를 지원한다. ADR-0002 에러 핸들링 정책 구현."""
from __future__ import annotations

import time
from dataclasses import dataclass

from .config import Config


class LLMCallFailed(Exception):
    pass


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    model_used: str
    status: str  # "ok" | "failed"


def _mock_response(system: str, user: str) -> str:
    """dry-run용 결정적 mock 응답 — 실제 API 비용 없이 배선을 검증한다."""
    return f"[MOCK:{system[:12].strip()}] input={len(user)}chars 기반 생성 결과"


class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self._client = None
        if not config.mock_llm:
            from openai import OpenAI  # 지연 임포트: mock 모드에서는 openai 패키지 불필요

            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=config.openrouter_api_key,
            )

    def _call_once(self, model: str, system: str, user: str) -> LLMResult:
        if self.config.mock_llm:
            text = _mock_response(system, user)
            return LLMResult(
                text=text,
                tokens_in=max(1, len(system + user) // 4),
                tokens_out=max(1, len(text) // 4),
                model_used=model,
                status="ok",
            )

        resp = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        usage = resp.usage
        return LLMResult(
            text=resp.choices[0].message.content or "",
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            model_used=model,
            status="ok",
        )

    def complete(self, system: str, user: str, model: str | None = None) -> LLMResult:
        """지수 백오프 재시도(최대 max_retries) 후 폴백 모델로 1회 전환, 그래도 실패하면 status=failed 반환."""
        target_model = model or self.config.model_default
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                return self._call_once(target_model, system, user)
            except Exception as exc:  # OpenRouter/네트워크 오류 전반
                last_error = exc
                if attempt < self.config.max_retries - 1:
                    time.sleep(min(2**attempt, 8))

        if target_model != self.config.model_fallback:
            try:
                return self._call_once(self.config.model_fallback, system, user)
            except Exception as exc:
                last_error = exc

        return LLMResult(text="", tokens_in=0, tokens_out=0, model_used=target_model, status="failed")
