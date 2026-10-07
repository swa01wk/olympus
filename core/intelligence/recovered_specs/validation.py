from __future__ import annotations

import ast
import re
from typing import Any, Literal

from agents.scout.schemas import Citation, RecoveredFeatureSpec, RepositorySurvey

ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW"]

_HIGH_KINDS = frozenset({"TEST_ASSERTED", "TEST_EXECUTION"})
_MEDIUM_KINDS = frozenset(
    {"ROUTE_BEHAVIOR", "DATA_INVARIANT", "VALIDATION_RULE", "STATE_TRANSITION"}
)


def cap_confidence(
    claim: ConfidenceLevel,
    cited_behavior_kinds: set[str],
) -> ConfidenceLevel:
    if cited_behavior_kinds & _HIGH_KINDS:
        cap: ConfidenceLevel = "HIGH"
    elif cited_behavior_kinds & _MEDIUM_KINDS:
        cap = "MEDIUM"
    else:
        cap = "LOW"
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return claim if order[claim] <= order[cap] else cap


def min_confidence(a: ConfidenceLevel, b: ConfidenceLevel) -> ConfidenceLevel:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return a if order[a] <= order[b] else b


def _entity_resolves(ref: str, entity_keys: set[str]) -> bool:
    if ref in entity_keys:
        return True
    normalized = ref.replace("\\", "/")
    for key in entity_keys:
        kn = key.replace("\\", "/")
        if kn == normalized or kn.endswith(normalized) or normalized.endswith(kn):
            return True
        if normalized in kn or kn in normalized:
            return True
    parts = normalized.split(":", 2)
    if len(parts) == 3:
        _typ, path, qn = parts
        tail = f"{path}:{qn}"
        for key in entity_keys:
            kn = key.replace("\\", "/")
            if kn.endswith(tail) or kn.endswith(f":{qn}"):
                return True
            key_parts = kn.split(":", 2)
            if len(key_parts) == 3 and key_parts[2] == qn:
                return True
    return False


def discovery_fact_aliases(fact_statements: set[str]) -> set[str]:
    """Stable FACT citation refs Scout may use for deterministic discovery summaries."""
    aliases: set[str] = set()
    for stmt in fact_statements:
        for key in ("entry_points", "config_files", "dependencies"):
            m = re.match(rf"Repository summary: {key} = (\[.*\])", stmt)
            if not m:
                continue
            try:
                items = ast.literal_eval(m.group(1))
            except (ValueError, SyntaxError):
                continue
            if isinstance(items, list):
                if not items:
                    aliases.add(f"{key}: []")
                for item in items:
                    aliases.add(f"{key}: {item}")
                    if isinstance(item, str):
                        aliases.add(item)
                        base = item.replace("\\", "/").rsplit("/", 1)[-1]
                        if base != item:
                            aliases.add(base)
    return aliases


def _fact_resolves(ref: str, fact_ids: set[str], fact_statements: set[str]) -> bool:
    if ref in fact_ids:
        return True
    ref_l = ref.lower()
    if ref_l.endswith((".toml", ".yaml", ".yml", ".json", ".cfg", ".ini", ".txt")):
        for stmt in fact_statements:
            if ref_l in stmt.lower():
                return True
    for stmt in fact_statements:
        sl = stmt.lower()
        if ref_l == sl or ref_l in sl or sl in ref_l:
            return True
    m = re.match(r"entry_points\s*:\s*(.+)", ref, re.I)
    if m:
        tail = m.group(1).strip().lower()
        for stmt in fact_statements:
            if tail and tail in stmt.lower():
                return True
    m = re.match(r"config_files\s*:\s*(.+)", ref, re.I)
    if m:
        tail = m.group(1).strip().lower()
        for stmt in fact_statements:
            sl = stmt.lower()
            if tail == "[]" and "config_files = []" in sl:
                return True
            if tail and tail in sl:
                return True
    m = re.match(r"dependencies\s*:\s*(.+)", ref, re.I)
    if m:
        tail = m.group(1).strip().lower()
        for stmt in fact_statements:
            if tail and tail in stmt.lower():
                return True
    if "dependenc" in ref_l:
        tokens = {
            t
            for t in re.split(r"[^\w]+", ref_l)
            if len(t) >= 4 and t not in {"dependencies", "include", "null", "versions", "with"}
        }
        for stmt in fact_statements:
            sl = stmt.lower()
            if "dependencies" not in sl and "framework detected" not in sl:
                continue
            if any(token in sl for token in tokens):
                return True
    if "framework" in ref_l:
        tokens = {t for t in re.split(r"[^\w]+", ref_l) if len(t) >= 4}
        for stmt in fact_statements:
            sl = stmt.lower()
            if (
                "framework detected:" in sl
                and tokens & set(re.split(r"[^\w]+", sl))
                and any(t in sl for t in tokens)
            ):
                return True
    return False


