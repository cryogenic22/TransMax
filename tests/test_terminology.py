
import pytest
from app.services.quality_gate import QualityGateService

class TestTerminologyConstraints:
    
    def setup_method(self):
        self.service = QualityGateService()

    def test_mandatory_term_success(self):
        """
        Scenario: Target text correctly includes the mandatory translation.
        """
        source = "The patient took 50mg of Aspirin."
        target = "Le patient a pris 50mg d'Aspirine." # 'Aspirine' matches
        
        glossary = [{"source": "Aspirin", "target": "Aspirine"}]
        constraints = {"glossary": glossary}
        
        violations = self.service.check_segment(source, target, constraints)
        mandatory_violations = [v for v in violations if v['type'] == 'mandatory_term_missing']
        
        assert len(mandatory_violations) == 0

    def test_mandatory_term_missing(self):
        """
        Scenario: Target text fails to use the mandatory translation.
        """
        source = "The patient took 50mg of Aspirin."
        target = "Le patient a pris 50mg d'Acetylsalicylic Acid." # Missing 'Aspirine'
        
        glossary = [{"source": "Aspirin", "target": "Aspirine"}]
        constraints = {"glossary": glossary}
        
        violations = self.service.check_segment(source, target, constraints)
        mandatory_violations = [v for v in violations if v['type'] == 'mandatory_term_missing']
        
        assert len(mandatory_violations) == 1
        assert mandatory_violations[0]['severity'] == 'major'
        assert "Aspirine" in mandatory_violations[0]['message']

    def test_forbidden_term_critical(self):
        """
        Scenario: Target text uses a strictly forbidden term.
        """
        source = "Take 2 tablets."
        target = "Drink 2 tablets." # 'Drink' is forbidden for tablets
        
        # forbidden_terms is a list of strings or dicts? Let's check plan.
        # Plan says "forbidden_terms list" in constraint pack.
        # We will pass it in constraints.
        
        constraints = {
            "forbidden_terms": [
                {"term": "Drink", "severity": "critical", "reason": "Use 'Take' for solid dosage forms."}
            ]
        }
        
        violations = self.service.check_segment(source, target, constraints)
        forbidden_violations = [v for v in violations if v['type'] == 'forbidden_term']
        
        assert len(forbidden_violations) == 1
        assert forbidden_violations[0]['severity'] == 'critical'
        assert "Drink" in forbidden_violations[0]['message']

    def test_word_boundary_safety(self):
        """
        Scenario: Ensure partial matches don't trigger false positives.
        API Quality Check: 'Use' is forbidden, but 'User' should pass.
        """
        source = "Select User Profile."
        target = "Select User Profile."
        
        constraints = {
            "forbidden_terms": [{"term": "Use", "severity": "major"}]
        }
        
        # 'User' contains 'Use', but with boundary check it should pass
        violations = self.service.check_segment(source, target, constraints)
        forbidden_violations = [v for v in violations if v['type'] == 'forbidden_term']
        
        assert len(forbidden_violations) == 0
        
    def test_case_sensitivity(self):
        """
        Scenario: Check if matching is robust to case (usually we want IgnoreCase for terms).
        """
        source = "Do not take."
        target = "do NOT Take." # forbidden 'Take'
        
        constraints = {
            "forbidden_terms": [{"term": "Take", "severity": "major"}]
        }
        
        violations = self.service.check_segment(source, target, constraints)
        # Should catch "Take" even if "do NOT Take."
        forbidden_violations = [v for v in violations if v['type'] == 'forbidden_term']
        
        assert len(forbidden_violations) == 1

if __name__ == "__main__":
    # verification helper
    t = TestTerminologyConstraints()
    t.setup_method()
    try:
        t.test_word_boundary_safety()
        print("Boundary check: OK (If implemented)")
    except Exception as e:
        print(f"Boundary check: FAILED {e}")
