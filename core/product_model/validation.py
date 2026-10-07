from __future__ import annotations

from core.domain.enums import EvidenceRequirement
from core.product_model.schemas import AcceptanceCriterionDraft, ProductDecomposition


def sanitize_proposal_requirement_refs(proposal: ProductDecomposition) -> ProductDecomposition:
    """Repair AC requirement_refs that point at requirements outside the AC's feature_spec."""
    reqs_by_spec: dict[str, list[str]] = {}
    for req in proposal.requirements:
        reqs_by_spec.setdefault(req.feature_spec_ref, []).append(req.ref)

    new_acs: list[AcceptanceCriterionDraft] = []
    changed = False
    for ac in proposal.acceptance_criteria:
        allowed = reqs_by_spec.get(ac.feature_spec_ref, [])
        allowed_set = set(allowed)
        filtered = [ref for ref in ac.requirement_refs if ref in allowed_set]
        if not filtered and allowed:
            filtered = [allowed[0]]
        if filtered != ac.requirement_refs:
            changed = True
            new_acs.append(ac.model_copy(update={"requirement_refs": filtered}))
        else:
            new_acs.append(ac)

    if not changed:
        return proposal
    return proposal.model_copy(update={"acceptance_criteria": new_acs})


def validate_proposal(proposal: ProductDecomposition) -> list[str]:
    errors: list[str] = []

    cap_refs = [c.ref for c in proposal.capabilities]
    feat_refs = [f.ref for f in proposal.features]
    spec_refs = [s.ref for s in proposal.feature_specs]
    req_refs = [r.ref for r in proposal.requirements]
    ac_refs = [a.ref for a in proposal.acceptance_criteria]

    for label, refs in (
        ("capability", cap_refs),
        ("feature", feat_refs),
        ("feature_spec", spec_refs),
        ("requirement", req_refs),
        ("acceptance_criterion", ac_refs),
    ):
        if len(refs) != len(set(refs)):
            errors.append(f"duplicate {label} refs")

    cap_set = set(cap_refs)
    feat_set = set(feat_refs)
    spec_set = set(spec_refs)

    for feat in proposal.features:
        if feat.capability_ref not in cap_set:
            errors.append(f"feature {feat.ref} references unknown capability {feat.capability_ref}")
        if not all(s.strip() for s in feat.source_sections):
            errors.append(f"feature {feat.ref} has empty source_sections entry")

    for cap in proposal.capabilities:
        if not all(s.strip() for s in cap.source_sections):
            errors.append(f"capability {cap.ref} has empty source_sections entry")

    specs_by_feature: dict[str, list[str]] = {}
    for spec in proposal.feature_specs:
        if spec.feature_ref not in feat_set:
            errors.append(f"feature_spec {spec.ref} references unknown feature {spec.feature_ref}")
        specs_by_feature.setdefault(spec.feature_ref, []).append(spec.ref)

    for feat_ref in feat_set:
        spec_list = specs_by_feature.get(feat_ref, [])
        if len(spec_list) != 1:
            errors.append(
                f"feature {feat_ref} must have exactly one feature_spec, got {len(spec_list)}"
            )

    reqs_by_spec: dict[str, list[str]] = {}
    for req in proposal.requirements:
        if req.feature_spec_ref not in spec_set:
            errors.append(f"requirement {req.ref} references unknown spec {req.feature_spec_ref}")
        reqs_by_spec.setdefault(req.feature_spec_ref, []).append(req.ref)

    acs_by_spec: dict[str, list[AcceptanceCriterionDraft]] = {}
    for ac in proposal.acceptance_criteria:
        if ac.feature_spec_ref not in spec_set:
            errors.append(f"AC {ac.ref} references unknown spec {ac.feature_spec_ref}")
        acs_by_spec.setdefault(ac.feature_spec_ref, []).append(ac)

    for spec_ref in spec_set:
        reqs = reqs_by_spec.get(spec_ref, [])
        if not reqs:
            errors.append(f"feature_spec {spec_ref} must have at least one requirement")
        acs = acs_by_spec.get(spec_ref, [])
        mandatory = [a for a in acs if a.mandatory]
        if not mandatory:
            errors.append(f"feature_spec {spec_ref} must have at least one mandatory AC")
        req_set = set(reqs)
        for ac in acs:
            if not ac.requirement_refs:
                errors.append(f"AC {ac.ref} must reference at least one requirement")
                continue
            for rr in ac.requirement_refs:
                if rr not in req_set:
                    errors.append(f"AC {ac.ref} references requirement {rr} not in same spec")
            if ac.mandatory and ac.evidence_requirement == EvidenceRequirement.REVIEW_ALLOWED:
                req_kinds = {
                    r.kind
                    for r in proposal.requirements
                    if r.ref in ac.requirement_refs and r.feature_spec_ref == spec_ref
                }
                if req_kinds and not all(k == "NON_FUNCTIONAL" for k in req_kinds):
                    errors.append(f"AC {ac.ref} REVIEW_ALLOWED mandatory AC must be non-functional")

    return errors
