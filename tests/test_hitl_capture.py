"""TMX-MQM-CAPTURE — reviewer override → learning bridge (gold signal)."""
import asyncio
from unittest.mock import AsyncMock, patch

from app.api.segments import _capture_hitl_override


def test_capture_invokes_learning_within_tenant_context():
    with patch("app.services.learning_service.LearningService") as LS:
        inst = LS.return_value
        inst.process_learning_event = AsyncMock(return_value=None)
        asyncio.run(
            _capture_hitl_override(
                segment_id="seg-1",
                source_text="Take 10 mg twice daily",
                mt_text="Prendre 10 mg une fois par jour",
                corrected_text="Prendre 10 mg deux fois par jour",
                org_id="org-123",
            )
        )
        inst.process_learning_event.assert_awaited_once()
        kwargs = inst.process_learning_event.await_args.kwargs
        assert kwargs["human_correction"] == "Prendre 10 mg deux fois par jour"
        assert kwargs["mt_text"] == "Prendre 10 mg une fois par jour"
        assert kwargs["segment_id"] == "seg-1"


def test_capture_skips_without_tenant_context():
    # No org → cannot write a tenant-scoped candidate; skip cleanly (A3),
    # and never construct/learn.
    with patch("app.services.learning_service.LearningService") as LS:
        asyncio.run(
            _capture_hitl_override("seg-1", "src", "mt", "corrected", org_id=None)
        )
        LS.assert_not_called()


def test_capture_never_raises_on_learning_failure():
    with patch("app.services.learning_service.LearningService") as LS:
        inst = LS.return_value
        inst.process_learning_event = AsyncMock(side_effect=RuntimeError("boom"))
        # Must swallow — a capture failure must never surface to the reviewer.
        asyncio.run(_capture_hitl_override("seg-1", "src", "mt", "new", "org-1"))
