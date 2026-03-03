"""OpenAI LLM provider implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class OpenAIProvider:
    """LLM provider using the OpenAI API."""

    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4o",
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._telemetry = telemetry or NoOpTelemetry()
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        model = model or self._default_model

        with self._telemetry.span("llm.complete", {"provider": "openai", "model": model}):
            client = self._get_client()
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            usage = response.usage

            self._telemetry.counter(
                "transmax_llm_tokens_total",
                value=float(usage.prompt_tokens),
                labels={"provider": "openai", "direction": "input"},
            )
            self._telemetry.counter(
                "transmax_llm_tokens_total",
                value=float(usage.completion_tokens),
                labels={"provider": "openai", "direction": "output"},
            )

            return {
                "content": choice.message.content,
                "usage": {
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                },
                "model": model,
            }
