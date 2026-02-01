{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://synaptyx.ai/schemas/transmax/v1/document_request.schema.json",
  "title": "TransMax Document Translation Request",
  "type": "object",
  "additionalProperties": false,
  "required": ["document", "target_language", "domain", "audience", "risk_level", "requirements"],
  "properties": {
    "document": {
      "type": "object",
      "additionalProperties": false,
      "required": ["doc_type", "source_language", "blocks"],
      "properties": {
        "doc_id": { "type": "string" },
        "doc_type": {
          "type": "string",
          "enum": ["pil", "smpc", "labeling", "cmc", "qos", "csr", "other"]
        },
        "source_language": { "type": "string", "minLength": 2, "maxLength": 16 },
        "meta": {
          "type": "object",
          "additionalProperties": true,
          "description": "Optional client metadata (country, product, version, etc.)."
        },
        "blocks": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/block" }
        }
      }
    },
    "target_language": { "type": "string", "minLength": 2, "maxLength": 16 },
    "domain": { "type": "string", "minLength": 1 },
    "audience": { "type": "string", "enum": ["hcp", "patient", "internal"] },
    "risk_level": { "type": "string", "enum": ["low", "medium", "high"] },
    "requirements": {
      "type": "object",
      "additionalProperties": false,
      "required": ["glossary_id"],
      "properties": {
        "glossary_id": { "type": "string", "minLength": 1 },
        "tm_id": { "type": "string" },
        "tone": { "type": "string" },
        "locale": { "type": "string" },
        "arabic_digits_policy": { "type": "string", "enum": ["preserve_western", "prefer_arabic_indic", "allow_either"] },
        "decimal_separator_policy": { "type": "string", "enum": ["preserve_source", "locale_default"] }
      }
    },
    "options": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "mode": { "type": "string", "enum": ["sync", "async"], "default": "async" },
        "max_iterations": { "type": "integer", "minimum": 0, "maximum": 5, "default": 2 },
        "store_raw_text": { "type": "boolean", "default": false },
        "callback_url": { "type": "string", "format": "uri" }
      }
    }
  },
  "$defs": {
    "block": {
      "type": "object",
      "additionalProperties": false,
      "required": ["block_id", "type", "content"],
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
        "content": {
          "description": "Block content depends on type.",
          "oneOf": [
            { "type": "string" },
            { "$ref": "#/$defs/list_content" },
            { "$ref": "#/$defs/table_content" }
          ]
        },
        "meta": {
          "type": "object",
          "additionalProperties": true,
          "description": "Optional block metadata: style, numbering, source offsets, etc."
        }
      }
    },
    "list_content": {
      "type": "object",
      "additionalProperties": false,
      "required": ["items"],
      "properties": {
        "ordered": { "type": "boolean", "default": false },
        "items": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["item_id", "text"],
            "properties": {
              "item_id": { "type": "string", "minLength": 1 },
              "text": { "type": "string" },
              "meta": { "type": "object", "additionalProperties": true }
            }
          }
        }
      }
    },
    "table_content": {
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
          "description": "Optional explicit grid size. If omitted, inferred from rows/cells.",
          "properties": {
            "row_count": { "type": "integer", "minimum": 1 },
            "col_count": { "type": "integer", "minimum": 1 }
          }
        },
        "header": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "header_rows": { "type": "integer", "minimum": 0, "default": 0 },
            "header_cols": { "type": "integer", "minimum": 0, "default": 0 }
          }
        },
        "rows": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/table_row" }
        }
      }
    },
    "table_row": {
      "type": "object",
      "additionalProperties": false,
      "required": ["row_id", "cells"],
      "properties": {
        "row_id": { "type": "string", "minLength": 1 },
        "cells": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/table_cell" }
        }
      }
    },
    "table_cell": {
      "type": "object",
      "additionalProperties": false,
      "required": ["cell_id", "cell_type", "value"],
      "properties": {
        "cell_id": { "type": "string", "minLength": 1 },
        "cell_type": {
          "type": "string",
          "enum": ["text", "numeric", "unit", "mixed", "code", "empty"]
        },
        "value": {
          "description": "Cell value. For mixed, use string and rely on gates for preservation.",
          "oneOf": [
            { "type": "string" },
            { "type": "number" },
            { "type": "null" }
          ]
        },
        "rowspan": { "type": "integer", "minimum": 1, "default": 1 },
        "colspan": { "type": "integer", "minimum": 1, "default": 1 },
        "meta": {
          "type": "object",
          "additionalProperties": true,
          "properties": {
            "is_header": { "type": "boolean", "default": false },
            "locked": {
              "type": "boolean",
              "default": false,
              "description": "If true, value must not change (e.g., numeric/unit/code cells)."
            },
            "format": { "type": "string", "description": "Optional formatting hint, e.g. '0.00', 'mg', etc." }
          }
        }
      }
    }
  }
}
