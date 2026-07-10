"""환경변수(.env) 및 실행 설정 로더."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    openrouter_api_key: str
    model_default: str
    model_fallback: str
    max_retries: int
    max_hops: int
    max_tokens_total: int
    mock_llm: bool

    @staticmethod
    def load(mock_override: bool | None = None) -> "Config":
        mock = os.environ.get("MOCK_LLM", "0") == "1" if mock_override is None else mock_override
        return Config(
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            model_default=os.environ.get("OPENROUTER_MODEL_DEFAULT", "openai/gpt-5.5"),
            model_fallback=os.environ.get("OPENROUTER_MODEL_FALLBACK", "openai/gpt-5.5"),
            max_retries=int(os.environ.get("MAX_RETRIES", "3")),
            max_hops=int(os.environ.get("MAX_HOPS", "12")),
            max_tokens_total=int(os.environ.get("MAX_TOKENS_TOTAL", "200000")),
            mock_llm=mock,
        )
