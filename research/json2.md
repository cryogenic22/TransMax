{
  "example_id": "ex-ar-001",
  "description": "Arabic mixed-script safety sentence with unit mismatch caught and fixed; ends as REVIEW_REQUIRED due to Arabic digit policy warning.",
  "request_payload": {
    "content": "Patient must take 10 mg daily.",
    "source_language": "en",
    "target_language": "ar",
    "domain": "labeling",
    "audience": "patient",
    "risk_level": "high",
    "requirements": {
      "tone": "plain_language",
      "glossary_id": "global_pharma_v2",
      "tm_id": "client_tm_2026",
      "arabic_digits_policy": "preserve_western",
      "decimal_separator_policy": "preserve_source"
    }
  },
  "audit_record": {
    "schema_version": "transmax.audit.v1",
    "audit_trail_id": "6d6d7b0a-5d0b-4c74-9d0a-1e2f5dbb3c3d",
    "created_at": "2026-01-17T10:12:45Z",
    "tenant": {
      "tenant_id": "pharma_co_001",
      "environment": "prod",
      "data_policy": {
        "store_raw_input": false,
        "store_raw_output": false,
        "raw_retention_days": 0
      }
    },
    "request": {
      "request_id": "req-20260117-00041",
      "caller": {
        "caller_app": "vault-labeling-pipeline",
        "caller_user_id": "svc-labeling-automation",
        "ip_hash": "sha256:2b4c6e0a1c2d4f..."
      },
      "source_language": "en",
      "target_language": "ar",
      "script_direction": "rtl",
      "domain": "labeling",
      "audience": "patient",
      "risk_level": "high",
      "requirements": {
        "tone": "plain_language",
        "glossary_id": "global_pharma_v2",
        "tm_id": "client_tm_2026",
        "arabic_digits_policy": "preserve_western",
        "decimal_separator_policy": "preserve_source"
      },
      "input_size": {
        "chars": 28,
        "words_estimate": 5,
        "segments": 1
      }
    },
    "versions": {
      "language_pack": {
        "pack_id": "ar_pack",
        "pack_version": "1.0.0",
        "tokeniser": "custom_ar",
        "normalisation_profile": "ar_v1"
      },
      "policy": {
        "policy_id": "transmax_policy_default",
        "policy_version": "1.1.0"
      },
      "prompt": {
        "prompt_id": "transmax_translate_prompt",
        "prompt_version": "1.3.2"
      },
      "model": {
        "provider": "openai",
        "name": "gpt-4o",
        "version": "2026-01"
      },
      "glossary": {
        "glossary_id": "global_pharma_v2",
        "glossary_version": "2.4.0"
      },
      "translation_memory": {
        "tm_id": "client_tm_2026",
        "tm_version": "2026.01.05"
      }
    },
    "artifacts": {
      "hashes": {
        "hash_algo": "sha256",
        "input_hash": "sha256:4a1b87a8b7f8cfe1c85a2dfc5b2d3f88d7d0f7d2b6c3a5a91e4e7b9a2c1d0e3f",
        "output_hash": "sha256:bd9b1aa8a2c8c8d7c61a1b7d55fd6c68b9a0c3a71f2d1b4b9b0d3e5f2a1c9d8e",
        "manifest_hash": "sha256:2f1c9a8b7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a"
      },
      "segmentation": {
        "segment_count": 1,
        "segments": [
          {
            "segment_id": "seg-001",
            "source_hash": "sha256:9b0c7a1e4d2f...",
            "target_hash": "sha256:ab11cc22dd33...",
            "type": "sentence"
          }
        ]
      },
      "iterations": [
        {
          "iteration_index": 0,
          "started_at": "2026-01-17T10:12:45Z",
          "ended_at": "2026-01-17T10:12:47Z",
          "llm_usage": { "input_tokens": 412, "output_tokens": 86, "cost_estimate": 0.0042 },
          "actions_taken": [],
          "gate_summary": {
            "checks_run": [
              "glossary_mandatory_terms",
              "numeric_consistency",
              "unit_consistency",
              "frequency_consistency",
              "negation_flip_check",
              "ar_digit_policy_check",
              "ar_unit_adjacency_check"
            ],
            "violation_counts": { "critical": 1, "major": 0, "minor": 1 }
          }
        },
        {
          "iteration_index": 1,
          "started_at": "2026-01-17T10:12:47Z",
          "ended_at": "2026-01-17T10:12:49Z",
          "llm_usage": { "input_tokens": 291, "output_tokens": 61, "cost_estimate": 0.0031 },
          "actions_taken": [
            {
              "action_type": "fix_unit_format",
              "segment_id": "seg-001",
              "reason": { "violation_type": "unit_mismatch", "rule_id": "unit_parse.v1" },
              "before_hash": "sha256:aa00bb11cc22...",
              "after_hash": "sha256:aa00bb11cc99...",
              "notes": "Restored mg to match source."
            }
          ],
          "gate_summary": {
            "checks_run": [
              "glossary_mandatory_terms",
              "numeric_consistency",
              "unit_consistency",
              "frequency_consistency",
              "negation_flip_check",
              "ar_digit_policy_check",
              "ar_unit_adjacency_check"
            ],
            "violation_counts": { "critical": 0, "major": 0, "minor": 1 }
          }
        }
      ]
    },
    "quality": {
      "schema_version": "transmax.quality.v1",
      "checks_run": [
        "glossary_mandatory_terms",
        "numeric_consistency",
        "unit_consistency",
        "frequency_consistency",
        "negation_flip_check",
        "ar_digit_policy_check",
        "ar_unit_adjacency_check"
      ],
      "violations": [
        {
          "type": "ar_digit_form_changed",
          "severity": "minor",
          "segment_id": "seg-001",
          "message": "Arabic digit policy set to preserve Western digits. Output uses Arabic-Indic digits in one span.",
          "evidence": {
            "method": "custom_rule",
            "rule_id": "ar_digit_policy.v1",
            "source_span": { "text": "10 mg", "start": 18, "end": 23 },
            "target_span": { "text": "١٠ mg", "start": 16, "end": 21 },
            "expected": "10",
            "observed": "١٠"
          },
          "suggested_action": "auto_fix"
        }
      ],
      "summary": {
        "counts_by_severity": { "critical": 0, "major": 0, "minor": 1 },
        "counts_by_type": { "ar_digit_form_changed": 1 }
      }
    },
    "decision": {
      "status": "REVIEW_REQUIRED",
      "scores": {
        "terminology": 0.99,
        "safety": 0.98,
        "format": 0.96,
        "overall": 0.97
      },
      "policy_explanation": "High-risk labeling policy for Arabic requires review until validated to allow PASS."
    },
    "integrity": {
      "hash_algo": "sha256",
      "record_hash": "sha256:0f1e2d3c4b5a69788796a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4",
      "signature": {
        "key_id": "kms-key-prod-01",
        "sig_algo": "ed25519",
        "signature_b64": "MEQCIBk3...r0c="
      }
    }
  },
  "translate_response": {
    "translation": "يجب على المريض تناول 10 mg يومياً.",
    "decision": "REVIEW_REQUIRED",
    "scores": { "terminology": 0.99, "safety": 0.98, "format": 0.96, "overall": 0.97 },
    "quality_report": {
      "violations": [
        {
          "type": "ar_digit_form_changed",
          "severity": "minor",
          "segment_id": "seg-001",
          "message": "Arabic digit policy set to preserve Western digits. Output uses Arabic-Indic digits in one span."
        }
      ]
    },
    "audit_trail_id": "6d6d7b0a-5d0b-4c74-9d0a-1e2f5dbb3c3d"
  }
}
