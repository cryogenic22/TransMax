"""TMX-MQM-4 — independent judge parser + service."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.defect_taxonomy import DefectSeverity, MqmDimension
from app.services.mqm_judge import judge_segments, parse_judge_response

SAMPLE = json.dumps({"annotations": [
    {"segment_id": "s1", "dimension": "Accuracy", "subtype": "Mistranslation",
     "severity": "Critical", "explanation": "frequency flip", "rule_ref": "DOSING",
     "evidence_refs": ["pi#4.2"], "suggested_fix": "deux fois par jour",
     "source_span": "twice daily", "target_span": "une fois par jour"},
    {"segment_id": "s2", "dimension": "Style", "severity": "Minor", "explanation": "awkward"},
    {"segment_id": "s3", "dimension": "NotADimension", "severity": "Critical", "explanation": "skip"},
    {"segment_id": "s4", "dimension": "Accuracy", "severity": "weird", "explanation": "skip"},
]})


def test_parse_maps_valid_and_skips_unknown():
    anns = parse_judge_response(SAMPLE, judge_id="judge-a", prompt_version="judge@1.0.0", model_version="m1")
    assert len(anns) == 2  # 2 valid; bad-dimension + bad-severity skipped (never guessed)
    a = anns[0]
    assert a.dimension is MqmDimension.ACCURACY
    assert a.severity is DefectSeverity.CRITICAL
    assert a.is_auto_fail is True
    assert a.rule_ref == "DOSING"
    assert a.evidence_refs == ["pi#4.2"]
    assert a.produced_by == "critique-agent"
    assert a.judge_id == "judge-a"
    assert a.prompt_version == "judge@1.0.0"


def test_parse_handles_garbage():
    assert parse_judge_response("not json at all", judge_id="j", prompt_version="judge@1.0.0") == []


def test_judge_segments_calls_llm_and_parses():
    class FakeResp:
        content = SAMPLE

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=FakeResp())
    with patch("app.services.llm.get_llm", return_value=fake_llm):
        anns = asyncio.run(judge_segments(
            [{"segment_id": "s1", "source_text": "Take twice daily", "translated_text": "Prendre une fois"}],
            "en", "fr",
        ))
    assert len(anns) == 2
    fake_llm.ainvoke.assert_awaited_once()


def test_judge_segments_empty_when_nothing_translated():
    anns = asyncio.run(judge_segments(
        [{"segment_id": "s1", "source_text": "x", "translated_text": ""}], "en", "fr",
    ))
    assert anns == []
