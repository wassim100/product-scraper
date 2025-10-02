#!/usr/bin/env python3
"""Pre-commit guard: blocks accidental commit of large regenerated JSON artifacts.

Usage:
  Called automatically via .githooks/pre-commit (configure: git config core.hooksPath .githooks)

Logic:
  - Collect staged files (git diff --cached --name-only)
  - If any matches forbidden patterns, abort with guidance.
  - Exit 0 otherwise.
"""
from __future__ import annotations
import subprocess
import sys
import re

FORBIDDEN_PATTERNS = [
    r".*_full\.json$",
    r".*_full\.cleaned\.json$",
    r".*printers_scanners.*\.json$",
    r".*_scanners_full.*\.json$",
    r".*\.smoketest.*\.json$",
    r"hp_printers_scanners_schema.*\.json$",
]

def _get_staged() -> list[str]:
    try:
        out = subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True)
        return [l.strip() for l in out.splitlines() if l.strip()]
    except subprocess.CalledProcessError:
        return []

def main() -> int:
    staged = _get_staged()
    if not staged:
        return 0
    bad = []
    for path in staged:
        for pat in FORBIDDEN_PATTERNS:
            if re.fullmatch(pat, path):
                bad.append(path)
                break
    if bad:
        print("❌ Commit bloqué: fichiers générés détectés (non versionner les artefacts de scraping):", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        print("\nSolution:")
        print("  1) git restore --staged <fichier>")
        print("  2) Si vous TENEZ à versionner un échantillon, placez-le dans samples/ et renommez-le (ex: sample_server.json)")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
