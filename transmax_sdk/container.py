"""Dependency injection container for SDK components."""

from __future__ import annotations

from typing import Any, Dict, Optional, TypeVar

from transmax_sdk.config import SDKConfig
from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol

T = TypeVar("T")


class SDKContainer:
    """Simple DI container that wires SDK components together.

    Components are lazily created on first access and cached for the
    lifetime of the container. Override any component by calling
    register() before first access.
    """

    def __init__(self, config: Optional[SDKConfig] = None, telemetry: Optional[TelemetryProtocol] = None) -> None:
        self._config = config or SDKConfig()
        self._telemetry = telemetry or self._build_telemetry()
        self._registry: Dict[str, Any] = {}
        self._factories: Dict[str, Any] = {}

    def _build_telemetry(self) -> TelemetryProtocol:
        if self._config.enable_otel:
            from transmax_sdk.telemetry.otel import OpenTelemetryService
            return OpenTelemetryService(
                service_name=self._config.otel_service_name,
                endpoint=self._config.otel_endpoint,
            )
        return NoOpTelemetry()

    @property
    def config(self) -> SDKConfig:
        return self._config

    @property
    def telemetry(self) -> TelemetryProtocol:
        return self._telemetry

    def register(self, name: str, instance: Any) -> None:
        """Register a pre-built instance."""
        self._registry[name] = instance

    def register_factory(self, name: str, factory: Any) -> None:
        """Register a factory callable. Will be called once on first resolve."""
        self._factories[name] = factory

    def resolve(self, name: str) -> Any:
        """Resolve a component by name. Creates from factory on first access."""
        if name not in self._registry:
            if name in self._factories:
                self._registry[name] = self._factories[name](self)
            else:
                raise KeyError(f"No component registered for '{name}'")
        return self._registry[name]

    def has(self, name: str) -> bool:
        return name in self._registry or name in self._factories

    def _register_defaults(self) -> None:
        """Wire up default SDK components. Called by TransMaxSDK."""
        # Quality gate
        if not self.has("quality_gate"):
            self.register_factory("quality_gate", lambda c: self._make_quality_gate(c))

        # Language detector
        if not self.has("language_detector"):
            self.register_factory("language_detector", lambda c: self._make_language_detector(c))

        # Router
        if not self.has("router"):
            self.register_factory("router", lambda c: self._make_router(c))

        # Cost tracker
        if not self.has("cost_tracker"):
            from transmax_sdk.telemetry.cost import CostTracker
            self.register("cost_tracker", CostTracker(
                cost_per_1k_input=self._config.cost_per_1k_input,
                cost_per_1k_output=self._config.cost_per_1k_output,
            ))

        # Translation memory
        if not self.has("tm"):
            self.register_factory("tm", lambda c: self._make_tm(c))

        # Glossary
        if not self.has("glossary"):
            self.register_factory("glossary", lambda c: self._make_glossary(c))

        # Audit
        if not self.has("audit"):
            self.register_factory("audit", lambda c: self._make_audit(c))

        # Document manager
        if not self.has("document_manager"):
            self.register_factory("document_manager", lambda c: self._make_document_manager(c))

        # Confidence scorer
        if not self.has("scorer"):
            self.register_factory("scorer", lambda c: self._make_scorer(c))

        # LLM provider (auto-wire from config API keys)
        if not self.has("llm_provider"):
            self.register_factory("llm_provider", lambda c: self._make_llm_provider(c))

        # All LLM providers dict (for smart routing)
        if not self.has("llm_providers"):
            self.register_factory("llm_providers", lambda c: self._make_all_llm_providers(c))

        # Pipeline (depends on other components)
        if not self.has("pipeline"):
            self.register_factory("pipeline", lambda c: self._make_pipeline(c))

    def _make_quality_gate(self, container: "SDKContainer"):
        from transmax_sdk.quality.gate import PharmaQualityGate
        return PharmaQualityGate(telemetry=container.telemetry)

    def _make_language_detector(self, container: "SDKContainer"):
        from transmax_sdk.language.detection import LanguageDetector
        return LanguageDetector()

    def _make_router(self, container: "SDKContainer"):
        # Use SmartRouter when multiple providers are available
        all_providers = container.resolve("llm_providers")
        if len(all_providers) > 1:
            from transmax_sdk.language.smart_router import SmartRouter
            return SmartRouter(
                direct_pairs=set(container.config.direct_pairs),
                available_providers=set(all_providers.keys()),
                telemetry=container.telemetry,
            )
        from transmax_sdk.language.router import AnyToAnyRouter
        return AnyToAnyRouter(
            direct_pairs=set(container.config.direct_pairs),
            telemetry=container.telemetry,
        )

    def _make_tm(self, container: "SDKContainer"):
        from transmax_sdk.memory.tm import VectorTranslationMemory
        return VectorTranslationMemory(
            fuzzy_threshold=container.config.tm_fuzzy_threshold,
            telemetry=container.telemetry,
        )

    def _make_glossary(self, container: "SDKContainer"):
        from transmax_sdk.memory.glossary import GlossaryManager
        return GlossaryManager(telemetry=container.telemetry)

    def _make_audit(self, container: "SDKContainer"):
        from transmax_sdk.audit.service import HashChainedAuditTrail
        return HashChainedAuditTrail(telemetry=container.telemetry)

    def _make_document_manager(self, container: "SDKContainer"):
        from transmax_sdk.documents.manager import DefaultDocumentManager
        return DefaultDocumentManager(telemetry=container.telemetry)

    def _make_scorer(self, container: "SDKContainer"):
        from transmax_sdk.quality.scoring import ConfidenceScorer
        return ConfidenceScorer(telemetry=container.telemetry)

    def _make_llm_provider(self, container: "SDKContainer"):
        """Auto-create LLM provider based on config API keys."""
        config = container.config
        if config.openai_api_key:
            from transmax_sdk.llm.openai_provider import OpenAIProvider
            return OpenAIProvider(
                api_key=config.openai_api_key,
                default_model=config.default_model,
                telemetry=container.telemetry,
            )
        if config.anthropic_api_key:
            from transmax_sdk.llm.anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                api_key=config.anthropic_api_key,
                telemetry=container.telemetry,
            )
        if config.gemini_api_key:
            from transmax_sdk.llm.gemini_provider import GeminiProvider
            return GeminiProvider(
                api_key=config.gemini_api_key,
                telemetry=container.telemetry,
            )
        return None  # Headless mode - no LLM

    def _make_all_llm_providers(self, container: "SDKContainer") -> Dict[str, Any]:
        """Build dict of all available LLM providers keyed by name."""
        providers: Dict[str, Any] = {}
        config = container.config
        if config.openai_api_key:
            from transmax_sdk.llm.openai_provider import OpenAIProvider
            providers["openai"] = OpenAIProvider(
                api_key=config.openai_api_key,
                default_model=config.default_model,
                telemetry=container.telemetry,
            )
        if config.anthropic_api_key:
            from transmax_sdk.llm.anthropic_provider import AnthropicProvider
            providers["anthropic"] = AnthropicProvider(
                api_key=config.anthropic_api_key,
                telemetry=container.telemetry,
            )
        if config.gemini_api_key:
            from transmax_sdk.llm.gemini_provider import GeminiProvider
            providers["gemini"] = GeminiProvider(
                api_key=config.gemini_api_key,
                telemetry=container.telemetry,
            )
        return providers

    def _make_pipeline(self, container: "SDKContainer"):
        from transmax_sdk.pipeline.pipeline import DefaultTranslationPipeline
        return DefaultTranslationPipeline(
            llm_provider=container.resolve("llm_provider"),
            quality_gate=container.resolve("quality_gate"),
            tm=container.resolve("tm"),
            glossary=container.resolve("glossary"),
            router=container.resolve("router"),
            scorer=container.resolve("scorer"),
            cost_tracker=container.resolve("cost_tracker"),
            telemetry=container.telemetry,
            llm_providers=container.resolve("llm_providers") or None,
            allow_passthrough=container.config.allow_passthrough,
        )
