"""Thin Anthropic API wrapper with retries. Every model call goes through here."""
from __future__ import annotations

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

_RETRYABLE = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.APIStatusError,
)


class LLM:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def complete(self, model: str, prompt: str, max_tokens: int = 500) -> str:
        msg = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
