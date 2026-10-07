import pytest
from core.tools.shell_policy import validate_shell_argv


@pytest.mark.unit
def test_disallowed_binary() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        validate_shell_argv("pytest", ["ls"])


@pytest.mark.unit
def test_metachar_in_argv() -> None:
    with pytest.raises(ValueError, match="metacharacter"):
        validate_shell_argv("pytest", ["pytest", "foo;rm"])
