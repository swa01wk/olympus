from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.config.settings import OlympusSettings, get_settings
from core.runtime.errors import ConfigError

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


@dataclass(frozen=True)
class ResolvedModel:
    alias: str
    provider: str
    model: str
    max_output_tokens: int
    temperature: float
    max_schema_retries: int
    max_transport_retries: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _expand_env(value: str, settings: OlympusSettings) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key == "MODEL_PROVIDER":
            return settings.model_provider
        if key == "MODEL_DEFAULT":
            return settings.model_default
        env_val = os.environ.get(key, "")
        if env_val:
            return env_val
        attr = key.lower()
        if hasattr(settings, attr):
            raw = getattr(settings, attr)
            if isinstance(raw, str):
                return raw
        return ""

    return _ENV_PATTERN.sub(repl, value)


def _env_model(settings: OlympusSettings, env_key: str) -> str:
    raw = os.environ.get(env_key, "")
    if raw:
        return raw
    mapping = {
        "MODEL_PRODUCT_REASONING": settings.model_product_reasoning,
        "MODEL_PLANNING": settings.model_planning,
        "MODEL_ARCHITECTURE_REASONING": settings.model_architecture_reasoning,
        "MODEL_REPOSITORY_REASONING": settings.model_repository_reasoning,
        "MODEL_CODE_IMPLEMENTATION": settings.model_code_implementation,
        "MODEL_CODE_REVIEW": settings.model_code_review,
        "MODEL_VERIFICATION": settings.model_verification,
        "MODEL_ORCHESTRATION": settings.model_orchestration,
        "MODEL_EMBEDDING": settings.model_embedding,
        "MODEL_DEFAULT": settings.model_default,
    }
    return mapping.get(env_key, "")


@lru_cache
def load_models_config() -> dict[str, Any]:
    path = _repo_root() / "config" / "models.yaml"
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigError("config/models.yaml must be a mapping")
    return data


def clear_models_config_cache() -> None:
    load_models_config.cache_clear()


class ModelPolicy:
    def __init__(self, settings: OlympusSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._config = load_models_config()

    def resolve(self, alias: str) -> ResolvedModel:
        aliases = self._config.get("aliases")
        if not isinstance(aliases, dict) or alias not in aliases:
            raise ConfigError(f"Unknown model alias: {alias}")

        entry = aliases[alias]
        if not isinstance(entry, dict):
            raise ConfigError(f"Invalid alias config for {alias}")

        defaults = self._config.get("defaults", {})
        if not isinstance(defaults, dict):
            defaults = {}

        provider_raw = str(
            entry.get("provider", defaults.get("provider", self._settings.model_provider))
        )
        provider = _expand_env(provider_raw, self._settings) or self._settings.model_provider

        model_env = str(entry.get("model_env", "MODEL_DEFAULT"))
        model = _env_model(self._settings, model_env) or self._settings.model_default
        if not model:
            raise ConfigError(f"No model configured for alias {alias} ({model_env})")

        max_output_tokens = int(
            entry.get("max_output_tokens", defaults.get("max_output_tokens", 4096))
        )
        temperature = float(entry.get("temperature", defaults.get("temperature", 0.0)))
        max_schema_retries = int(
            entry.get("max_schema_retries", defaults.get("max_schema_retries", 2))
        )
        max_transport_retries = int(
            entry.get("max_transport_retries", defaults.get("max_transport_retries", 3))
        )

        return ResolvedModel(
            alias=alias,
            provider=provider,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            max_schema_retries=max_schema_retries,
            max_transport_retries=max_transport_retries,
        )

    @property
    def retention(self) -> dict[str, str]:
        retention = self._config.get("retention", {})
        if not isinstance(retention, dict):
            return {"store_prompts": "hash_only", "store_responses": "structured_only"}
        return {
            "store_prompts": str(retention.get("store_prompts", "hash_only")),
            "store_responses": str(retention.get("store_responses", "structured_only")),
        }
