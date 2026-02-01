import unittest
from app.services.quality_gate import QualityGateService

class TestPharmaGates(unittest.TestCase):
    def setUp(self):
        self.service = QualityGateService()

    def test_negation_flip_critical(self):
        """Test that missing negation is flagged as CRITICAL"""
        source = "Do not take with food."
        target_valid = "Ne pas prendre avec de la nourriture."
        target_invalid = "Prendre avec de la nourriture." # Dangerous!
        
        # Valid
        v = self.service.check_negation(source, target_valid)
        self.assertEqual(len(v), 0)
        
        # Invalid
        v = self.service.check_negation(source, target_invalid)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]['type'], 'negation_flip')
        self.assertEqual(v[0]['severity'], 'critical')

    def test_pii_token_integrity(self):
        """Test that PII tokens must match exactly"""
        source = "Patient [[PII:NAME:abc1]] visited."
        target_valid = "Le patient [[PII:NAME:abc1]] a visité."
        target_invalid_1 = "Le patient [[PII:NAME:xyz9]] a visité." # Wrong ID
        target_invalid_2 = "Le patient [NAME_1] a visité." # Legacy format
        
        # Valid
        v = self.service.check_pii_tokens(source, target_valid)
        self.assertEqual(len(v), 0)
        
        # Invalid ID
        v = self.service.check_pii_tokens(source, target_invalid_1)
        self.assertTrue(len(v) > 0)
        self.assertEqual(v[0]['severity'], 'critical')

    def test_unit_blocker(self):
        """Test that unit mismatch is CRITICAL"""
        source = "Dose: 50 mg"
        target_valid = "Dose : 50 mg"
        target_invalid = "Dose : 50 g" # Lethal!
        
        # Valid
        v = self.service.check_units(source, target_valid)
        self.assertEqual(len(v), 0)
        
        # Invalid
        v = self.service.check_units(source, target_invalid)
        self.assertTrue(len(v) > 0)
        self.assertEqual(v[0]['severity'], 'critical')

if __name__ == "__main__":
    unittest.main()
