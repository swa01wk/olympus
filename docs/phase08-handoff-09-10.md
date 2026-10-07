# Phase 08 handoff — Assurance (09) and Release (10)

This document satisfies Phase 08 §15: **`FindingPolicy`** and **`LineageService.register_hop`** are documented for downstream phases.

## FindingPolicy (`core/assurance/findings_policy.py`)

**Purpose.** Agents (Warden in Phase 09, merge executor in Phase 08) propose **severity** and **category**; Olympus computes **`blocking`** from policy. Agents must never set `blocking` directly on persisted findings.

**Config.** `config/policy/default.yaml` → `findings:`:

| Key | Meaning |
|-----|---------|
| `blocking_severities` | Any finding with this severity is blocking (default: `BLOCKER`, `MAJOR`). |
| `blocking_categories` | Any finding with this category is blocking regardless of severity (default includes `MERGE_CONFLICT`, `INTEGRATION_CHECK_FAILED`, `BASE_NOT_ANCESTOR_OF_CANONICAL`). |

**API.**

```python
FindingPolicy().is_blocking(severity: str, category: str) -> bool
```

**Phase 09 extension.** Warden persists findings with `source=WARDEN`; call `FindingPolicy().is_blocking(...)` before insert/update. Waivers use `Approval(FINDING_WAIVER)` (Phase 09).

**Phase 08 usage.** `core/assurance/findings.py` sets `blocking` via `FindingPolicy` when creating machine findings (e.g. merge conflicts).

## LineageService.register_hop (`core/traceability/lineage/service.py`)

**Purpose.** Compose **forward** and **reverse** product-to-code graphs by chaining async hop functions. Phase 08 registers product/spec/code hops in `core/traceability/lineage/factory.py` (`build_lineage_service()`).

**Extension point (Phase 09 / 10).**

```python
LineageHop = Callable[[AsyncSession, LineageGraph, str], Awaitable[None]]


class LineageService:
    def register_hop(self, hop: LineageHop) -> None: ...
```

- **`forward(session, root_type, root_id)`** — runs registered hops up to three passes (allows hops to append nodes/edges that later hops consume).
- **`reverse(session, code_entity_id)`** — walks `SpecCodeLink`, `CodeEntityChange`, and registered hops toward product roots.

**Phase 09.** Register hops that attach **Evidence**, **verification obligations**, and **gate** nodes to the graph (same `LineageGraph` / `LineageNode.type` conventions).

**Phase 10.** Register hops from **Release** / manifest SHA back to verified IC and evidence.

**Default hops (Phase 08).** See `hop_feature_to_specs`, `hop_specs_to_impl_and_code`, `hop_reverse_product_context` in `core/traceability/lineage/hops.py`.

## Obligation source registry (`core/assurance/obligations.py`)

**Purpose.** Deterministic verification obligations are derived when an IC becomes READY. Phase 09 ships the **AC mandatory/optional** source; later phases register more sources without changing the orchestrator.

**Extension point.**

```python
from core.assurance.obligations import register_obligation_source

register_obligation_source(my_async_source_fn)
```

Each source returns `list[VerificationObligation]` for the IC. **`ObligationService.derive`** runs all registered sources once per IC (idempotent via DB uniqueness on subject + gate).

**Phase 10 / 12 / 13 / 15.** Register baseline, regression, reproduction, and impact-driven sources here; gate finalizer scope filters by `gate_type` (see `core/assurance/gates.py`).

## Gate finalizer hook (`core/assurance/release_hook.py`)

**Purpose.** After all gates on an IC finalize, **`recompute_release_eligibility`** runs (no-op until Phase 10 implements release conditions). Phase 09 documents the hook so Phase 10 can register eligibility without changing assurance orchestration.

**Phase 10.** Implement condition registry + manifest eligibility against `required_gates_pass` and evidence at the integrated SHA.

## Verification

```bash
./scripts/verify-phases-00-07.sh --phase 08 --live
```

Includes §15: handoff doc check, deterministic `tests/workflow/integration`, and live Forge IC precursor (one live Forge + one deterministic candidate → IC READY) when API keys are configured.
