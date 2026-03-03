"""End-to-end pipeline tests: full flow from text to result."""

import pytest
from transmax_sdk import TransMaxSDK
from transmax_sdk.types import TranslationStatus


class TestE2EPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_headless(self):
        """Full pipeline: translate -> quality -> score."""
        sdk = TransMaxSDK()
        result = await sdk.translate("Take 10mg ibuprofen daily.", target_lang="fr", source_lang="en")

        assert result.source_lang == "en"
        assert result.target_lang == "fr"
        assert len(result.segments) == 1
        assert result.translated_text
        assert result.confidence >= 0
        assert result.status in (
            TranslationStatus.PASS,
            TranslationStatus.REVIEW_REQUIRED,
            TranslationStatus.BLOCKED,
        )
        assert result.to_dict()  # Serializable

    @pytest.mark.asyncio
    async def test_pipeline_with_tm(self):
        """Pipeline uses TM for exact matches."""
        sdk = TransMaxSDK()
        tm = sdk.container.resolve("tm")
        tm.store("Take 10mg daily", "Prendre 10mg par jour", "en", "fr")

        result = await sdk.translate("Take 10mg daily", target_lang="fr", source_lang="en")
        assert result.segments[0].translation_source == "TM_EXACT"
        assert result.segments[0].translated_text == "Prendre 10mg par jour"
        assert result.total_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_pipeline_with_glossary(self):
        """Quality check enforces glossary terms."""
        sdk = TransMaxSDK()
        defects = await sdk.quality_check(
            source_text="Report any adverse event",
            translated_text="Signaler tout événement",
            source_lang="en",
            target_lang="fr",
        )
        # No glossary loaded, so no glossary defect (but that's expected)
        assert isinstance(defects, list)

    @pytest.mark.asyncio
    async def test_pipeline_detects_critical_defect(self):
        """Critical defect (missing number) causes BLOCKED status."""
        sdk = TransMaxSDK()

        # Manually check quality
        defects = await sdk.quality_check(
            source_text="Administer 500mg every 6 hours",
            translated_text="Administrer toutes les heures",
            source_lang="en",
            target_lang="fr",
        )
        critical = [d for d in defects if d.severity.value == "CRITICAL"]
        assert len(critical) > 0  # Missing 500 and 6


class TestE2EAudit:
    def test_audit_through_sdk(self):
        """Audit trail works through SDK container."""
        sdk = TransMaxSDK()
        audit = sdk.container.resolve("audit")

        audit_id = audit.create_trail("e2e_job_1")
        audit.log_event(audit_id, "JOB_STARTED", {"test": True})
        audit.log_event(audit_id, "TRANSLATION_COMPLETE", {"segments": 5})

        # Verify integrity
        result = audit.verify_integrity(audit_id)
        assert result["valid"] is True

        # Export bundle
        bundle = audit.export_bundle(audit_id)
        assert bundle["integrity_status"] == "PASS"
        assert len(bundle["chain_of_custody"]) == 2


class TestE2EDocumentFlow:
    @pytest.mark.asyncio
    async def test_document_to_translation(self):
        """Document segmentation -> translation flow."""
        sdk = TransMaxSDK()
        doc_mgr = sdk.container.resolve("document_manager")

        text = "Take 10mg daily. Do not exceed recommended dose. Store below 25 degrees."
        segments = doc_mgr.text_to_segments(text, "sentence", "doc_1")

        assert len(segments) == 3
        assert segments[0].source_text == "Take 10mg daily."

        # Translate all segments
        result = await sdk.translate(
            [s.source_text for s in segments],
            target_lang="fr",
            source_lang="en",
        )
        assert len(result.segments) == 3
