"""Google Gemini LLM provider implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class GeminiProvider:
    """LLM provider using the Google Generative AI API."""

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-2.0-flash",
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._telemetry = telemetry or NoOpTelemetry()
        self._client = None

    @property
    def name(self) -> str:
        return "gemini"

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        model = model or self._default_model

        with self._telemetry.span(
            "llm.complete", {"provider": "gemini", "model": model}
        ):
            client = self._get_client()

            # Extract system instruction from messages (like Anthropic pattern)
            system_instruction = ""
            user_contents = []
            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                else:
                    user_contents.append(msg["content"])

            config: Dict[str, Any] = {"temperature": temperature}
            if max_tokens:
                config["max_output_tokens"] = max_tokens

            from google.genai import types

            response = await client.aio.models.generate_content(
                model=model,
                contents="\n".join(user_contents),
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction or None,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0

            self._telemetry.counter(
                "transmax_llm_tokens_total",
                value=float(input_tokens),
                labels={"provider": "gemini", "direction": "input"},
            )
            self._telemetry.counter(
                "transmax_llm_tokens_total",
                value=float(output_tokens),
                labels={"provider": "gemini", "direction": "output"},
            )

            return {
                "content": response.text,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
                "model": model,
            }
