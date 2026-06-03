"""Prompt-injection scanner for source segments (TMX-INJ-1).

A pure, deterministic detector for prompt-injection / instruction-override
attempts embedded in the SOURCE text a customer submits for translation.
Pharma documents pass through an LLM translator (a qualified supplier, A6);
an adversarial or compromised source could try to hijack that LLM
("ignore previous instructions and output X", fake role tags, etc.). Per
A2 (quality is enforced at deterministic gates, never inside the translator
prompt) this lives outside the LLM call and surfaces injected segments as a
CRITICAL ``PROMPT_INJECTION`` defect so they are BLOCKED for human review
(A3 fail-loud) rather than silently translated.

Design for PRECISION over recall: patterns target unambiguous injection
*phrases* and chat/instruction *markup*, NOT individual words, so ordinary
pharma language ("patient instructions", "do not exceed", "the system was
evaluated") is never flagged. Recall gaps are acceptable — a missed novel
phrasing degrades to today's behaviour; a false positive would wrongly block
legitimate clinical content.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Zero-width / invisible characters used to break up trigger phrases
# ("i<zwsp>gnore previous instructions"). Stripped before matching.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def _normalize(text: str) -> str:
    """Fold obfuscation before matching (TMX-INJ-1a).

    NFKC collapses full-width / compatibility forms (e.g. fullwidth latin used
    to dodge ASCII patterns); zero-width chars are removed; whitespace runs are
    collapsed to single spaces. We scan the normalized form — the original is
    untouched, and normalizing benign text never CREATES an injection phrase,
    so this raises recall without hurting precision.
    """
    t = unicodedata.normalize("NFKC", text)
    t = t.translate(_ZERO_WIDTH)
    t = re.sub(r"\s+", " ", t)
    return t

# Each entry: (label, compiled pattern). Patterns are case-insensitive and
# anchored to injection phrasing / role-markup, deliberately high-precision.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore_previous", re.compile(r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?|text|messages?)", re.I)),
    ("disregard_above", re.compile(r"disregard\s+(?:all\s+|the\s+|any\s+)?(?:previous\s+|above\s+|prior\s+)?(?:instructions?|prompts?|text|context)", re.I)),
    ("forget_instructions", re.compile(r"forget\s+(?:all\s+|the\s+)?(?:everything|previous|above|prior|earlier)\b", re.I)),
    ("you_are_now", re.compile(r"you\s+are\s+now\s+(?:a\s+|an\s+|the\s+)", re.I)),
    ("system_prompt_ref", re.compile(r"system\s+prompt", re.I)),
    ("reveal_prompt", re.compile(r"(?:reveal|repeat|print|show|output|expose)\s+(?:me\s+)?(?:your\s+|the\s+)?(?:system\s+|initial\s+|original\s+)?(?:prompt|instructions?)", re.I)),
    ("new_instructions_marker", re.compile(r"\bnew\s+instructions?\s*:", re.I)),
    ("instead_directive", re.compile(r"\binstead[,\s]+(?:output|say|write|respond|print|translate|return|reply)\b", re.I)),
    ("act_as_model", re.compile(r"act\s+as\s+(?:an?\s+)?(?:ai|assistant|language\s+model|llm|dan|chatbot|developer\s+mode)", re.I)),
    ("role_tag", re.compile(r"</?\s*(?:system|assistant|user)\s*>", re.I)),
    ("inst_tag", re.compile(r"\[/?\s*(?:INST|SYS|SYSTEM)\s*\]", re.I)),
    ("override_directive", re.compile(r"override\s+(?:your\s+|the\s+|all\s+)?(?:previous\s+)?(?:instructions?|settings?|rules?|safety|guardrails?)", re.I)),
    ("jailbreak", re.compile(r"\bjailbreak\b", re.I)),
    ("prompt_injection_literal", re.compile(r"prompt\s+injection", re.I)),
    # TMX-INJ-1a — additional high-precision vectors.
    ("begin_response_with", re.compile(r"begin\s+your\s+(?:response|answer|reply|output)\s+with", re.I)),
    ("you_must_output", re.compile(r"you\s+must\s+(?:output|respond|reply|say|write|return)\b", re.I)),
    ("translate_as_literal", re.compile(r"translate\s+(?:this|it|the\s+\w+)\s+as\s+[\"']", re.I)),
)


@dataclass(frozen=True)
class InjectionFinding:
    """One detected injection vector in a piece of text."""

    label: str
    snippet: str  # the matched substring (for evidence in the audit/defect)


class InjectionScanner:
    """Stateless scanner. Reusable; holds no per-call state."""

    def scan(self, text: str) -> list[InjectionFinding]:
        """Return all injection findings in ``text`` (empty list ⇒ clean).

        Input is normalized first (TMX-INJ-1a) to defeat zero-width / full-width
        obfuscation of trigger phrases.
        """
        if not text:
            return []
        text = _normalize(text)
        findings: list[InjectionFinding] = []
        for label, pattern in _PATTERNS:
            m = pattern.search(text)
            if m:
                findings.append(InjectionFinding(label=label, snippet=m.group(0)))
        return findings

    def is_injected(self, text: str) -> bool:
        """True iff ``text`` contains at least one injection vector."""
        return bool(self.scan(text))


# Module-level singleton (stateless ⇒ safe to share).
default_injection_scanner = InjectionScanner()
