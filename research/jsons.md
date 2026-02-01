{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://synaptyx.ai/schemas/transmax/v1/quality_report.schema.json",
  "title": "TransMax Quality Report",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "checks_run", "violations", "summary"],
  "properties": {
    "schema_version": { "type": "string", "const": "transmax.quality.v1" },
    "checks_run": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string" },
      "description": "Names/ids of deterministic checks executed."
    },
    "violations": {
      "type": "array",
      "items": { "$ref": "#/$defs/violation" }
    },
    "summary": {
      "type": "object",
      "additionalProperties": false,
      "required": ["counts_by_severity", "counts_by_type"],
      "properties": {
        "counts_by_severity": {
          "type": "object",
          "additionalProperties": false,
          "required": ["critical", "major", "minor"],
          "properties": {
            "critical": { "type": "integer", "minimum": 0 },
            "major": { "type": "integer", "minimum": 0 },
            "minor": { "type": "integer", "minimum": 0 }
          }
        },
        "counts_by_type": {
          "type": "object",
          "additionalProperties": { "type": "integer", "minimum": 0 },
          "description": "Map of violation type -> count."
        }
      }
    }
  },
  "$defs": {
    "severity": {
      "type": "string",
      "enum": ["critical", "major", "minor"]
    },
    "violation_type": {
      "type": "string",
      "enum": [
        "number_mismatch",
        "unit_mismatch",
        "frequency_mismatch",
        "negation_flip",
        "modality_drift",
        "population_drift",
        "mandatory_term_missing",
        "forbidden_term_present",
        "preferred_phrase_missing",
        "hallucinated_addition_suspected",
        "format_structure_change",

        "ar_digit_form_changed",
        "ar_decimal_separator_inconsistent",
        "ar_unit_adjacency_broken",
        "ar_bidi_punctuation_issue",

        "ja_term_variant_disallowed",
        "ja_mandatory_phrase_missing",
        "ja_tokenisation_alignment_issue"
      ]
    },
    "evidence": {
      "type": "object",
      "additionalProperties": false,
      "required": ["method"],
      "properties": {
        "method": {
          "type": "string",
          "enum": [
            "regex",
            "numeric_parse",
            "unit_parse",
            "glossary_match",
            "tokeniser_match",
            "diff_alignment",
            "custom_rule"
          ]
        },
        "rule_id": { "type": "string" },
        "source_span": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "text": { "type": "string" },
            "start": { "type": "integer", "minimum": 0 },
            "end": { "type": "integer", "minimum": 0 }
          }
        },
        "target_span": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "text": { "type": "string" },
            "start": { "type": "integer", "minimum": 0 },
            "end": { "type": "integer", "minimum": 0 }
          }
        },
        "expected": { "type": "string" },
        "observed": { "type": "string" }
      }
    },
    "violation": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "severity", "segment_id", "message", "evidence"],
      "properties": {
        "type": { "$ref": "#/$defs/violation_type" },
        "severity": { "$ref": "#/$defs/severity" },
        "segment_id": { "type": "string", "minLength": 1 },
        "message": { "type": "string", "minLength": 1 },
        "evidence": { "$ref": "#/$defs/evidence" },
        "suggested_action": {
          "type": "string",
          "enum": ["auto_fix", "needs_review", "block_output"],
          "default": "needs_review"
        }
      }
    },
    "action_event": {
      "type": "object",
      "additionalProperties": false,
      "required": ["action_type", "segment_id", "reason", "before_hash", "after_hash"],
      "properties": {
        "action_type": {
          "type": "string",
          "enum": [
            "replace_mandatory_term",
            "remove_forbidden_term",
            "fix_number_format",
            "fix_unit_format",
            "fix_frequency_phrase",
            "restore_negation",
            "adjust_modality",
            "apply_preferred_phrase",
            "rewrite_segment_targeted"
          ]
        },
        "segment_id": { "type": "string", "minLength": 1 },
        "reason": {
          "type": "object",
          "additionalProperties": false,
          "required": ["violation_type"],
          "properties": {
            "violation_type": { "$ref": "#/$defs/violation_type" },
            "rule_id": { "type": "string" }
          }
        },
        "before_hash": { "type": "string", "minLength": 32 },
        "after_hash": { "type": "string", "minLength": 32 },
        "notes": {
          "type": "string",
          "description": "Optional short note written by the system (not free-form LLM reasoning)."
        }
      }
    }
  }
}





