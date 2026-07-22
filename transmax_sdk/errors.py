"""Typed SDK errors: the pipeline fails closed, never silently (A3).

Every error carries a stable string ``code`` so callers can branch without
string-matching messages::

    try:
        result = await sdk.translate(...)
    except TransMaxSDKError as exc:
        if exc.code == "PROVIDER_UNAVAILABLE":
            ...
"""

from __future__ import annotations


class TransMaxSDKError(Exception):
    """Base class for typed TransMax SDK errors.

    Subclasses override the class attribute ``code`` with a stable,
    machine-readable identifier.
    """

    code: str = "SDK_ERROR"


class ProviderUnavailableError(TransMaxSDKError):
    """No LLM provider is configured for a path that requires one.

    Raised instead of fabricating passthrough output: untranslated source
    text labelled as machine translation is an unearned provenance claim
    (CLAUDE.md A3). To intentionally run without a provider, opt in via
    ``SDKConfig.allow_passthrough=True`` (or
    ``DefaultTranslationPipeline(allow_passthrough=True)``); passthrough
    output is then labelled ``PASSTHROUGH_UNTRANSLATED``, never ``MT``.
    """

    code: str = "PROVIDER_UNAVAILABLE"


class InvalidModelResponseError(TransMaxSDKError):
    """A model response could not be parsed into translations.

    Raised instead of silently returning zero translations. Carries the
    parse-failure reason plus the LENGTH and SHA-256 of the raw payload —
    never the payload itself, which may contain regulated content that must
    not leak into exception messages or logs.
    """

    code: str = "INVALID_MODEL_RESPONSE"

    def __init__(self, message: str, *, raw_length: int, raw_sha256: str) -> None:
        super().__init__(message)
        self.raw_length = raw_length
        self.raw_sha256 = raw_sha256
