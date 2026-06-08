from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    test_root = repo_root / "server" / "test"
    test_files = sorted(test_root.rglob("test_*.py"))

    if not test_files:
        print("[backend] No pytest files found under server/test. Skipping backend test step.")
        return 0

    try:
        import pytest
    except ImportError:
        print("[backend] pytest is not installed in the selected interpreter.", file=sys.stderr)
        return 1

    return int(pytest.main(["-vv", "-s", str(test_root)]))


if __name__ == "__main__":
    raise SystemExit(main())
