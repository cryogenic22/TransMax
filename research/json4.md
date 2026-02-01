{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://synaptyx.ai/schemas/transmax/v1/document_response.schema.json",
  "title": "TransMax Document Translation Response",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "job", "decision", "translated_document", "quality_report", "audit_trail_id"],
  "properties": {
    "schema_version": { "type": "string", "const": "transmax.document_response.v1" },

    "job": {
      "type": "object",
      "additionalProperties": false,
      "required": ["job_id", "status", "created_at", "updated_at"],
      "properties": {
        "job_id": { "type": "string", "minLength": 1 },
        "status": { "type": "string", "enum": ["QUEUED", "RUNNING", "COMPLETED", "FAILED"] },
        "created_at": { "type": "string", "format": "date-time" },
        "updated_at": { "type": "string", "format": "date-time" },
        "error": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "code": { "type": "string" },
            "message": { "type": "string" }
          }
        }
      }
    },

    "decision": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "scores"],
      "properties": {
        "status": { "type": "string", "enum": ["PASS", "REVIEW_REQUIRED", "BLOCKED"] },
        "scores": {
          "type": "object",
          "additionalProperties": false,
          "required": ["terminology", "safety", "format", "overall"],
          "properties": {
            "terminology": { "type": "number", "minimum": 0, "maximum": 1 },
            "safety": { "type": "number", "minimum": 0, "maximum": 1 },
            "format": { "type": "number", "minimum": 0, "maximum": 1 },
            "overall": { "type": "number", "minimum": 0, "maximum": 1 }
          }
        },
        "policy_explanation": {
          "type": "string",
          "description": "Optional short note (policy rule triggered). Not free-form LLM reasoning."
        }
      }
    },

    "translated_document": {
      "type": "object",
      "additionalProperties": false,
      "required": ["doc_type", "source_language", "target_language", "blocks"],
      "properties": {
        "doc_id": { "type": "string" },
        "doc_type": {
          "type": "string",
          "enum": ["pil", "smpc", "labeling", "cmc", "qos", "csr", "other"]
        },
        "source_language": { "type": "string", "minLength": 2, "maxLength": 16 },
        "target_language": { "type": "string", "minLength": 2, "maxLength": 16 },
        "script_direction": { "type": "string", "enum": ["ltr", "rtl"] },
        "meta": { "type": "object", "additionalProperties": true },

        "blocks": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/translated_block" }
        }
      }
    },

    "quality_report": {
      "$ref": "https://synaptyx.ai/schemas/transmax/v1/quality_report.schema.json"
    },

    "violation_index": {
      "type": "object",
      "additionalProperties": false,
      "description": "Optional UI helper index: where each violation lives in the document.",
      "properties": {
        "by_block": {
          "type": "object",
          "additionalProperties": {
            "type": "array",
            "items": { "$ref": "#/$defs/violation_pointer" }
          }
        }
      }
    },

    "audit_trail_id": {
      "type": "string",
      "pattern": "^[0-9a-fA-F-]{36}$"
    }
  },

  "$defs": {
    "translated_block": {
      "type": "object",
      "additionalProperties": false,
      "required": ["block_id", "type", "source_content_ref", "translated_content"],
      "properties": {
        "block_id": { "type": "string", "minLength": 1 },
        "type": {
          "type": "string",
          "enum": [
            "heading",
            "paragraph",
            "list",
            "table",
            "footnote",
            "caption",
            "code",
            "other"
          ]
        },

        "source_content_ref": {
          "type": "object",
          "additionalProperties": false,
          "description": "Reference to original content (hashes or retrieval token).",
          "required": ["content_hash"],
          "properties": {
            "content_hash": { "type": "string", "minLength": 32 },
            "content_ref": { "type": "string", "description": "Optional pointer to stored raw content if enabled." }
          }
        },

        "translated_content": {
          "description": "Translated content mirrors block type.",
          "oneOf": [
            { "type": "string" },
            { "$ref": "#/$defs/translated_list_content" },
            { "$ref": "#/$defs/translated_table_content" }
          ]
        },

        "meta": { "type": "object", "additionalProperties": true },

        "segment_map": {
          "type": "array",
          "description": "For UI highlighting and audit linking: map internal segment ids to this block.",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["segment_id", "source_hash", "target_hash"],
            "properties": {
              "segment_id": { "type": "string", "minLength": 1 },
              "source_hash": { "type": "string", "minLength": 32 },
              "target_hash": { "type": "string", "minLength": 32 }
            }
          }
        }
      }
    },

    "translated_list_content": {
      "type": "object",
      "additionalProperties": false,
      "required": ["ordered", "items"],
      "properties": {
        "ordered": { "type": "boolean" },
        "items": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["item_id", "translated_text"],
            "properties": {
              "item_id": { "type": "string", "minLength": 1 },
              "translated_text": { "type": "string" },
              "meta": { "type": "object", "additionalProperties": true }
            }
          }
        }
      }
    },

    "translated_table_content": {
      "type": "object",
      "additionalProperties": false,
      "required": ["table_id", "rows"],
      "properties": {
        "table_id": { "type": "string", "minLength": 1 },
        "title": { "type": "string" },
        "caption": { "type": "string" },
        "grid": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "row_count": { "type": "integer", "minimum": 1 },
            "col_count": { "type": "integer", "minimum": 1 }
          }
        },
        "header": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "header_rows": { "type": "integer", "minimum": 0 },
            "header_cols": { "type": "integer", "minimum": 0 }
          }
        },
        "rows": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/translated_table_row" }
        }
      }
    },

    "translated_table_row": {
      "type": "object",
      "additionalProperties": false,
      "required": ["row_id", "cells"],
      "properties": {
        "row_id": { "type": "string", "minLength": 1 },
        "cells": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/translated_table_cell" }
        }
      }
    },

    "translated_table_cell": {
      "type": "object",
      "additionalProperties": false,
      "required": ["cell_id", "translated_value"],
      "properties": {
        "cell_id": { "type": "string", "minLength": 1 },
        "translated_value": {
          "oneOf": [
            { "type": "string" },
            { "type": "number" },
            { "type": "null" }
          ]
        },
        "cell_type": {
          "type": "string",
          "enum": ["text", "numeric", "unit", "mixed", "code", "empty"]
        },
        "meta": { "type": "object", "additionalProperties": true }
      }
    },

    "violation_pointer": {
      "type": "object",
      "additionalProperties": false,
      "required": ["violation_id", "location"],
      "properties": {
        "violation_id": { "type": "string", "minLength": 1 },
        "location": { "$ref": "#/$defs/location" }
      }
    },

    "location": {
      "type": "object",
      "additionalProperties": false,
      "required": ["block_id", "kind"],
      "properties": {
        "block_id": { "type": "string", "minLength": 1 },
        "kind": { "type": "string", "enum": ["segment", "list_item", "table_cell"] },

        "segment_id": { "type": "string" },

        "item_id": { "type": "string" },

        "table": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "table_id": { "type": "string" },
            "row_id": { "type": "string" },
            "cell_id": { "type": "string" }
          }
        }
      },
      "allOf": [
        {
          "if": { "properties": { "kind": { "const": "segment" } } },
          "then": { "required": ["segment_id"] }
        },
        {
          "if": { "properties": { "kind": { "const": "list_item" } } },
          "then": { "required": ["item_id"] }
        },
        {
          "if": { "properties": { "kind": { "const": "table_cell" } } },
          "then": { "required": ["table"] }
        }
      ]
    }
  }
}

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://synaptyx.ai/schemas/transmax/v1/quality_report_with_locations.schema.json",
  "title": "TransMax Quality Report (Extended with Locations)",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "checks_run", "violations", "summary"],
  "properties": {
    "schema_version": { "type": "string", "const": "transmax.quality.v1loc" },
    "checks_run": { "type": "array", "minItems": 1, "items": { "type": "string" } },
    "violations": {
      "type": "array",
      "items": { "$ref": "#/$defs/violation_with_location" }
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
          "additionalProperties": { "type": "integer", "minimum": 0 }
        }
      }
    }
  },
  "$defs": {
    "severity": { "type": "string", "enum": ["critical", "major", "minor"] },
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

    "location": {
      "type": "object",
      "additionalProperties": false,
      "required": ["block_id", "kind"],
      "properties": {
        "block_id": { "type": "string", "minLength": 1 },
        "kind": { "type": "string", "enum": ["segment", "list_item", "table_cell"] },
        "segment_id": { "type": "string" },
        "item_id": { "type": "string" },
        "table": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "table_id": { "type": "string" },
            "row_id": { "type": "string" },
            "cell_id": { "type": "string" }
          }
        }
      },
      "allOf": [
        {
          "if": { "properties": { "kind": { "const": "segment" } } },
          "then": { "required": ["segment_id"] }
        },
        {
          "if": { "properties": { "kind": { "const": "list_item" } } },
          "then": { "required": ["item_id"] }
        },
        {
          "if": { "properties": { "kind": { "const": "table_cell" } } },
          "then": { "required": ["table"] }
        }
      ]
    },

    "evidence": {
      "type": "object",
      "additionalProperties": false,
      "required": ["method"],
      "properties": {
        "method": {
          "type": "string",
          "enum": ["regex", "numeric_parse", "unit_parse", "glossary_match", "tokeniser_match", "diff_alignment", "custom_rule"]
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

    "violation_with_location": {
      "type": "object",
      "additionalProperties": false,
      "required": ["violation_id", "type", "severity", "message", "evidence", "location"],
      "properties": {
        "violation_id": {
          "type": "string",
          "description": "Stable id for UI linking. e.g., v-000123",
          "pattern": "^v-[0-9]{6}$"
        },
        "type": { "$ref": "#/$defs/violation_type" },
        "severity": { "$ref": "#/$defs/severity" },
        "message": { "type": "string", "minLength": 1 },
        "evidence": { "$ref": "#/$defs/evidence" },
        "location": { "$ref": "#/$defs/location" },
        "suggested_action": {
          "type": "string",
          "enum": ["auto_fix", "needs_review", "block_output"],
          "default": "needs_review"
        }
      }
    }
  }
}
