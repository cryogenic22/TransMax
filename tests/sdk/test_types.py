"""Tests for SDK shared types."""

from transmax_sdk.types import (
    CostRecord,
    LanguageDetectionResult,
    QualityDefect,
    RouteStrategy,
    SegmentResult,
    Severity,
    TranslationRequest,
    TranslationResult,
    TranslationSegment,
    TranslationStatus,
)


class TestSeverityEnum:
    def test_values(self):
        assert Severity.CRITICAL == "CRITICAL"
        assert Severity.MAJOR == "MAJOR"
        assert Severity.MINOR == "MINOR"

    def test_string_comparison(self):
        assert Severity("CRITICAL") is Severity.CRITICAL


class TestQualityDefect:
    def test_construction(self):
        d = QualityDefect(
            category="NUMERIC_MISMATCH",
            severity=Severity.CRITICAL,
            message="Number 10 missing in target",
        )
        assert d.category == "NUMERIC_MISMATCH"
        assert d.severity == Severity.CRITICAL
        assert d.segment_id is None

    def test_to_dict(self):
        d = QualityDefect(
            category="PII_LEAK",
            severity=Severity.MAJOR,
            message="Email leaked",
            segment_id="seg_1",
        )
        data = d.to_dict()
        assert data["category"] == "PII_LEAK"
        assert data["severity"] == "MAJOR"
        assert data["segment_id"] == "seg_1"

    def test_from_dict_roundtrip(self):
        original = QualityDefect(
            category="UNIT_MISMATCH",
            severity=Severity.CRITICAL,
            message="mg -> ml conversion error",
            suggestion="Use mg",
        )
        data = original.to_dict()
        restored = QualityDefect.from_dict(data)
        assert restored.category == original.category
        assert restored.severity == original.severity
        assert restored.suggestion == original.suggestion


class TestTranslationSegment:
    def test_construction(self):
        seg = TranslationSegment(segment_id="s1", source_text="Take 10mg daily")
        assert seg.segment_id == "s1"
        assert seg.order_index == 0
        assert seg.metadata == {}

    def test_with_context(self):
        seg = TranslationSegment(
            segment_id="s2",
            source_text="Take 10mg daily",
            context_before="Dosage:",
            context_after="With food.",
        )
        assert seg.context_before == "Dosage:"


class TestTranslationRequest:
    def test_defaults(self):
        req = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Hello")],
        )
        assert req.source_lang == "auto"
        assert req.target_lang == "en"
        assert req.domain == "pharma"

    def test_custom_options(self):
        req = TranslationRequest(
            segments=[],
            source_lang="fr",
            target_lang="de",
            options={"model": "gpt-4o-mini"},
        )
        assert req.options["model"] == "gpt-4o-mini"


class TestTranslationResult:
    def test_translated_text_joins_segments(self):
        result = TranslationResult(
            segments=[
                SegmentResult(segment_id="s1", source_text="Hello", translated_text="Bonjour"),
                SegmentResult(segment_id="s2", source_text="World", translated_text="Monde"),
            ],
            source_lang="en",
            target_lang="fr",
        )
        assert result.translated_text == "Bonjour\nMonde"

    def test_confidence_average(self):
        result = TranslationResult(
            segments=[
                SegmentResult(segment_id="s1", source_text="a", translated_text="b", confidence=80.0),
                SegmentResult(segment_id="s2", source_text="c", translated_text="d", confidence=90.0),
            ],
            source_lang="en",
            target_lang="fr",
        )
        assert result.confidence == 85.0

    def test_confidence_empty(self):
        result = TranslationResult(segments=[], source_lang="en", target_lang="fr")
        assert result.confidence == 0.0

    def test_defects_aggregated(self):
        d1 = QualityDefect(category="A", severity=Severity.MINOR, message="x")
        d2 = QualityDefect(category="B", severity=Severity.MAJOR, message="y")
        result = TranslationResult(
            segments=[
                SegmentResult(segment_id="s1", source_text="a", translated_text="b", defects=[d1]),
                SegmentResult(segment_id="s2", source_text="c", translated_text="d", defects=[d2]),
            ],
            source_lang="en",
            target_lang="fr",
        )
        assert len(result.defects) == 2

    def test_to_dict(self):
        result = TranslationResult(
            segments=[
                SegmentResult(segment_id="s1", source_text="Hi", translated_text="Salut"),
            ],
            source_lang="en",
            target_lang="fr",
            audit_id="audit_123",
        )
        data = result.to_dict()
        assert data["source_lang"] == "en"
        assert data["audit_id"] == "audit_123"
        assert len(data["segments"]) == 1


class TestCostRecord:
    def test_construction(self):
        rec = CostRecord(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.0075,
        )
        assert rec.cost_usd == 0.0075
        assert rec.request_id is None


class TestLanguageDetectionResult:
    def test_construction(self):
        result = LanguageDetectionResult(
            lang_code="ja", confidence=0.99, lang_name="Japanese"
        )
        assert result.lang_code == "ja"


class TestRouteStrategy:
    def test_values(self):
        assert RouteStrategy.DIRECT.value == "DIRECT"
        assert RouteStrategy.PIVOT_ENGLISH.value == "PIVOT_ENGLISH"
