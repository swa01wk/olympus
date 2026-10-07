"""SecretProvider — env:, file:, and encrypted secret: credential backends."""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.domain.integrations.models import StoredSecret
from core.repositories.credentials import CredentialResolver, CredentialStatus, ResolvedCredential

_FILE_PATTERN = re.compile(r"^file:([A-Za-z0-9_./-]+)$")
_SECRET_PATTERN = re.compile(r"^secret:([A-Za-z0-9_./-]+)$")


def _fernet() -> Fernet | None:
    raw = get_settings().olympus_secret_key.get_secret_value()
    if not raw:
        return None
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


class FileCredentialResolver:
    def status(self, credential_ref: str) -> CredentialStatus:
        match = _FILE_PATTERN.match(credential_ref)
        if not match:
            return "INVALID"
        path = Path(match.group(1)).expanduser()
        if path.is_file() and path.stat().st_size > 0:
            return "CONFIGURED"
        return "MISSING"

    def resolve(self, credential_ref: str) -> ResolvedCredential | None:
        match = _FILE_PATTERN.match(credential_ref)
        if not match:
            return None
        path = Path(match.group(1)).expanduser()
        if not path.is_file():
            return None
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            return None
        return ResolvedCredential(ref=credential_ref, secret=SecretStr(value))


class SecretStoreCredentialResolver:
    """Resolves secret:name refs from the encrypted secrets table (sync session required)."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._cache: dict[str, str] = {}

    def bind_session(self, session: AsyncSession) -> None:
        self._session = session

    def status(self, credential_ref: str) -> CredentialStatus:
        match = _SECRET_PATTERN.match(credential_ref)
        if not match:
            return "INVALID"
        if _fernet() is None:
            return "MISSING"
        if self._session is None:
            return "MISSING"
        return "CONFIGURED"

    async def resolve_async(self, credential_ref: str) -> ResolvedCredential | None:
        match = _SECRET_PATTERN.match(credential_ref)
        if not match or self._session is None:
            return None
        name = match.group(1)
        if name in self._cache:
            return ResolvedCredential(ref=credential_ref, secret=SecretStr(self._cache[name]))
        f = _fernet()
        if f is None:
            return None
        row = await self._session.execute(select(StoredSecret).where(StoredSecret.name == name))
        stored = row.scalar_one_or_none()
        if stored is None:
            return None
        try:
            plain = f.decrypt(stored.ciphertext).decode("utf-8")
        except InvalidToken:
            return None
        self._cache[name] = plain
        return ResolvedCredential(ref=credential_ref, secret=SecretStr(plain))

    def resolve(self, credential_ref: str) -> ResolvedCredential | None:
        return None


async def store_secret(session: AsyncSession, name: str, value: str) -> str:
    f = _fernet()
    if f is None:
        raise ValueError("OLYMPUS_SECRET_KEY is required for secret: backend")
    ciphertext = f.encrypt(value.encode("utf-8"))
    existing = await session.execute(select(StoredSecret).where(StoredSecret.name == name))
    row = existing.scalar_one_or_none()
    if row is None:
        session.add(StoredSecret(name=name, ciphertext=ciphertext))
    else:
        row.ciphertext = ciphertext
        row.rotated_at = None
    await session.flush()
    return f"secret:{name}"


class AsyncAwareCredentialResolver:
    """Wraps sync resolvers and adds async secret: resolution."""

    def __init__(
        self,
        inner: CredentialResolver,
        secret_store: SecretStoreCredentialResolver,
    ) -> None:
        self._inner = inner
        self._secret_store = secret_store

    def status(self, credential_ref: str) -> CredentialStatus:
        if credential_ref.startswith("secret:"):
            return self._secret_store.status(credential_ref)
        return self._inner.status(credential_ref)

    def resolve(self, credential_ref: str) -> ResolvedCredential | None:
        if credential_ref.startswith("secret:"):
            return self._secret_store.resolve(credential_ref)
        return self._inner.resolve(credential_ref)

    async def resolve_async(self, credential_ref: str) -> ResolvedCredential | None:
        if credential_ref.startswith("secret:"):
            return await self._secret_store.resolve_async(credential_ref)
        return self._inner.resolve(credential_ref)


def build_credential_resolver(session: AsyncSession | None = None) -> AsyncAwareCredentialResolver:
    from core.repositories.credentials import (
        CompositeCredentialResolver,
        EnvCredentialResolver,
        NoneCredentialResolver,
    )

    composite = CompositeCredentialResolver()
    composite.register("none:", NoneCredentialResolver())
    composite.register("env:", EnvCredentialResolver())
    composite.register("file:", FileCredentialResolver())
    secret_store = SecretStoreCredentialResolver(session)
    return AsyncAwareCredentialResolver(composite, secret_store)
