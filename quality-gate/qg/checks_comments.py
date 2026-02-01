from __future__ import annotations

import io
import tokenize
from dataclasses import dataclass


def python_comment_tokens(content: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(content).readline):
            if tok.type == tokenize.COMMENT:
                out.append((int(tok.start[0]), str(tok.string)))
    except tokenize.TokenError:
        return out
    return out


def js_comment_tokens(lines: list[str]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    in_block = False
    for i, line in enumerate(lines, 1):
        if in_block:
            out.append((i, line))
            in_block = "*/" not in line
            continue

        start, is_block = _comment_start(line)
        if start is None:
            continue
        out.append((i, line[start:]))
        if is_block:
            in_block = "*/" not in line[start:]
    return out


def _comment_start(line: str) -> tuple[int | None, bool]:
    idx_line = line.find("//")
    idx_block = line.find("/*")
    if idx_line < 0 and idx_block < 0:
        return None, False
    if idx_block >= 0 and (idx_line < 0 or idx_block < idx_line):
        return idx_block, True
    return idx_line, False


@dataclass(slots=True)
class _StripState:
    mode: str  # code | line_comment | block_comment | single | double | template | regex
    escape: bool = False
    in_char_class: bool = False


def strip_js_ts_strings_and_comments(text: str) -> str:
    out: list[str] = []
    state = _StripState(mode="code", escape=False)
    i = 0
    while i < len(text):
        i += _strip_step(text, i, out, state)
    return "".join(out)


def _strip_step(text: str, i: int, out: list[str], state: _StripState) -> int:
    ch = text[i]
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if state.mode == "line_comment":
        return _step_line_comment(ch, out, state)
    if state.mode == "block_comment":
        return _step_block_comment(ch, nxt, out, state)
    if state.mode == "single":
        return _step_string(ch, out, state, end="'")
    if state.mode == "double":
        return _step_string(ch, out, state, end='"')
    if state.mode == "template":
        return _step_string(ch, out, state, end="`")
    if state.mode == "regex":
        return _step_regex(ch, out, state)
    return _step_code(text, i, ch, nxt, out, state)


def _step_line_comment(ch: str, out: list[str], state: _StripState) -> int:
    if ch == "\n":
        state.mode = "code"
        out.append("\n")
    else:
        out.append(" ")
    return 1


def _step_block_comment(ch: str, nxt: str, out: list[str], state: _StripState) -> int:
    if ch == "*" and nxt == "/":
        state.mode = "code"
        out.append("  ")
        return 2
    out.append("\n" if ch == "\n" else " ")
    return 1


def _step_string(ch: str, out: list[str], state: _StripState, *, end: str) -> int:
    if state.escape:
        state.escape = False
        out.append(" " if ch != "\n" else "\n")
        return 1
    if ch == "\\":
        state.escape = True
        out.append(" ")
        return 1
    if ch == end:
        state.mode = "code"
    out.append("\n" if ch == "\n" else " ")
    return 1


def _step_code(text: str, i: int, ch: str, nxt: str, out: list[str], state: _StripState) -> int:
    if ch == "/" and nxt in {"/", "*"}:
        state.mode = "line_comment" if nxt == "/" else "block_comment"
        out.append("  ")
        return 2
    if ch == "/" and nxt and _looks_like_regex_start(text, i, nxt):
        state.mode = "regex"
        state.escape = False
        state.in_char_class = False
        out.append(" ")
        return 1
    mode = {"'": "single", '"': "double", "`": "template"}.get(ch)
    if mode:
        state.mode = mode
        out.append(" ")
        return 1
    out.append(ch)
    return 1


def _step_regex(ch: str, out: list[str], state: _StripState) -> int:
    if state.escape:
        state.escape = False
        out.append("\n" if ch == "\n" else " ")
        return 1
    if ch == "\\":
        state.escape = True
        out.append(" ")
        return 1
    if not state.in_char_class:
        if ch == "[":
            state.in_char_class = True
            out.append(" ")
            return 1
        if ch == "/":
            state.mode = "code"
            out.append(" ")
            return 1
    elif ch == "]":
        state.in_char_class = False
        out.append(" ")
        return 1
    out.append("\n" if ch == "\n" else " ")
    return 1


def _looks_like_regex_start(text: str, i: int, nxt: str) -> bool:
    # Heuristic regex literal detection for stripping-only passes.
    # Goal: avoid mis-parsing regex bodies (which may contain quotes/comment-like tokens)
    # as real JS/TS strings/comments, which breaks brace tracking.
    if nxt in {'"', "'", "[", "\\", "^", "$", "."}:
        return True

    prev = _prev_non_ws(text, i - 1)
    if not prev:
        return True
    if prev in "([{:;,!?&|^~<>+-*%=":
        return True

    keyword = _prev_identifier(text, i - 1)
    return keyword in {"return", "throw", "case", "typeof", "instanceof", "in", "of"}


def _prev_non_ws(text: str, start: int) -> str:
    j = start
    while j >= 0:
        ch = text[j]
        if not ch.isspace():
            return ch
        j -= 1
    return ""


def _prev_identifier(text: str, start: int) -> str:
    j = start
    while j >= 0 and text[j].isspace():
        j -= 1
    end = j + 1
    while j >= 0 and (text[j].isalnum() or text[j] == "_"):
        j -= 1
    ident = text[j + 1 : end].strip()
    return ident
