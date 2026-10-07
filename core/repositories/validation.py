from __future__ import annotations

import re

from core.domain.enums import RepositoryProvider
from core.domain.exceptions import DomainError

CREDENTIAL_REF_PATTERN = re.compile(r"^(none|env|file|secret):[A-Za-z0-9_./-]*$")
SECRET_SHAPES = (
    re.compile(r"^ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"^glpat-"),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
    re.compile(r"^[A-Za-z0-9+/=]{40,}$"),
)
USERINFO_IN_URL = re.compile(r"^[a-z+]+://[^/@]*@")


def validate_credential_ref(credential_ref: str) -> None:
    if not CREDENTIAL_REF_PATTERN.match(credential_ref):
        raise DomainError(
            code="INVALID_CREDENTIAL_REF",
            message="credential_ref must match scheme:name grammar",
        )
    _, name = credential_ref.split(":", 1)
    for pattern in SECRET_SHAPES:
        if pattern.search(name):
            raise DomainError(
                code="CREDENTIAL_VALUE_REJECTED",
                message="credential_ref name looks like a secret value",
            )


def validate_remote_url(remote_url: str | None) -> None:
    if remote_url is None:
        return
    if USERINFO_IN_URL.match(remote_url):
        raise DomainError(
            code="CREDENTIAL_VALUE_REJECTED",
            message="remote_url must not contain userinfo",
        )


def validate_provider_supported(provider: RepositoryProvider) -> None:
    if provider in {RepositoryProvider.GITLAB, RepositoryProvider.BITBUCKET}:
        raise DomainError(
            code="PROVIDER_NOT_SUPPORTED",
            message=f"Provider {provider} is not supported in this phase",
        )
