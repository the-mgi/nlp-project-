"""Unified-diff helpers: split source/test files, added-line maps, size statistics."""
from __future__ import annotations

import re

TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_tests?\.py$|(^|/)conftest\.py$")

_FILE_SPLIT = re.compile(r"(?=^diff --git )", re.M)
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def split_files(diff: str) -> list[str]:
    return [f for f in _FILE_SPLIT.split(diff) if f.startswith("diff --git")]


def file_path(file_diff: str) -> str:
    m = re.search(r"^\+\+\+ b/(.+)$", file_diff, re.M)
    if m:
        return m.group(1).strip()
    m = re.search(r"^diff --git a/(\S+) b/(\S+)", file_diff, re.M)
    return m.group(2) if m else ""


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH_RE.search(path))


def added_lines(file_diff: str) -> set[int]:
    """1-indexed line numbers (in the new file) of lines added by a file diff."""
    out, new_ln = set(), None
    for line in file_diff.splitlines():
        m = _HUNK.match(line)
        if m:
            new_ln = int(m.group(3))
            continue
        if new_ln is None or line.startswith(("+++", "---")) and new_ln is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            out.add(new_ln)
            new_ln += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass
        elif line.startswith("\\"):
            pass
        else:
            new_ln += 1
    return out


def diff_stats(diff: str) -> dict:
    """Size statistics used for the scaling analysis (O3)."""
    files = split_files(diff)
    add = rem = hunks = 0
    for f in files:
        in_hunk = False
        for line in f.splitlines():
            if _HUNK.match(line):
                hunks += 1
                in_hunk = True
                continue
            if not in_hunk:
                continue
            if line.startswith("+"):
                add += 1
            elif line.startswith("-"):
                rem += 1
    return {"files": len(files), "hunks": hunks, "added": add, "removed": rem,
            "changed_lines": add + rem}
