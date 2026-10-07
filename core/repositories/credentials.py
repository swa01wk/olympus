"""Credential resolution for repository connectors (none: and env: in phase 04)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import SecretStr

CredentialStatus = Literal["NOT_REQUIRED", "CONFIGURED", "MISSING", "INVALID"]


@dataclass(frozen=True)
class ResolvedCredential:
    ref: str
    secret: SecretStr


class CredentialResolver(Protocol):
    def status(self, credential_ref: str) -> CredentialStatus: ...

    def resolve(self, credential_ref: str) -> ResolvedCredential | None: ...


class CompositeCredentialResolver:
    def __init__(self) -> None:
        self._prefix_handlers: dict[str, CredentialResolver] = {}

    def register(self, prefix: str, resolver: CredentialResolver) -> None:
        self._prefix_handlers[prefix] = resolver

    def status(self, credential_ref: str) -> CredentialStatus:
        resolver = self._resolver_for(credential_ref)
        if resolver is None:
            return "INVALID"
        return resolver.status(credential_ref)

    def resolve(self, credential_ref: str) -> ResolvedCredential | None:
        resolver = self._resolver_for(credential_ref)
        if resolver is None:
            return None
        return resolver.resolve(credential_ref)

    def _resolver_for(self, credential_ref: str) -> CredentialResolver | None:
        if ":" not in credential_ref:
            return None
        prefix = credential_ref.split(":", 1)[0] + ":"
        return self._prefix_handlers.get(prefix)


class NoneCredentialResolver:
    def status(self, credential_ref: str) -> CredentialStatus:
        if credential_ref == "none:":
            return "NOT_REQUIRED"
        return "INVALID"

    def resolve(self, credential_ref: str) -> ResolvedCredential | None:
        if credential_ref == "none:":
            return None
        return None


class EnvCredentialResolver:
    _pattern = re.compile(r"^env:([A-Za-z_][A-Za-z0-9_]*)$")

    def status(self, credential_ref: str) -> CredentialStatus:
        match = self._pattern.match(credential_ref)
        if not match:
            return "INVALID"
        var = match.group(1)
        if os.environ.get(var):
            return "CONFIGURED"
        return "MISSING"

    def resolve(self, credential_ref: str) -> ResolvedCredential | None:
        match = self._pattern.match(credential_ref)
        if not match:
            return None
        var = match.group(1)
        value = os.environ.get(var)
        if not value:
            return None
        return ResolvedCredential(ref=credential_ref, secret=SecretStr(value))


def build_default_credential_resolver() -> CompositeCredentialResolver:
    composite = CompositeCredentialResolver()
    composite.register("none:", NoneCredentialResolver())
    composite.register("env:", EnvCredentialResolver())
    from core.integrations.connectors.secrets import FileCredentialResolver

    composite.register("file:", FileCredentialResolver())
    return composite
