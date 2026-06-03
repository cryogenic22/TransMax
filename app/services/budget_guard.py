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

    @classmethod
    def from_settings(cls) -> "JobBudget":
        """Build the per-job budget from the global settings (opt-in limits)."""
        from app.core.config import settings
        return cls(
            max_tokens=getattr(settings, "max_tokens_per_job", None),
            max_cost_usd=getattr(settings, "max_cost_usd_per_job", None),
        )

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


def budget_posture(
    tokens_used: int,
    cost_used_usd: float,
    budget: JobBudget,
    threshold: float = 0.8,
) -> str:
    """Router cost-posture for a job's consumption so far (TMX-ROUTER-5).

    Returns ``"constrained"`` once consumption reaches ``threshold`` (default
    80%) of either configured limit — the LLM router downgrades the model tier
    one step in that case (cost-aware selection). A disabled budget is always
    ``"normal"``, so this is a no-op until per-job budgets are configured.
    """
    if not budget.is_enabled:
        return "normal"
    if budget.max_tokens is not None and tokens_used >= threshold * budget.max_tokens:
        return "constrained"
    if budget.max_cost_usd is not None and cost_used_usd >= threshold * budget.max_cost_usd:
        return "constrained"
    return "normal"
