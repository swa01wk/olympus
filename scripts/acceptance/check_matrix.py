#!/usr/bin/env python3
"""Verify ARCH §22 / TECH §31 acceptance matrix against junit XML (Phase 19 §4.8)."""

from __future__ import annotations

import argparse
import glob
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


def _load_matrix(path: Path) -> list[dict[str, object]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("matrix must be a list of rows")
    return data


def _collect_junit_cases(junit_paths: list[str]) -> dict[str, str]:
    cases: dict[str, str] = {}
    for pattern in junit_paths:
        for path in glob.glob(pattern):
            tree = ET.parse(path)
            root = tree.getroot()
            for case in root.iter("testcase"):
                classname = case.attrib.get("classname", "")
                name = case.attrib.get("name", "")
                nodeid = f"{classname}::{name}" if classname else name
                if case.find("skipped") is not None:
                    cases[nodeid] = "skipped"
                elif case.find("failure") is not None or case.find("error") is not None:
                    cases[nodeid] = "failed"
                else:
                    cases[nodeid] = "passed"
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Check acceptance matrix vs junit")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--junit", nargs="+", required=True)
    args = parser.parse_args()

    rows = _load_matrix(args.matrix)
    junit = _collect_junit_cases(args.junit)
    errors: list[str] = []

    for row in rows:
        row_id = str(row.get("id", ""))
        tests = row.get("tests") or []
        if not tests:
            errors.append(f"{row_id}: no mapped tests")
            continue
        ok = False
        for node in tests:
            node_str = str(node)
            status = junit.get(node_str)
            if status == "passed":
                ok = True
                break
            if status is None:
                errors.append(f"{row_id}: missing junit node {node_str}")
            elif status == "skipped":
                errors.append(f"{row_id}: skipped counts as failed ({node_str})")
            else:
                errors.append(f"{row_id}: failed ({node_str})")
        if not ok and not any(str(n) in junit for n in tests):
            errors.append(f"{row_id}: no passing mapped test")

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    print(f"matrix ok ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
