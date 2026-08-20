"""LLM client abstraction.

Production note: agents should depend on this interface instead of importing an SDK directly.
"""

from dataclasses import dataclass

import openai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from multi_agent_research_lab.core.config import Settings, get_settings


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


# Pricing per 1M tokens (USD): (input_price, output_price)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
}


class LLMClient:
    """Provider-agnostic LLM client implementation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.model = self.settings.openai_model
        self.timeout = float(self.settings.timeout_seconds)
        self._client: openai.OpenAI | None = None
        if self.settings.openai_api_key:
            self._client = openai.OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.timeout,
            )

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        input_rate, output_rate = MODEL_PRICING.get(model, (0.15, 0.60))
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return a model completion with retry and token tracking."""
        if not self._client:
            raise ValueError(
                "OPENAI_API_KEY is not configured in .env. "
                "Please add your OPENAI_API_KEY to proceed."
            )

        @retry(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(
                (openai.APIConnectionError, openai.RateLimitError, openai.APITimeoutError)
            ),
        )
        def _call_api() -> LLMResponse:
            assert self._client is not None
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=self.timeout,
            )

            choice = response.choices[0]
            content = choice.message.content or ""
            usage = response.usage

            input_tokens = usage.prompt_tokens if usage else None
            output_tokens = usage.completion_tokens if usage else None
            cost = None
            if input_tokens is not None and output_tokens is not None:
                cost = self._calculate_cost(self.model, input_tokens, output_tokens)

            return LLMResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )

        return _call_api()
