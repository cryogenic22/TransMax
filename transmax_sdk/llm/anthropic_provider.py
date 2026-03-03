"""Anthropic LLM provider implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class AnthropicProvider:
    """LLM provider using the Anthropic API."""

    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-sonnet-4-20250514",
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._telemetry = telemetry or NoOpTelemetry()
        self._client = None

    @property
    def name(self) -> str:
        return "anthropic"

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        model = model or self._default_model

        with self._telemetry.span("llm.complete", {"provider": "anthropic", "model": model}):
            client = self._get_client()

            # Anthropic separates system message from user messages
            system_msg = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)

            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": user_messages,
                "max_tokens": max_tokens or 4096,
                "temperature": temperature,
            }
            if system_msg:
                kwargs["system"] = system_msg

            response = await client.messages.create(**kwargs)

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            self._telemetry.counter(
                "transmax_llm_tokens_total",
                value=float(input_tokens),
                labels={"provider": "anthropic", "direction": "input"},
            )
            self._telemetry.counter(
                "transmax_llm_tokens_total",
                value=float(output_tokens),
                labels={"provider": "anthropic", "direction": "output"},
            )

            return {
                "content": response.content[0].text,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
                "model": model,
            }
