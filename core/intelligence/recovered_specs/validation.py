from __future__ import annotations

import ast
import re
from typing import Any, Literal

from agents.scout.schemas import (
    Citation,
    InferenceDraft,
    PrincipalEntityLink,
    RecoveredAcDraft,
    RecoveredFeatureSpec,
    RepositorySurvey,
    UncertaintyDraft,
)

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
        typ, path, qn = parts
        tail = f"{path}:{qn}"
        for key in entity_keys:
            kn = key.replace("\\", "/")
            if kn.endswith(tail) or kn.endswith(f":{qn}"):
                return True
            key_parts = kn.split(":", 2)
            if len(key_parts) == 3 and key_parts[2] == qn:
                return True
            # FILE/MODULE refs name a file; the qualified-name part is often garbled.
            if typ in {"FILE", "MODULE"} and len(key_parts) == 3 and key_parts[1] == path:
                return True
    elif "." in normalized and ":" not in normalized:
        # Dotted ``module.Class.attr`` refs point at a member of an indexed class.
        for key in entity_keys:
            key_parts = key.split(":", 2)
            if len(key_parts) != 3 or key_parts[0] != "CLASS":
                continue
            if normalized.startswith(f"{key_parts[2]}."):
                return True
    return False


def canonical_entity_keys(ref: str, entity_keys: set[str]) -> list[str]:
    """Exact index stable keys a free-form entity ref names (empty when ambiguous or unknown).

    Accepts ``TYPE:path:qualname``, ``TYPE path`` (``ROUTE POST /x``), a bare route
    (``POST /x``), ``path:qualname`` and a dotted qualified name. Every entity sharing the
    resolved ``path:qualname`` is returned, so a model class yields both CLASS and ORM_MODEL.
    """
    norm = ref.strip().replace("\\", "/")
    if not norm:
        return []
    if norm in entity_keys:
        return [norm]
    head, _, rest = norm.partition(" ")
    if head.isupper() and rest and ":" not in head:
        candidate = f"{head}:{rest}"
        if candidate in entity_keys:
            return [candidate]
        if f"ROUTE:{norm}" in entity_keys:
            return [f"ROUTE:{norm}"]
    by_tail: dict[str, list[str]] = {}
    by_qualname: dict[str, list[str]] = {}
    for key in entity_keys:
        typ, _, tail = key.partition(":")
        if not tail:
            continue
        by_tail.setdefault(tail, []).append(key)
        path_qn = tail.split(":", 1)
        if len(path_qn) == 2:
            by_qualname.setdefault(path_qn[1], []).append(key)
    _, _, typed_tail = norm.partition(":")
    for tail in (norm, typed_tail):
        if tail and tail in by_tail:
            return sorted(by_tail[tail])
    matches = by_qualname.get(norm, [])
    if matches and len({m.partition(":")[2] for m in matches}) == 1:
        return sorted(matches)
    # ``path:short_name`` / ``path::test`` (optionally TYPE-prefixed), or a bare dotted suffix.
    bare = norm.replace("::", ":")
    typ, sep, rest = bare.partition(":")
    if sep and typ.isupper() and "/" not in typ:
        bare = rest
    path, sep, short = bare.rpartition(":")
    if not sep:
        path, short = "", bare
    if not short or " " in short:
        return []
    hits = [
        key
        for key in entity_keys
        if len(parts := key.split(":", 2)) == 3
        and (not path or parts[1] == path)
        and (parts[2] == short or parts[2].endswith(f".{short}"))
    ]
    if hits and len({h.partition(":")[2] for h in hits}) == 1:
        return sorted(hits)
    return []


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
            sk = link.stable_key
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

    def prune_unsupported(
        self,
        survey: RepositorySurvey,
        feature_specs: list[RecoveredFeatureSpec],
        *,
        behavior_ids: set[str],
        fact_ids: set[str],
        fact_statements: set[str],
        entity_keys: set[str],
        principal_aliases: dict[str, list[str]] | None = None,
    ) -> tuple[RepositorySurvey, list[RecoveredFeatureSpec], list[dict[str, str]]]:
        """Drop citations that do not resolve, and claims left with none.

        Every claim that survives keeps at least one valid citation; a feature whose
        acceptance criteria are all dropped is removed. Principal entity links are rewritten
        to exact index stable keys and joined by the survey draft's principal entities;
        ``principal_aliases`` maps a handler or test key to the
        route/model keys it belongs to, which are linked as well. Returns what was pruned.
        """
        aliases = principal_aliases or {}
        pruned: list[dict[str, str]] = []

        def resolve(ref: str) -> list[str]:
            keys = canonical_entity_keys(ref, entity_keys)
            return keys + [a for k in keys for a in aliases.get(k, []) if a not in keys]

        def valid(citations: list[Citation], where: str) -> list[Citation]:
            kept: list[Citation] = []
            for cit in citations:
                errs = self._check_citations(
                    [cit], behavior_ids, fact_ids, fact_statements, entity_keys
                )
                if errs:
                    pruned.append({"where": where, "removed": "citation", "error": errs[0]})
                else:
                    kept.append(cit)
            return kept

        def prune_inferences(items: list[InferenceDraft], where: str) -> list[InferenceDraft]:
            out: list[InferenceDraft] = []
            for inf in items:
                cits = valid(inf.citations, f"{where}.inference")
                if cits:
                    out.append(inf.model_copy(update={"citations": cits}))
                else:
                    pruned.append(
                        {"where": where, "removed": "inference", "error": inf.statement[:120]}
                    )
            return out

        def prune_uncertainties(
            items: list[UncertaintyDraft], where: str
        ) -> list[UncertaintyDraft]:
            return [
                unc.model_copy(update={"citations": valid(unc.citations, f"{where}.uncertainty")})
                for unc in items
            ]

        pruned_survey = survey.model_copy(
            update={
                "inferences": prune_inferences(survey.inferences, "survey"),
                "uncertainties": prune_uncertainties(survey.uncertainties, "survey"),
            }
        )
        drafts = {f.ref: f.principal_entities for f in survey.features}
        kept_specs: list[RecoveredFeatureSpec] = []
        for spec in feature_specs:
            where = f"feature:{spec.feature_ref}"
            acs: list[RecoveredAcDraft] = []
            for ac in spec.acceptance_criteria:
                cits = valid(ac.citations, f"{where}.ac:{ac.ref}")
                if cits:
                    acs.append(ac.model_copy(update={"citations": cits}))
                else:
                    pruned.append(
                        {"where": where, "removed": "acceptance_criterion", "error": ac.ref}
                    )
            if not acs:
                pruned.append({"where": where, "removed": "feature", "error": "NO_SUPPORTED_ACS"})
                continue
            links: dict[str, PrincipalEntityLink] = {}
            for link in spec.principal_entity_links:
                keys = resolve(link.stable_key)
                if not keys:
                    pruned.append(
                        {
                            "where": where,
                            "removed": "entity_link",
                            "error": f"UNKNOWN_ENTITY:{link.stable_key}",
                        }
                    )
                    continue
                for key in keys:
                    links.setdefault(key, link.model_copy(update={"stable_key": key}))
            for ref in drafts.get(spec.feature_ref, []):
                for key in resolve(ref):
                    links.setdefault(key, PrincipalEntityLink(stable_key=key, confidence=0.5))
            kept_specs.append(
                spec.model_copy(
                    update={
                        "acceptance_criteria": acs,
                        "principal_entity_links": list(links.values()),
                        "inferences": prune_inferences(spec.inferences, where),
                        "uncertainties": prune_uncertainties(spec.uncertainties, where),
                    }
                )
            )
        return pruned_survey, kept_specs, pruned

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
