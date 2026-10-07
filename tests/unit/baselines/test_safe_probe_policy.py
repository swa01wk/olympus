from __future__ import annotations

from core.intelligence.baselines.probes import SafeRuntimeProbeGenerator


def test_safe_probe_generator_reads_policy() -> None:
    gen = SafeRuntimeProbeGenerator()
    assert gen._probes_mode == "safe_only"
