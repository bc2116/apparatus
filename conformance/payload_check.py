"""Check that the universal starter payload exactly matches its golden manifest.

Stdlib only, so it runs on any machine with `python3` and no environment:

    python3 conformance/payload_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_DIR = REPO_ROOT / "starter" / "payload"
MANIFEST = REPO_ROOT / "conformance" / "golden" / "payload-manifest.txt"

# OS metadata noise that must never count as payload content.
IGNORED_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def expected_paths() -> set[str]:
    paths = set()
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            paths.add(line)
    return paths


def actual_paths() -> set[str]:
    return {
        p.relative_to(PAYLOAD_DIR).as_posix()
        for p in PAYLOAD_DIR.rglob("*")
        if p.is_file() and p.name not in IGNORED_NAMES
    }


def diff() -> tuple[set[str], set[str]]:
    """Return (missing, unexpected) relative to the golden manifest."""
    expected = expected_paths()
    actual = actual_paths()
    return expected - actual, actual - expected


def main() -> int:
    missing, unexpected = diff()
    if not missing and not unexpected:
        print(f"payload OK: {len(expected_paths())} files match the golden manifest")
        return 0
    for path in sorted(missing):
        print(f"MISSING from payload: {path}")
    for path in sorted(unexpected):
        print(f"UNEXPECTED in payload: {path}")
    print("Payload and golden manifest disagree. If the change is intentional,")
    print("update docs/spec/workspace.md and conformance/golden/payload-manifest.txt")
    print("in the same PR.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
