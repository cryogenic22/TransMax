"""Tests for MCP tool implementations."""

import pytest
from transmax_sdk import TransMaxSDK
from transmax_mcp.tools import TransMaxTools


class TestMCPTools:
    def setup_method(self):
        self.sdk = TransMaxSDK(config={"allow_passthrough": True})
        self.tools = TransMaxTools(sdk=self.sdk)

    def test_detect_language(self):
        result = self.tools.detect_language("This is an English sentence.")
        assert result["lang_code"] == "en"
        assert result["confidence"] > 0.5
        assert "lang_name" in result

    @pytest.mark.asyncio
    async def test_translate_returns_schema(self):
        result = await self.tools.translate(
            "This is an English sentence about pharmaceutical dosages.",
            "fr",
            source_lang="en",
        )
        assert "translated_text" in result
        assert "confidence" in result
        assert "status" in result
        assert "defects" in result
        assert result["source_lang"] == "en"
        assert result["target_lang"] == "fr"

    @pytest.mark.asyncio
    async def test_quality_check_clean(self):
        result = await self.tools.quality_check(
            source_text="Hello world",
            translated_text="Bonjour le monde",
            source_lang="en",
            target_lang="fr",
        )
        assert "verdict" in result
        assert "defect_count" in result
        assert "metrics" in result

    @pytest.mark.asyncio
    async def test_quality_check_with_defect(self):
        result = await self.tools.quality_check(
            source_text="Take 10mg daily",
            translated_text="Prendre quotidiennement",
            source_lang="en",
            target_lang="fr",
        )
        assert result["defect_count"] > 0
        assert result["verdict"] in ("BLOCKED", "REVIEW_REQUIRED")

    def test_glossary_lookup_empty(self):
        result = self.tools.glossary_lookup("adverse event")
        assert result["match_count"] == 0

    def test_estimate_cost(self):
        result = self.tools.estimate_cost("Take 10mg daily with food")
        assert result["estimated_cost_usd"] > 0
        assert "model" in result


class TestMCPToolsAutoDetect:
    @pytest.mark.asyncio
    async def test_translate_auto_detect_french(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        tools = TransMaxTools(sdk=sdk)
        result = await tools.translate(
            "Ceci est une phrase en français sur les médicaments.",
            target_lang="en",
            source_lang="auto",
        )
        assert result["source_lang"] == "fr"

    @pytest.mark.asyncio
    async def test_translate_auto_detect_japanese(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        tools = TransMaxTools(sdk=sdk)
        result = await tools.translate(
            "これは日本語のテストです",
            target_lang="en",
            source_lang="auto",
        )
        assert result["source_lang"] == "ja"
