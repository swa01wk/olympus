#!/usr/bin/env python3
"""One-shot GIT_ASKPASS helper (reads OLYMPUS_GIT_* env; never log output)."""

from __future__ import annotations

import os
import sys


def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    if "Username" in prompt:
        print(os.environ.get("OLYMPUS_GIT_USERNAME", "olympus"), end="")
        return
    print(os.environ.get("OLYMPUS_GIT_CREDENTIAL", ""), end="")


if __name__ == "__main__":
    main()
