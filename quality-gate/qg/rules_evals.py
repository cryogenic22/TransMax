from __future__ import annotations

from pathlib import Path
from typing import Any

from .checks_evals import check_baseline_exists, check_eval_coverage, check_eval_thresholds


def apply(*, root_dir: Path, config: dict[str, Any], add_issue) -> None:
    check_eval_coverage(root_dir=root_dir, config=config, add_issue=add_issue)
    check_eval_thresholds(root_dir=root_dir, config=config, add_issue=add_issue)
    check_baseline_exists(root_dir=root_dir, config=config, add_issue=add_issue)

