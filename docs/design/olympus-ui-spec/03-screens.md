# Screens

Ten canonical screens. S02 is the hub; S03–S06, S09 and S10 are lane drill-downs; S07 and S08 are lens drill-downs; S01 sits above the cycle. Each screen card in **Components → Screens** is a live prototype that starts on that screen.

## S01 · Project Overview
- **Goal.** Show persistent project truth, the active objective and the operator's next decision.
- **Composition.** Four truth tiles: released baseline, canonical assurance index, product model, behavioural baselines. Active-cycle panel with objective, journey spine, compact ribbon and attention queue. Coverage with explicit denominators. Project continuity table of every cycle with its outcome.
- **Actions.** Open control-plane map (primary), inspect an attention item, start a new delivery cycle.
- **Truth rule.** No overall completion percentage. Every coverage bar names what it counts: spec→code mapping, mandatory AC proof, or executable baseline coverage.
- **Objects.** Project, DeliveryCycle, Release, CodeIndexVersion, approval and blocker summaries.

## S02 · Delivery Cycle (hub)
- **Goal.** Operate the current change through a visible control plane.
- **Composition.** Cycle header and ribbon, attention strip, graph panel (lenses, legend, Graph/List, journey spine, six lanes), object inspector.
- **Actions.** Select, explain, switch lens, open a drill-down, request a permitted typed command.
- **Truth rule.** The ribbon is lifecycle, the graph is connected records, the inspector is authorization and reasons. Viewing a node never issues a command. Future obligations are dashed and never drawn as complete.
- **Objects.** DeliveryCycle and every product, work, execution, intelligence and assurance record in its neighbourhood.

## S03 · Product / Specs (lane IN)
- **Goal.** Review intended behaviour, technical realization, versions and provenance.
- **Composition.** Capability → feature → spec tree with states. Centre panel by journey: proposed spec with source quote, rules, ACs and open clarification (GF); observed vs recovered vs canonical table with provenance (BF); v1 → v2 version diff with ACs and regression baseline (FC); observed vs expected with sources checked (BG). Right: ImplementationSpec and project architecture.
- **Actions.** Approve scope / spec, request changes, answer clarification, review and promote recovered intent, inspect impact scope.
- **Truth rule.** Behavioural truth (FeatureSpec) and implementation design (ImplementationSpec) stay distinct. Architecture is project-wide; an ImplementationSpec cannot silently redefine it. Brownfield recovery is proposed until reviewed.

## S04 · Task DAG (lane WK)
- **Goal.** Explain dependency order, admission and durable work boundaries.
- **Composition.** Layered DAG (dotted edge = dependency still waiting) with a List toggle. A "Why is <task> <state>?" box with the seven scheduler predicates. Immutable TaskContract (inputs pinned by version, base commit, allowed scope, prohibited, constraints, outputs, verification, escalation). Attempt history.
- **Actions.** Inspect contract and dependencies, follow active or historical execution.
- **Truth rule.** A task is durable; an execution is one attempt. A passing unit test or a producer declaration does not complete the task, the product or the release.

## S05 · Execution Inspector (lane EX)
- **Goal.** Make bounded autonomous work and its recovery attributable.
- **Composition.** All attempts in the cycle (failures and stale attempts stay). Attempt header: contract, snapshot, base SHA, capability and runtime. Checkpoint callout when waiting. Governed tool events with the ToolGateway decision for each (Allowed, Denied · logged, Failed, Passed). Provisional candidate diff. Boundary panel: lease and heartbeat, snapshot hash, workspace, model policy alias, observed provider metadata, permitted tools.
- **Actions.** Inspect contract, answer checkpoint, request cancellation, open attempt lineage.
- **Truth rule.** A retry creates a new attempt; failed attempts and old snapshots are kept. Show the configured model alias and the observed provider metadata, never a hard-coded model name.

## S06 · Code Intelligence (lane CD)
- **Goal.** Inspect structural repository truth and how it relates to specification intent.
- **Composition.** A three-way SHA scope banner: provisional candidate · canonical assurance target · released baseline. File and symbol tree with Δ / new tags. Symbol detail with an illustrative excerpt and a relations table (relation, target, origin, confidence). Spec ↔ code links with origin, confidence and evidence.
- **Actions.** Switch scope, trace symbol to intent, show impact.
- **Truth rule.** The three scopes are always labelled separately. Canonical structural facts do not make discovered intent canonical. Principal symbols map to specs; helpers inherit context through structure.

## S07 · Traceability (trace lens)
- **Goal.** Answer why code exists, what produced it, what proves it and which outcome contains it.
- **Composition.** Narrative lineage, one step per layer, with record chips and state, relation labels between steps, an Origin → outcome / Outcome → origin toggle and a history toggle (failed, stale, denied). Answer panel and link-origin legend (GENERATED_LINEAGE, DISCOVERED, HUMAN_CONFIRMED).
- **Actions.** Follow any record in either direction, show on map in the trace lens, inspect code or proof.
- **Truth rule.** Historical, superseded and inferred links stay visible with labels.

## S08 · Impact Explorer (impact lens)
- **Goal.** Establish a bounded change or repair scope before writable execution.
- **Composition.** Lead, direct structural impact table (FACT), inferred expansion table (INFERENCE with confidence, or below-floor exclusions), proposed scope (paths, selected verification and why, risk, architecture delta).
- **Actions.** Review bounded plan, escalate architecture delta, show on map in the impact lens.
- **Truth rule.** Per journey: Greenfield shows architecture and realization boundaries; Brownfield shows readiness gaps and uncertainty; Feature Change shows affected symbols, contracts, tests and baselines; Bug Fix shows failure path and probable cause. Inference is never shown as proven fact.

## S09 · Assurance (lane EV)
- **Goal.** Inspect independent evidence, gaps, findings and deterministic gate state.
- **Composition.** Exact-target banner. Evidence matrix of obligation × evidence × target SHA × result, where an old-SHA row is labelled "not current target". Gate finalization checklist, or readiness conditions for Brownfield. Findings and the remediation loop.
- **Actions.** Inspect blocking proof, request exact-target verification, open finding or repair work, open release eligibility.
- **Truth rule.** Agents provide evidence and recommendations; Olympus finalizes gates. Old-SHA proof cannot satisfy the current candidate. Brownfield uses readiness conditions, not release gates.

## S10 · Release (lane OU)
- **Goal.** Review exact-SHA eligibility, required decisions and the recorded outcome.
- **Composition.** Versioned manifest, server eligibility predicates (release.eligibility), approvals, release truth (assurance target, current released baseline, deployment), outcome history, and a separate optional deployment.
- **Actions.** Review release approval, execute release (enabled only when every predicate passes), open complete lineage. Brownfield instead shows a readiness handoff with "Start Feature Change" / "Start Bug Fix", enabled at READY_FOR_CHANGE.
- **Truth rule.** Proof ready, approval pending, eligible and released are distinct states. Approval cannot replace proof. Release is not deployment: no green deployment badge without an independent deployment result.
