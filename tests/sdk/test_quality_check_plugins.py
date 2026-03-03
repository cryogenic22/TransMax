"""Tests for individual quality check plugins."""

from transmax_sdk.quality.checks.numeric import NumericCheck
from transmax_sdk.quality.checks.units import UnitsCheck
from transmax_sdk.quality.checks.negation import NegationCheck
from transmax_sdk.quality.checks.glossary import GlossaryCheck
from transmax_sdk.quality.checks.pii import PIICheck
from transmax_sdk.quality.checks.tables import TablesCheck
from transmax_sdk.quality.checks.placeholders import PlaceholdersCheck
from transmax_sdk.quality.checks.complexity import ComplexityCheck
from transmax_sdk.quality.checks.analytical import AnalyticalCheck
from transmax_sdk.types import Severity


class TestNumericCheck:
    def test_detects_missing_number(self):
        c = NumericCheck()
        defects = c.check("Take 10mg daily", "Prendre mg quotidiennement", "en", "fr")
        assert len(defects) == 1
        assert defects[0].severity == Severity.CRITICAL

    def test_passes_when_numbers_present(self):
        c = NumericCheck()
        defects = c.check("Take 10mg daily", "Prendre 10mg par jour", "en", "fr")
        assert len(defects) == 0

    def test_handles_decimal_numbers(self):
        c = NumericCheck()
        defects = c.check("Dose: 0.5ml", "Dose: 0,5ml", "en", "fr")
        assert len(defects) == 0  # 0.5 matches 0,5

    def test_no_numbers_no_defects(self):
        c = NumericCheck()
        defects = c.check("Hello world", "Bonjour le monde", "en", "fr")
        assert len(defects) == 0


class TestUnitsCheck:
    def test_detects_missing_unit(self):
        c = UnitsCheck()
        defects = c.check("5mg daily", "5 quotidiennement", "en", "fr")
        assert any(d.category == "UNIT_MISMATCH" for d in defects)

    def test_passes_when_units_present(self):
        c = UnitsCheck()
        defects = c.check("5mg daily", "5mg par jour", "en", "fr")
        unit_defects = [d for d in defects if d.category == "UNIT_MISMATCH"]
        assert len(unit_defects) == 0

    def test_detects_missing_symbol(self):
        c = UnitsCheck()
        defects = c.check("Temperature: 37°C", "Température: 37C", "en", "fr")
        assert any("°" in d.message for d in defects)


class TestNegationCheck:
    def test_detects_negation_flip_en_fr(self):
        c = NegationCheck()
        defects = c.check("Do not take with food", "Prendre avec de la nourriture", "en", "fr")
        assert len(defects) == 1
        assert defects[0].severity == Severity.CRITICAL

    def test_passes_when_negation_preserved(self):
        c = NegationCheck()
        defects = c.check("Do not take", "Ne pas prendre", "en", "fr")
        assert len(defects) == 0

    def test_no_negation_no_defect(self):
        c = NegationCheck()
        defects = c.check("Take daily", "Prendre quotidiennement", "en", "fr")
        assert len(defects) == 0

    def test_japanese_negation(self):
        c = NegationCheck()
        defects = c.check("Do not use", "使用する", "en", "ja")
        assert len(defects) == 1  # Missing ない/ません


class TestGlossaryCheck:
    def test_detects_missing_term(self):
        c = GlossaryCheck()
        constraints = {
            "glossary": [{"source_text": "adverse event", "target_text": "événement indésirable"}]
        }
        defects = c.check(
            "Report any adverse event",
            "Signaler tout événement",
            "en", "fr", constraints,
        )
        assert len(defects) == 1
        assert defects[0].severity == Severity.MAJOR

    def test_passes_when_term_present(self):
        c = GlossaryCheck()
        constraints = {
            "glossary": [{"source_text": "adverse event", "target_text": "événement indésirable"}]
        }
        defects = c.check(
            "Report any adverse event",
            "Signaler tout événement indésirable",
            "en", "fr", constraints,
        )
        assert len(defects) == 0

    def test_no_glossary_no_defects(self):
        c = GlossaryCheck()
        defects = c.check("Hello", "Bonjour", "en", "fr")
        assert len(defects) == 0


