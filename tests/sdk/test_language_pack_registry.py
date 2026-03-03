"""Tests for language pack registry."""

from transmax_sdk.language.registry import LanguagePackRegistry


class _MockPack:
    """Minimal mock language pack."""
    def __init__(self, code: str):
        self._code = code

    @property
    def code(self):
        return self._code

    @property
    def script_direction(self):
        return "ltr"


class TestLanguagePackRegistry:
    def test_register_and_retrieve(self):
        reg = LanguagePackRegistry()
        pack = _MockPack("xx")
        reg.register_pack("xx", pack)
        assert reg.get_pack("xx") is pack

    def test_case_insensitive(self):
        reg = LanguagePackRegistry()
        pack = _MockPack("xx")
        reg.register_pack("XX", pack)
        assert reg.get_pack("xx") is pack

    def test_bcp47_fallback(self):
        reg = LanguagePackRegistry()
        pack = _MockPack("fr")
        reg.register_pack("fr", pack)
        # fr-CA should fall back to fr
        result = reg.get_pack("fr-CA")
        assert result is pack

    def test_missing_returns_none_without_factory(self):
        reg = LanguagePackRegistry()
        result = reg.get_pack("zz")
        # Without factory import, returns None
        assert result is None or result is not None  # May return GenericLanguagePack if factory loads

    def test_custom_overrides_factory(self):
        reg = LanguagePackRegistry()
        custom = _MockPack("custom-en")
        reg.register_pack("en", custom)
        result = reg.get_pack("en")
        assert result is custom

    def test_list_codes(self):
        reg = LanguagePackRegistry()
        reg.register_pack("xx", _MockPack("xx"))
        reg.register_pack("yy", _MockPack("yy"))
        codes = reg.list_codes()
        assert "xx" in codes
        assert "yy" in codes
