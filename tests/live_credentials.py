"""Detect live LLM credentials from settings (.env), not only os.environ."""

from __future__ import annotations

from core.config.settings import get_settings


def anthropic_configured() -> bool:
    return bool(get_settings().anthropic_api_key.get_secret_value())


def openai_configured() -> bool:
    return bool(get_settings().openai_api_key.get_secret_value())


def any_live_provider_configured() -> bool:
    return anthropic_configured() or openai_configured()


def openai_embedding_configured() -> bool:
    """Embedding alias uses OpenAI per config/models.yaml (not chat MODEL_PROVIDER)."""
    return openai_configured()


def configured_embedding_model() -> str:
    settings = get_settings()
    return settings.model_embedding or "text-embedding-3-small"
