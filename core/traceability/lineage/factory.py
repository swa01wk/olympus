"""Configured LineageService for API and tests."""

from __future__ import annotations

from core.traceability.lineage.hops import (
    hop_ac_to_evidence,
    hop_evidence_to_ic,
    hop_feature_to_specs,
    hop_finding_to_remediation_task,
    hop_reverse_product_context,
    hop_specs_to_impl_and_code,
)
from core.traceability.lineage.hops_release import hop_ic_to_release
from core.traceability.lineage.service import LineageService


def build_lineage_service() -> LineageService:
    svc = LineageService()
    svc.register_hop(hop_feature_to_specs)
    svc.register_hop(hop_specs_to_impl_and_code)
    svc.register_hop(hop_reverse_product_context)
    svc.register_hop(hop_ac_to_evidence)
    svc.register_hop(hop_evidence_to_ic)
    svc.register_hop(hop_finding_to_remediation_task)
    svc.register_hop(hop_ic_to_release)
    return svc
