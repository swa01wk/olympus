from __future__ import annotations

import pytest
from core.domain.enums import RepositoryProvider
from core.domain.exceptions import DomainError
from core.repositories.validation import (
    validate_credential_ref,
    validate_provider_supported,
    validate_remote_url,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "ref",
    ["none:", "env:MY_TOKEN", "file:./creds", "secret:github_pat"],
)
def test_credential_ref_schemes_accepted(ref: str) -> None:
    validate_credential_ref(ref)


@pytest.mark.parametrize(
    "ref",
    [
        "secret:ghp_abcdefghijklmnopqrstuvwxyz1234567890",
        "secret:abcdefghijklmnopqrstuvwxyz0123456789ABCD",
    ],
)
def test_credential_ref_secret_shape_rejected(ref: str) -> None:
    with pytest.raises(DomainError) as exc:
        validate_credential_ref(ref)
    assert exc.value.code == "CREDENTIAL_VALUE_REJECTED"


def test_remote_url_userinfo_rejected() -> None:
    with pytest.raises(DomainError) as exc:
        validate_remote_url("https://user:pw@github.com/x.git")
    assert exc.value.code == "CREDENTIAL_VALUE_REJECTED"


def test_provider_not_supported() -> None:
    with pytest.raises(DomainError) as exc:
        validate_provider_supported(RepositoryProvider.GITLAB)
    assert exc.value.code == "PROVIDER_NOT_SUPPORTED"
