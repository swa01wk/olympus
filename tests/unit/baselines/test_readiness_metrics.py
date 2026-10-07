from __future__ import annotations

from core.intelligence.baselines.readiness import _classify_remediable, _metric_row


def test_metric_row_shape() -> None:
    row = _metric_row("baseline_coverage", 0.5, 1.0, False)
    assert row["name"] == "baseline_coverage"
    assert row["ok"] is False


def test_remediable_only_coverage_gaps() -> None:
    metrics = [
        _metric_row("baseline_coverage", 0.0, 1.0, False),
        _metric_row("review_completion", 1.0, 1.0, True),
    ]
    assert _classify_remediable(metrics, ["baseline_coverage"]) is True


def test_not_remediable_when_blocking_uncertainty() -> None:
    metrics = [_metric_row("blocking_uncertainties_open", 2.0, 0.0, False)]
    assert _classify_remediable(metrics, ["blocking_uncertainties_open"]) is False
