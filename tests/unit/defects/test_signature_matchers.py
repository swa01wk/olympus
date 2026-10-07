from core.assurance.reproduction.signature import (
    classify_junit_failure,
    extract_http_status_from_failure,
    match_signature,
)


def test_http_status_signature_match() -> None:
    assert match_signature({"kind": "http_status", "value": 500}, http_status=500)
    assert not match_signature({"kind": "http_status", "value": 409}, http_status=500)


def test_assertion_vs_collection() -> None:
    assert classify_junit_failure([])[0] == "COLLECTION"
    failed = [{"passed": False, "failure_text": "assert 500"}]
    assert classify_junit_failure(failed)[0] == "ASSERTION"
    assert classify_junit_failure([{"passed": True}])[0] == "PASS"


def test_extract_http_status() -> None:
    assert extract_http_status_from_failure("Expected 500 but got 200") == 500
    assert extract_http_status_from_failure("AssertionError: 500") == 500
