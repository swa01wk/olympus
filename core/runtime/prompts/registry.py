from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from jinja2 import StrictUndefined, TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    version: str
    path: Path
    body: str
    content_hash: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER.match(raw)
    if not match:
        raise ValueError("Prompt template missing YAML front matter")
    meta = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict):
        raise ValueError("Prompt front matter must be a mapping")
    body = raw[match.end() :]
    return {str(k): str(v) for k, v in meta.items()}, body


def load_prompt(relative_path: str) -> PromptTemplate:
    path = _repo_root() / relative_path
    raw = path.read_text(encoding="utf-8")
    meta, body = _parse_front_matter(raw)
    template_id = meta.get("id", "")
    version = meta.get("version", "")
    if not template_id or not version:
        raise ValueError(f"Prompt {path} requires id and version in front matter")
    content_hash = _sha256(raw)
    return PromptTemplate(
        template_id=template_id,
        version=version,
        path=path,
        body=body,
        content_hash=content_hash,
    )


def render_prompt(template: PromptTemplate, variables: dict[str, object]) -> str:
    env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
    try:
        compiled = env.from_string(template.body)
        return compiled.render(**variables)
    except TemplateSyntaxError as exc:
        raise ValueError(str(exc)) from exc
