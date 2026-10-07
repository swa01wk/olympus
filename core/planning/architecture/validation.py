from __future__ import annotations

from core.planning.schemas import ArchitectureProposal


def validate_architecture_proposal(proposal: ArchitectureProposal) -> list[str]:
    errors: list[str] = []
    body = proposal.body
    comp_names = [c.name for c in body.components]
    if len(comp_names) != len(set(comp_names)):
        errors.append("duplicate component names")
    directories = [c.directory for c in body.components]
    if len(directories) != len(set(directories)):
        errors.append("duplicate component directories")
    layer_set = set(body.layers)
    for rule in body.dependency_rules:
        parts = [p.strip() for p in rule.split("->")]
        if len(parts) != 2:
            errors.append(f"invalid dependency rule: {rule}")
            continue
        if parts[0] not in layer_set or parts[1] not in layer_set:
            errors.append(f"dependency rule references unknown layer: {rule}")
    stack = body.technology_stack.model_dump()
    required_stack = ("language", "web", "orm", "tests")
    missing = [k for k in required_stack if not str(stack.get(k, "")).strip()]
    if missing:
        errors.append(f"technology_stack missing keys: {sorted(missing)}")
    for q in proposal.open_questions:
        if q.blocking:
            errors.append(f"blocking open question: {q.question}")
    return errors
