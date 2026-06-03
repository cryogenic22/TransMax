"""Per-job LLM budget guard (TMX-BUDGET-1).

A pure, side-effect-free value object that decides whether a translation
job's accumulated qualified-supplier consumption (token + cost, sourced from
the A6-2 accumulators) has crossed a configured ceiling.

The guard is **opt-in**: a ``JobBudget`` with both limits ``None`` is disabled
and never trips, so existing jobs are unaffected (addendum: config-not-
branching — limits live in settings, not in `if` ladders).

Enforcement is cooperative and lives in the translation engine: when the
guard reports ``is_exceeded`` the engine stops scheduling LLM calls and marks
the unspent segments ``BLOCKED`` with reason ``budget_exceeded`` (A3 — fail
loud; never silently truncate or mistranslate) and records a
``BUDGET_EXCEEDED`` audit event (A1).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class JobBudget:
    """An immutable per-job consumption ceiling.

    Either limit may be ``None`` (that dimension is unbounded). A budget with
    BOTH limits ``None`` is disabled — :py:meth:`is_exceeded` always returns
    ``False``.
    """

    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None

    @property
    def is_enabled(self) -> bool:
        """True iff at least one limit is set."""
        return self.max_tokens is not None or self.max_cost_usd is not None

    def is_exceeded(self, tokens: int, cost_usd: float) -> bool:
        """Whether ``tokens``/``cost_usd`` consumed so far exceed this budget.

        A limit is breached only when consumption is STRICTLY GREATER than the
        limit — being exactly at the limit is within budget. A ``None`` limit
        is never breached. Returns ``False`` for a disabled budget.
        """
        if self.max_tokens is not None and tokens > self.max_tokens:
            return True
        if self.max_cost_usd is not None and cost_usd > self.max_cost_usd:
            return True
        return False
