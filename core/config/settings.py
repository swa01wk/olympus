from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

OlympusEnv = Literal["local", "test", "integration", "journey", "production"]
WorkspaceBackend = Literal["LOCAL_FILESYSTEM"]
ModelProvider = Literal["anthropic", "openai"]
GitProvider = Literal["local", "github", "gitea"]


def _resolve_writable_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    probe = resolved / ".olympus_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise ValueError(f"Directory is not writable: {resolved}") from exc
    return resolved


class OlympusSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="postgresql+psycopg://olympus:olympus@localhost:5432/olympus",
        validation_alias="DATABASE_URL",
    )
    olympus_env: OlympusEnv = Field(default="local", validation_alias="OLYMPUS_ENV")
    olympus_storage_root: Path = Field(
        default=Path("./var/olympus"),
        validation_alias="OLYMPUS_STORAGE_ROOT",
    )
    olympus_workspace_backend: WorkspaceBackend = Field(
        default="LOCAL_FILESYSTEM",
        validation_alias="OLYMPUS_WORKSPACE_BACKEND",
    )
    olympus_workspace_root: Path = Field(
        ...,
        validation_alias="OLYMPUS_WORKSPACE_ROOT",
    )
    olympus_worktree_root: Path | None = Field(
        default=None,
        validation_alias="OLYMPUS_WORKTREE_ROOT",
    )
    olympus_secret_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="OLYMPUS_SECRET_KEY",
    )

    model_provider: ModelProvider = Field(default="anthropic", validation_alias="MODEL_PROVIDER")
    model_default: str = Field(default="", validation_alias="MODEL_DEFAULT")
    model_product_reasoning: str = Field(default="", validation_alias="MODEL_PRODUCT_REASONING")
    model_planning: str = Field(default="", validation_alias="MODEL_PLANNING")
    model_architecture_reasoning: str = Field(
        default="",
        validation_alias="MODEL_ARCHITECTURE_REASONING",
    )
    model_repository_reasoning: str = Field(
        default="",
        validation_alias="MODEL_REPOSITORY_REASONING",
    )
    model_code_implementation: str = Field(
        default="",
        validation_alias="MODEL_CODE_IMPLEMENTATION",
    )
    model_code_review: str = Field(default="", validation_alias="MODEL_CODE_REVIEW")
    model_verification: str = Field(default="", validation_alias="MODEL_VERIFICATION")
    model_orchestration: str = Field(default="", validation_alias="MODEL_ORCHESTRATION")
    model_embedding: str = Field(default="", validation_alias="MODEL_EMBEDDING")

    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="ANTHROPIC_API_KEY",
    )
    openai_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="OPENAI_API_KEY")

    llm_live_tests: int = Field(default=0, validation_alias="LLM_LIVE_TESTS")
    llm_test_budget_usd: Decimal = Field(
        default=Decimal("5.00"),
        validation_alias="LLM_TEST_BUDGET_USD",
    )

    runtime_checkpoint_schema: str = Field(
        default="langgraph_runtime",
        validation_alias="RUNTIME_CHECKPOINT_SCHEMA",
    )

    git_provider: GitProvider = Field(default="local", validation_alias="GIT_PROVIDER")
    github_token: SecretStr = Field(default=SecretStr(""), validation_alias="GITHUB_TOKEN")
    github_webhook_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="GITHUB_WEBHOOK_SECRET",
    )
    olympus_webhook_secrets_file: Path = Field(
        default=Path("./config/webhook_secrets.local.yaml"),
        validation_alias="OLYMPUS_WEBHOOK_SECRETS_FILE",
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="",
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    service_name: str = Field(default="olympus", validation_alias="OLYMPUS_SERVICE_NAME")
    worker_poll_interval_seconds: float = Field(
        default=5.0,
        validation_alias="OLYMPUS_WORKER_POLL_INTERVAL_SECONDS",
    )
    execution_lease_ttl_seconds: float = Field(
        default=120.0,
        validation_alias="OLYMPUS_EXECUTION_LEASE_TTL_SECONDS",
    )
    execution_heartbeat_interval_seconds: float = Field(
        default=30.0,
        validation_alias="OLYMPUS_EXECUTION_HEARTBEAT_INTERVAL_SECONDS",
    )
    scheduler_admit_batch_size: int = Field(
        default=10,
        validation_alias="OLYMPUS_SCHEDULER_ADMIT_BATCH_SIZE",
    )
    product_source_decompose_max_chars: int = Field(
        default=32_000,
        validation_alias="OLYMPUS_PRODUCT_SOURCE_DECOMPOSE_MAX_CHARS",
        ge=1,
    )

    @field_validator("olympus_worktree_root", mode="before")
    @classmethod
    def empty_worktree_root_is_none(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        return value

    @model_validator(mode="after")
    def validate_env_and_paths(self) -> Self:
        if self.olympus_env == "journey" and self.llm_live_tests != 1:
            raise ValueError(
                "OLYMPUS_ENV=journey requires LLM_LIVE_TESTS=1 (mocked output is not journey proof)"
            )

        self.olympus_storage_root = _resolve_writable_dir(self.olympus_storage_root)
        self.olympus_workspace_root = _resolve_writable_dir(self.olympus_workspace_root)

        if self.olympus_worktree_root is not None:
            self.olympus_worktree_root = _resolve_writable_dir(self.olympus_worktree_root)
        else:
            derived = self.olympus_workspace_root / "worktrees"
            self.olympus_worktree_root = _resolve_writable_dir(derived)

        return self

    @property
    def effective_worktree_root(self) -> Path:
        assert self.olympus_worktree_root is not None
        return self.olympus_worktree_root


@lru_cache
def get_settings() -> OlympusSettings:
    return OlympusSettings(
        olympus_workspace_root=Path(
            os.environ.get("OLYMPUS_WORKSPACE_ROOT", "./var/olympus/workspaces")
        ),
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()
