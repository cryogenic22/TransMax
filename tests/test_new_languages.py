
import pytest
from app.services.language_packs.factory import LanguagePackFactory
from app.core.policy_definitions import ViolationType

def test_french_pack():
    pack = LanguagePackFactory.get_pack("fr")
    assert pack.code == "fr"
    
    # Negation
    violations = pack.check_negation("Do not eat", "Mangez")
    assert len(violations) >= 1
    assert violations[0]['type'] == ViolationType.NEGATION_FLIP.value
    
    violations = pack.check_negation("Do not eat", "Ne mangez pas")
    assert len(violations) == 0

def test_german_pack():
    pack = LanguagePackFactory.get_pack("de")
    assert pack.code == "de"
    
    # Negation
    violations = pack.check_negation("Do not eat", "Essen Sie")
    assert len(violations) >= 1
    
    violations = pack.check_negation("Do not eat", "Essen Sie nicht")
    assert len(violations) == 0

def test_spanish_pack():
    pack = LanguagePackFactory.get_pack("es")
    assert pack.code == "es"
    
    # Numbers (Decimal comma)
    # 1.5 -> 1,5
    violations = pack.check_numbers("Value 1.5", "Valor 1,5")
    assert len(violations) == 0
    
    violations = pack.check_numbers("Value 1.5", "Valor 2")
    assert len(violations) >= 1

if __name__ == "__main__":
    test_french_pack()
    test_german_pack()
    test_spanish_pack()
    print("New Language Tests Passed")
