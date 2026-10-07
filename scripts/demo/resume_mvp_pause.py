#!/usr/bin/env python3
"""Mark var/olympus/demo/pause.json resumed so a paused MVP demo can continue."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.demo.chained.driver import ChainedDriver


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume a chained MVP driver pause")
    parser.add_argument(
        "--pause-file",
        type=Path,
        default=Path("var/olympus/demo/pause.json"),
    )
    args = parser.parse_args()
    if not args.pause_file.is_file():
        print(f"Pause file not found: {args.pause_file}", file=sys.stderr)
        return 1
    ChainedDriver.resume_pause(args.pause_file)
    print(f"Resumed {args.pause_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
