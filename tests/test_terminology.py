
import pytest
from app.services.quality_gate import QualityGateService

class TestTerminologyConstraints:

    def setup_method(self):
        self.service = QualityGateService()

    def test_mandatory_term_success(self):
        """Target text correctly includes the mandatory translation."""
        source = "The patient took 50mg of Aspirin."
        target = "Le patient a pris 50mg d'Aspirine."

        glossary = [{"source": "Aspirin", "target": "Aspirine"}]
        constraints = {"glossary": glossary}

        violations = self.service.check_segment(source, target, constraints, "fr")
        mandatory_violations = [v for v in violations if v['category'] == 'TERMINOLOGY' and 'Glossary' in v['message']]

        assert len(mandatory_violations) == 0

    def test_mandatory_term_missing(self):
        """Target text fails to use the mandatory translation."""
        source = "The patient took 50mg of Aspirin."
        target = "Le patient a pris 50mg d'Acetylsalicylic Acid."

        glossary = [{"source": "Aspirin", "target": "Aspirine"}]
        constraints = {"glossary": glossary}

        violations = self.service.check_segment(source, target, constraints, "fr")
        mandatory_violations = [v for v in violations if v['category'] == 'TERMINOLOGY' and 'Glossary' in v['message']]

        assert len(mandatory_violations) == 1
        assert mandatory_violations[0]['severity'] == 'MAJOR'
        assert "Aspirine" in mandatory_violations[0]['message']

    def test_forbidden_term_critical(self):
        """Target text uses a strictly forbidden term."""
        source = "Take 2 tablets."
        target = "Drink 2 tablets."

        constraints = {
            "forbidden_terms": [
                {"term": "Drink", "severity": "critical", "reason": "Use 'Take' for solid dosage forms."}
            ]
        }

        violations = self.service.check_segment(source, target, constraints, "en")
        forbidden_violations = [v for v in violations if v['category'] == 'TERMINOLOGY' and 'Forbidden' in v['message']]

        assert len(forbidden_violations) == 1
        assert "Drink" in forbidden_violations[0]['message']

    def test_case_sensitivity(self):
        """Case-insensitive forbidden term detection."""
        source = "Do not take."
        target = "do NOT Take."

        constraints = {
            "forbidden_terms": [{"term": "Take", "severity": "major"}]
        }

        violations = self.service.check_segment(source, target, constraints, "en")
        forbidden_violations = [v for v in violations if v['category'] == 'TERMINOLOGY' and 'Forbidden' in v['message']]

        assert len(forbidden_violations) == 1

if __name__ == "__main__":
    t = TestTerminologyConstraints()
    t.setup_method()
    try:
        t.test_mandatory_term_missing()
        print("OK")
    except Exception as e:
        print(f"FAILED {e}")
