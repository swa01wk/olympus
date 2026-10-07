from __future__ import annotations

from core.planning.glob_scope import path_matches_pattern, pattern_allowed
from core.planning.models import ArchitectureContract
from core.planning.schemas import ArchitectureBody, ConformanceReport, ImplementationSpecBody


class ArchitectureConformanceValidator:
    def validate(
        self,
        draft: ImplementationSpecBody,
        arch: ArchitectureBody,
        contracts: list[ArchitectureContract],
    ) -> ConformanceReport:
        violations: list[str] = []
        comp_names = {c.name for c in arch.components}
        for name in draft.components:
            if name not in comp_names:
                violations.append(f"unknown component: {name}")

        contract_keys = {c.key for c in contracts}
        dir_patterns = [e.path for e in arch.directory_conventions] + [
            c.directory for c in arch.components
        ]
        for api in draft.apis:
            if api.contract_key and api.contract_key not in contract_keys:
                violations.append(f"unknown contract_key: {api.contract_key}")

        for glob in draft.file_scope:
            if not pattern_allowed(glob):
                violations.append(f"invalid file_scope pattern: {glob}")
                continue
            allowed = False
            for d in dir_patterns:
                candidates = [d, d.rstrip("/") + "/**", d + "/**"]
                if any(path_matches_pattern(glob, c) for c in candidates):
                    allowed = True
                    break
            if not allowed:
                violations.append(f"file_scope outside architecture conventions: {glob}")

        for ref in draft.architecture_refs:
            known = comp_names | contract_keys | {d.id for d in arch.decisions}
            if ref not in known:
                violations.append(f"unknown architecture_ref: {ref}")

        return ConformanceReport(ok=not violations, violations=violations)
