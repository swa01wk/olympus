"""Argv-only shell execution policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from core.config.settings import get_settings

_METACHAR = re.compile(r"[;&|`$<>]")


@dataclass(frozen=True)
class ShellPolicy:
    categories: dict[str, list[str]]
    timeout_s: int
    max_output_bytes: int
    disabled_categories: frozenset[str]


def load_shell_policy() -> ShellPolicy:
    root = Path(__file__).resolve().parents[2]
    path = root / "config" / "shell_policy.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    return ShellPolicy(
        categories={k: list(v.get("binaries", [])) for k, v in raw.get("categories", {}).items()},
        timeout_s=int(defaults.get("timeout_s", 300)),
        max_output_bytes=int(defaults.get("max_output_bytes", 500_000)),
        disabled_categories=frozenset(raw.get("disabled_categories", [])),
    )


def validate_shell_argv(category: str, argv: list[str], policy: ShellPolicy | None = None) -> None:
    pol = policy or load_shell_policy()
    if category in pol.disabled_categories:
        raise ValueError(f"shell category {category} disabled")
    if category not in pol.categories:
        raise ValueError(f"unknown shell category {category}")
    if not argv:
        raise ValueError("empty argv")
    for part in argv:
        if _METACHAR.search(part):
            raise ValueError("shell metacharacters in argv")
    binary = Path(argv[0]).name
    allowed = pol.categories[category]
    if binary not in allowed:
        raise ValueError(f"binary {binary} not allowed for category {category}")


def scrubbed_env() -> dict[str, str]:
    import os

    secret_prefixes = ("OLYMPUS_", "ANTHROPIC_", "OPENAI_", "GITHUB_", "DATABASE_")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C.UTF-8",
    }
    for key, value in os.environ.items():
        if key.startswith(secret_prefixes):
            continue
        if "KEY" in key or "TOKEN" in key or "SECRET" in key or "PASSWORD" in key:
            continue
        env[key] = value
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    _ = get_settings()
    return env