class RecoveryValidator:
    def validate_survey(
        self,
        survey: RepositorySurvey,
        *,
        behavior_ids: set[str],
        fact_ids: set[str],
        fact_statements: set[str],
        entity_keys: set[str],
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for inf in survey.inferences:
            errors.extend(
                self._check_citations(
                    inf.citations, behavior_ids, fact_ids, fact_statements, entity_keys
                )
            )
        for unc in survey.uncertainties:
            for cit in unc.citations:
                errors.extend(
                    self._check_citations(
                        [cit], behavior_ids, fact_ids, fact_statements, entity_keys
                    )
                )
        return (not errors, errors)

    def validate_feature_spec(
        self,
        spec: RecoveredFeatureSpec,
        *,
        behavior_ids: set[str],
        fact_ids: set[str],
        fact_statements: set[str],
        entity_keys: set[str],
        behavior_kinds: dict[str, str],
    ) -> tuple[bool, list[str], dict[str, Any]]:
        errors: list[str] = []
        for inf in spec.inferences:
            errors.extend(
                self._check_citations(
                    inf.citations, behavior_ids, fact_ids, fact_statements, entity_keys
                )
            )
        for ac in spec.acceptance_criteria:
            errors.extend(
                self._check_citations(
                    ac.citations, behavior_ids, fact_ids, fact_statements, entity_keys
                )
            )
            kinds = {
                behavior_kinds.get(c.ref, "")
                for c in ac.citations
                if c.ref_type == "OBSERVED_BEHAVIOR"
            }
            _ = cap_confidence(ac.confidence, {k for k in kinds if k})
        for link in spec.principal_entity_links:
            sk = str(link.get("stable_key", ""))
            if not sk:
                continue
            if sk in behavior_ids:
                continue
            if not _entity_resolves(sk, entity_keys):
                errors.append(f"UNKNOWN_ENTITY:{sk}")
        cited_kinds = {
            behavior_kinds.get(c.ref, "")
            for ac in spec.acceptance_criteria
            for c in ac.citations
            if c.ref_type == "OBSERVED_BEHAVIOR"
        }
        persisted = cap_confidence(spec.confidence, {k for k in cited_kinds if k})
        report = {"claimed_confidence": spec.confidence, "persisted_confidence": persisted}
        return (not errors, errors, report)

    def _check_citations(
        self,
        citations: list[Citation],
        behavior_ids: set[str],
        fact_ids: set[str],
        fact_statements: set[str],
        entity_keys: set[str],
    ) -> list[str]:
        errors: list[str] = []
        if not citations:
            errors.append("CITATION_REQUIRED")
            return errors
        for cit in citations:
            if cit.ref_type == "OBSERVED_BEHAVIOR" and cit.ref not in behavior_ids:
                errors.append(f"UNKNOWN_BEHAVIOR:{cit.ref}")
            elif cit.ref_type == "FACT" and not _fact_resolves(cit.ref, fact_ids, fact_statements):
                errors.append(f"UNKNOWN_FACT:{cit.ref}")
            elif cit.ref_type == "CODE_ENTITY" and not _entity_resolves(cit.ref, entity_keys):
                errors.append(f"UNKNOWN_ENTITY:{cit.ref}")
        return errors
