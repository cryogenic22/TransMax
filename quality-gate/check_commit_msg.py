#!/usr/bin/env python3
"""
Commit Message Format Checker
=============================
Enforces conventional commits format.

Format: <type>(<scope>): <description>

Types:
  feat     - New feature
  fix      - Bug fix
  docs     - Documentation only
  style    - Code style (formatting, semicolons, etc.)
  refactor - Code refactoring (no feature/fix)
  perf     - Performance improvement
  test     - Adding/updating tests
  build    - Build system changes
  ci       - CI configuration
  chore    - Other changes (deps, config, etc.)
  revert   - Revert previous commit

Examples:
  feat(auth): add OAuth2 login
  fix(api): handle null response from external service
  docs: update README with new setup instructions
  refactor(components): extract Button from Form

Rules:
  1. Type is required and must be from the list above
  2. Scope is optional but encouraged
  3. Description must be 10-72 characters
  4. Description must start with lowercase
  5. Description must not end with period
"""

import re
import sys
from pathlib import Path

# Conventional commits pattern
COMMIT_PATTERN = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"  # type
    r"(\([a-z0-9_-]+\))?"  # optional scope
    r"!?"  # optional breaking change indicator
    r": "  # separator
    r"(.{10,72})"  # description (10-72 chars)
    r"$",
    re.MULTILINE,
)

# Alternative patterns we also accept
MERGE_PATTERN = re.compile(r"^Merge (branch|pull request|remote-tracking branch)")
REVERT_PATTERN = re.compile(r'^Revert "')
WIP_PATTERN = re.compile(r"^WIP:", re.IGNORECASE)
RELEASE_PATTERN = re.compile(r"^(v?\d+\.\d+\.\d+|Release \d+)")

# Patterns that indicate AI-generated commits (acceptable)
AI_GENERATED_PATTERN = re.compile(r"Generated with \[Claude Code\]|Co-Authored-By: Claude")


def check_commit_message(message: str) -> tuple[bool, str]:
    summary = _commit_summary(message)
    if not summary:
        return False, "Empty commit summary line"
    if _is_allowed_special_case(summary):
        return True, ""
    return _validate_conventional_commit(summary)


def _commit_summary(message: str) -> str:
    lines = message.strip().split("\n")
    if not lines:
        return ""
    return lines[0].strip()


def _is_allowed_special_case(summary: str) -> bool:
    return bool(
        MERGE_PATTERN.match(summary)
        or REVERT_PATTERN.match(summary)
        or WIP_PATTERN.match(summary)
        or RELEASE_PATTERN.match(summary)
    )


def _validate_conventional_commit(summary: str) -> tuple[bool, str]:
    match = COMMIT_PATTERN.match(summary)
    if not match:
        return _format_error(summary)
    description = match.group(3)
    ok, error = _validate_description(description)
    return (ok, error) if not ok else (True, "")


def _format_error(summary: str) -> tuple[bool, str]:
    if ":" not in summary:
        return (
            False,
            "Missing type prefix. Use: feat|fix|docs|style|refactor|perf|test|build|ci|chore: <description>",
        )
    commit_type, desc = (part.strip() for part in summary.split(":", 1))
    ok, error = _validate_type(commit_type)
    if not ok:
        return False, error
    ok, error = _validate_description(desc)
    if not ok:
        return False, error
    return False, "Invalid format. Expected: type(scope): description (10-72 chars)"


def _validate_type(commit_type: str) -> tuple[bool, str]:
    valid_types = {
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
    }
    type_without_scope = re.sub(r"\([^)]+\)", "", commit_type.strip().lower())
    if type_without_scope not in valid_types:
        return (
            False,
            f"Invalid type '{type_without_scope}'. Valid types: {', '.join(sorted(valid_types))}",
        )
    return True, ""


def _validate_description(desc: str) -> tuple[bool, str]:
    description = desc.strip()
    if len(description) < 10:
        return False, f"Description too short ({len(description)} chars). Minimum 10 characters."
    if len(description) > 72:
        return False, f"Description too long ({len(description)} chars). Maximum 72 characters."
    if description[0].isupper():
        return False, "Description should start with lowercase letter"
    if description.endswith("."):
        return False, "Description should not end with a period"
    if _is_lazy_description(description):
        return False, f"Description too vague: '{description}'. Be specific about what changed."
    return True, ""


def _is_lazy_description(description: str) -> bool:
    lazy_patterns = [
        r"^(update|fix|change|modify|edit)s?$",
        r"^(update|fix|change|modify|edit)s? (stuff|things|code|it)$",
        r"^wip$",
        r"^work in progress$",
        r"^minor( changes)?$",
        r"^misc( changes)?$",
    ]
    return any(re.match(pattern, description, re.IGNORECASE) for pattern in lazy_patterns)


def main():
    """Main entry point for commit-msg hook."""
    # Get commit message file path from git
    if len(sys.argv) < 2:
        print("Usage: check_commit_msg.py <commit-msg-file>")
        sys.exit(1)

    commit_msg_file = Path(sys.argv[1])

    if not commit_msg_file.exists():
        print(f"Error: Commit message file not found: {commit_msg_file}")
        sys.exit(1)

    message = commit_msg_file.read_text(encoding="utf-8")

    # Skip if it's an AI-generated commit (we trust Claude)
    if AI_GENERATED_PATTERN.search(message):
        sys.exit(0)

    passed, error = check_commit_message(message)

    if passed:
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("COMMIT MESSAGE REJECTED")
        print("=" * 60)
        print(f"\nError: {error}")
        print("\nExpected format:")
        print("  <type>(<scope>): <description>")
        print("\nTypes: feat, fix, docs, style, refactor, perf, test, build, ci, chore")
        print("\nExamples:")
        print("  feat(auth): add OAuth2 login support")
        print("  fix(api): handle null response gracefully")
        print("  docs: update installation instructions")
        print("=" * 60 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