class TestPIICheck:
    def test_detects_email_leak(self):
        c = PIICheck()
        defects = c.check("Contact us", "Contact: john@example.com", "en", "fr")
        assert any("PII" in d.category for d in defects)

    def test_detects_unresolved_token(self):
        c = PIICheck()
        defects = c.check("Contact", "Contact <EMAIL_1>", "en", "fr")
        assert len(defects) >= 1

    def test_clean_text_no_defects(self):
        c = PIICheck()
        defects = c.check("Hello", "Bonjour", "en", "fr")
        assert len(defects) == 0


class TestTablesCheck:
    def test_detects_table_count_mismatch(self):
        c = TablesCheck()
        source = "| A | B |\n|---|---|\n| 1 | 2 |"
        target = "No table here"
        defects = c.check(source, target, "en", "fr")
        assert len(defects) == 1
        assert defects[0].severity == Severity.CRITICAL

    def test_passes_matching_tables(self):
        c = TablesCheck()
        source = "| A | B |\n|---|---|\n| 1 | 2 |"
        target = "| X | Y |\n|---|---|\n| 1 | 2 |"
        defects = c.check(source, target, "en", "fr")
        assert len(defects) == 0

    def test_no_tables_no_defects(self):
        c = TablesCheck()
        defects = c.check("Hello", "Bonjour", "en", "fr")
        assert len(defects) == 0


class TestPlaceholdersCheck:
    def test_detects_missing_placeholder(self):
        c = PlaceholdersCheck()
        defects = c.check("Hello {{name}}", "Bonjour", "en", "fr")
        assert len(defects) == 1

    def test_passes_preserved_placeholder(self):
        c = PlaceholdersCheck()
        defects = c.check("Hello {{name}}", "Bonjour {{name}}", "en", "fr")
        assert len(defects) == 0

    def test_detects_numbered_placeholder_missing(self):
        c = PlaceholdersCheck()
        defects = c.check("Step [1]: do this", "Étape: faire cela", "en", "fr")
        assert len(defects) >= 1


class TestComplexityCheck:
    def test_flags_latex(self):
        c = ComplexityCheck()
        defects = c.check("Formula: $E = mc^2$", "Formule: $E = mc^2$", "en", "fr")
        assert len(defects) == 1
        assert defects[0].severity == Severity.MAJOR

    def test_flags_code_block(self):
        c = ComplexityCheck()
        defects = c.check("```python\nprint('hello')\n```", "code", "en", "fr")
        assert len(defects) == 1

    def test_simple_text_no_flag(self):
        c = ComplexityCheck()
        defects = c.check("Take daily", "Prendre quotidiennement", "en", "fr")
        assert len(defects) == 0


class TestAnalyticalCheck:
    def test_detects_anchor_mismatch(self):
        c = AnalyticalCheck()
        constraints = {"archetype": "ANALYTICAL"}
        defects = c.check("strongly agree", "mauvais", "en", "fr", constraints)
        assert any(d.category == "ANCHOR_MISMATCH" for d in defects)

    def test_passes_correct_anchor(self):
        c = AnalyticalCheck()
        constraints = {"archetype": "ANALYTICAL"}
        defects = c.check("strongly agree", "tout à fait d'accord", "en", "fr", constraints)
        anchor_defects = [d for d in defects if d.category == "ANCHOR_MISMATCH"]
        assert len(anchor_defects) == 0

    def test_skips_without_analytical_flag(self):
        c = AnalyticalCheck()
        defects = c.check("strongly agree", "mauvais", "en", "fr")
        assert len(defects) == 0

    def test_sentiment_shift_detected(self):
        c = AnalyticalCheck()
        constraints = {"check_analytical_anchors": True}
        defects = c.check("This is bad", "C'est bon", "en", "fr", constraints)
        sentiment_defects = [d for d in defects if d.category == "SENTIMENT_SHIFT"]
        assert len(sentiment_defects) == 1
