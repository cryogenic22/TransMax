from __future__ import annotations

from pathlib import Path
from typing import Any

from .checks_governance import check_exception_debt


def apply(*, root_dir: Path, config: dict[str, Any], add_issue) -> None:
    check_exception_debt(root_dir=root_dir, config=config, add_issue=add_issue)

