#!/usr/bin/env python3
"""Drive Greenfield journey steps via the control API (manual demo)."""

from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Olympus Greenfield demo driver")
    parser.add_argument(
        "--api-base", default=os.environ.get("OLYMPUS_API_BASE", "http://127.0.0.1:8000")
    )
    parser.add_argument("--human-token", default=os.environ.get("OLYMPUS_HUMAN_TOKEN"))
    args = parser.parse_args()
    if not args.human_token:
        print("Set OLYMPUS_HUMAN_TOKEN or pass --human-token", file=sys.stderr)
        return 1
    print(f"API base: {args.api_base}")
    print("Implement step-by-step API calls mirroring tests/journey/test_greenfield_supportdesk.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
