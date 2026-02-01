
import pytest
from app.services.language_packs.factory import LanguagePackFactory, DefaultPack
from app.services.language_packs.base import BaseLanguagePack

# Mock Packs for Testing
class MockFrenchPack(BaseLanguagePack):
    @property
    def code(self): return "fr"
    @property
    def script_direction(self): return "ltr"
    def check_variants(self, t): return [{"type": "MOCK_FR", "message": "FR Base Check"}]

class MockFrenchCanadianPack(MockFrenchPack):
    @property
    def code(self): return "fr-CA"
    def check_variants(self, t): return [{"type": "MOCK_FR_CA", "message": "FR-CA Check"}]

def test_exact_match():
    # Setup Factory with mocks (Monkeypatching for test)
    original_packs = LanguagePackFactory._packs
    LanguagePackFactory._packs = {
        "fr": MockFrenchPack(),
        "fr-ca": MockFrenchCanadianPack()
    }
    
    try:
        pack = LanguagePackFactory.get_pack("fr-CA")
        assert isinstance(pack, MockFrenchCanadianPack)
        assert pack.code == "fr-CA"
        
        pack_lower = LanguagePackFactory.get_pack("fr-ca") # Case insensitivity
        assert isinstance(pack_lower, MockFrenchCanadianPack)
    finally:
        LanguagePackFactory._packs = original_packs

def test_fallback_logic():
    # Setup: Only have 'fr', request 'fr-BE' (should fall back to 'fr')
    original_packs = LanguagePackFactory._packs
    LanguagePackFactory._packs = {
        "fr": MockFrenchPack()
    }
    
    try:
        pack = LanguagePackFactory.get_pack("fr-BE")
        assert isinstance(pack, MockFrenchPack)
        assert pack.code == "fr" # Base code
    finally:
        LanguagePackFactory._packs = original_packs

def test_deep_fallback_to_default():
    # Request 'xx-YY', no 'xx', no 'xx-YY' -> DefaultPack
    pack = LanguagePackFactory.get_pack("xx-YY")
    assert isinstance(pack, DefaultPack)
    assert pack.code == "en"

def test_complex_bcp47():
    # 'zh-Hans-CN' -> 'zh-Hans' -> 'zh' -> Default
    # We will implement logic to strip last segment
    original_packs = LanguagePackFactory._packs
    class MockChineseSimple(BaseLanguagePack):
        @property
        def code(self): return "zh-hans"
        @property
        def script_direction(self): return "ltr"
        def check_variants(self, t): return []
        
    LanguagePackFactory._packs = {
        "zh-hans": MockChineseSimple()
    }
    
    try:
        pack = LanguagePackFactory.get_pack("zh-Hans-CN")
        assert isinstance(pack, MockChineseSimple)
    finally:
        LanguagePackFactory._packs = original_packs
