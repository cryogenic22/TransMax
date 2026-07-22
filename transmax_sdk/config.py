"""SDK configuration with feature flags and sensible defaults."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SDKConfig(BaseModel):
    """Configuration for the TransMax SDK.

    All fields have sensible defaults so the SDK can be instantiated
    with just an API key for the simplest use case.
    """

    # LLM Providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    deepl_api_key: Optional[str] = None

    # Model defaults
    default_model: str = "gpt-4o"
    small_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # Translation
    default_domain: str = "pharma"
    default_source_lang: str = "auto"
    batch_size: int = 5
    max_concurrent_batches: int = 4
    max_refinement_iterations: int = 3
    confidence_threshold: float = 0.85
    enable_back_translation: bool = True
    # Fail-closed behaviour (A3): with no LLM provider configured the pipeline
    # raises ProviderUnavailableError. Set True to explicitly opt in to
    # passthrough output (unaltered source text labelled
    # PASSTHROUGH_UNTRANSLATED, never "MT") for headless testing.
    allow_passthrough: bool = False

    # Quality
    quality_check_plugins: List[str] = Field(
        default_factory=lambda: [
            "numeric", "units", "negation", "glossary",
            "pii", "tables", "placeholders", "complexity", "analytical",
        ]
    )

    # Translation Memory
    tm_exact_threshold: float = 1.0
    tm_fuzzy_threshold: float = 0.85
    enable_tm: bool = True

    # Resilience
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 60.0
    rate_limit_tokens_per_second: float = 50.0
    max_retries: int = 3
    retry_base_delay: float = 1.0

    # Telemetry
    enable_otel: bool = False
    enable_prometheus: bool = False
    enable_json_logging: bool = True
    otel_service_name: str = "transmax-sdk"
    otel_endpoint: Optional[str] = None

    # Database (optional - headless mode if None)
    database_url: Optional[str] = None

    # Language routing
    direct_pairs: List[str] = Field(
        default_factory=lambda: [
            "en-fr", "fr-en", "en-de", "de-en", "en-es", "es-en",
            "en-pt", "pt-en", "en-it", "it-en", "en-nl", "nl-en",
            "en-ja", "ja-en", "en-zh", "zh-en", "en-ko", "ko-en",
            "en-ar", "ar-en", "fr-de", "de-fr", "es-pt", "pt-es",
            "fr-es", "es-fr", "fr-it", "it-fr",
        ]
    )

    # Cost tracking
    cost_per_1k_input: Dict[str, float] = Field(
        default_factory=lambda: {
            "gpt-4o": 0.0025,
            "gpt-4o-mini": 0.00015,
            "gpt-4-turbo-preview": 0.01,
            "claude-3-opus-20240229": 0.015,
            "claude-sonnet-4-20250514": 0.003,
            "gemini-2.0-flash": 0.0001,
            "gemini-2.5-pro": 0.00125,
        }
    )
    cost_per_1k_output: Dict[str, float] = Field(
        default_factory=lambda: {
            "gpt-4o": 0.01,
            "gpt-4o-mini": 0.0006,
            "gpt-4-turbo-preview": 0.03,
            "claude-3-opus-20240229": 0.075,
            "claude-sonnet-4-20250514": 0.015,
            "gemini-2.0-flash": 0.0004,
            "gemini-2.5-pro": 0.01,
        }
    )

    # Extension
    extra: Dict[str, Any] = Field(default_factory=dict)
