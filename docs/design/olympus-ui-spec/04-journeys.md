# Journeys

The same ten screens run all four journeys. What changes is the **ribbon** (stages), the **spine** (lane order), which **drill-down is primary at each stage**, and the **content mode** of S03, S08, S09 and S10. The **Journey × screen matrix** page in Components → Specification shows all 40 cells.

## What changes, screen by screen

| Screen | Greenfield (DC-001) | Brownfield (DC-002) | Feature Change (DC-003) | Bug Fix (DC-004) |
|---|---|---|---|---|
| S01 Overview | No released baseline; R1 target | Existing repo + R1; B1 target | R1 baseline, R2 target | R2 baseline, R3 target |
| S02 Cycle map | Spine runs left → right | Spine starts in CD, doubles back to IN | One early hop to CD for impact | Zig-zag EV ↔ IN ↔ CD |
| S03 Specs | Decompose PRD; scope / architecture approval | Observed vs recovered vs canonical | v1 → v2 behavioural / technical delta | Resolve expected behaviour or checkpoint |
| S04 Task DAG | Implementation + verification deps | Discovery / baseline work, no feature build | Minimal impact-aware tasks | Minimal bounded repair tasks |
| S05 Execution | Writable attempts, checkpoints | Read-only discovery; isolated baseline runs | Bounded code changes; stale retry | Reproduction, diagnostic, repair; denied action |
| S06 Code | New code, GENERATED_LINEAGE | Existing structure, DISCOVERED links | Affected symbols, incremental re-index | Failure path, before / after SHA |
| S07 Trace | Source → verified R1 | Code → recovered intent → readiness (reversed) | Request + delta → safe R2 | Defect + before/after proof → R3 |
| S08 Impact | Architecture boundaries | Readiness gaps, uncertainty | Symbols / contracts / tests / baselines | Probable cause + minimal scope |
| S09 Assurance | New mandatory AC proof + review | Readiness conditions, not gates | New ACs + impacted old behaviour | Original failure passes + regression + baselines |
| S10 Release | Verified R1; optional deployment | Readiness handoff; no release command | Verified R2 manifest | Verified R3 manifest |

## Greenfield Build · DC-001 · Product → Code · outcome R1

| Stage | Lane | Primary surface | Operator action | Persisted output | What the map shows |
|---|---|---|---|---|---|
| DISCOVERY | IN | Intake → S03 | Upload PRD or description | Immutable ProductSource, version, hash | Source enters the graph; extraction is a proposal |
| PRODUCT_MODEL | IN | S03 | Resolve questions, review scope | Capabilities, features, FeatureSpecs, ACs | Proposed vs approved versions; APR-101 pending |
| ARCHITECTURE | IN | S08 / S03 | Review architecture where policy requires | ARCH baseline, contracts, ImplementationSpecs | Project-wide constraint edges into IMPL |
| PLANNING | WK | S04 | Inspect plan and dependencies | Validated DAG, compiled TaskContracts | Why each task is ready / blocked |
| DEVELOPMENT | EX | S05 | Observe; answer checkpoints | Snapshots, leases, worktrees, candidates | Failed EX-102 kept; EX-104 checkpointed on CHK-012 |
| INTEGRATION | CD | S06 | Inspect combined candidate / conflicts | IC-001 @ 9e31ab7, canonical index, links | Candidates converge; target ≠ released baseline |
| ASSURANCE | EV | S09 | Inspect gaps; request verification | AC proof, Warden review, gates | Same-SHA evidence; missing obligations |
| RELEASE | OU | S10 | Review approval; execute when eligible | R1 manifest, outcome bundle | All predicates, including approvals, server-evaluated |
| COMPLETE | OU | S01 / S07 | Inspect outcome, continue | R1 and complete lineage | Project persists for later cycles |

## Brownfield Onboarding · DC-002 · Code → Product model · outcome B1 + READY_FOR_CHANGE

| Stage | Lane | Primary surface | Operator action | Persisted output | What the map shows |
|---|---|---|---|---|---|
| RECON | CD | Intake → S02 | Register repo, branch, exact SHA | Immutable source reference, deterministic facts | Code inputs precede product recovery |
| CODE_INDEX | CD | S06 | Inspect structure and tests | AST / routes / schemas / tests @ 9e31ab7 | Canonical structure; intent still unknown |
| RECOVERED_SPEC | IN | S03 / S07 | Review evidence, uncertainty, provenance | ObservedBehaviour, RecoveredSpec, DISCOVERED links | FACT vs INFERENCE vs UNCERTAINTY; OB-011 "Not blessed" |
| BASELINE | EV | S09 / S04 | Review baseline proposals; request runs | Baselines, exact-SHA proof | Accidental behaviour is never silently blessed |
| READINESS | EV | S09 / S08 | Resolve gaps; promote trusted intent | Promotions, DEC-004, readiness assessment | Coverage + baselines + open uncertainty |
| READY | OU | S10 / S01 | Start a Feature Change or Bug Fix | B1 + READY_FOR_CHANGE | R1 unchanged; no new release or deployment |

## Feature Change · DC-003 · Product delta → Code delta · outcome R2

| Stage | Lane | Primary surface | Operator action | Persisted output | What the map shows |
|---|---|---|---|---|---|
| INTAKE | IN | Intake → S02 | Submit requested behaviour | ChangeRequest CR-004 in project context | Request enters the existing product/code graph |
| SPEC_DELTA | IN | S03 | Review v1 → v2, approve | Versioned FeatureSpec / ImplementationSpec | Stable feature identity; APR-301 |
| IMPACT_ANALYSIS | CD | S08 | Inspect paths, tests, baselines | IA-003 with rationale | Direct (solid) vs inferred (dashed, 0.62) impact |
| PLANNING | WK | S04 | Inspect minimal plan | Tasks + immutable contracts | Scope precedes admission |
| DEVELOPMENT | EX | S05 | Observe bounded work | Attempts, snapshots, worktrees, candidates | EX-203 stale (TC-104 v1 ≠ v2); EX-204 current |
| INTEGRATION | CD | S06 | Inspect combined change / re-index | IC-003 @ c83a12d, refreshed links | Canonical index advances; released baseline stays R1 |
| ASSURANCE | EV | S09 | Verify new ACs + impacted baselines | EV-501, EV-601…603, WR-003 | AC-011-03 missing at c83a12d; APR-302 pending |
| RELEASE | OU | S10 | Approve; execute when eligible | R2 manifest and outcome | Release independent of optional deployment |
| COMPLETE | OU | S01 / S07 | Inspect lineage, continue | R2 becomes project baseline | R1, superseded versions and failures retained |

## Bug Fix · DC-004 · Failure → Spec → Code path → Repair · outcome R3

| Stage | Lane | Primary surface | Operator action | Persisted output | What the map shows |
|---|---|---|---|---|---|
| TRIAGE | IN | Intake → S02 | Report defect with steps | DEF-017 with source and severity | Failure enters as a reported observation |
| REPRODUCTION | EV | S09 / S05 | Inspect failing scenario at before-SHA | EV-901 @ c83a12d | "Failure reproduced", a successful investigation, not a PASS |
| EXPECTED_BEHAVIOR | IN | S03 | Resolve intent from canonical spec | AC-017-04 via SPEC-017 v3 (DEC-004) | Unknown expectation would checkpoint for a decision |
| ROOT_CAUSE | CD | S08 | Review probable path and scope | RC-004, p = 0.78, trace + code evidence | Probability shown apart from proven cause |
| DEVELOPMENT | EX | S04 / S05 | Observe minimal repair | TC-402, EX-402, candidate 0b9e3f1 | One denied out-of-scope write, logged, not retried wider |
| INTEGRATION | CD | S06 | Inspect repaired SHA / re-index | IC-004 @ e5d1c04 | Before and after SHAs explicit |
| REGRESSION | EV | S09 | Re-run original + regression + baselines | EV-951, EV-952, EV-961…963 | Failing history retained; new independent proof |
| ASSURANCE | EV | S09 | Inspect review, findings, gates | Warden / Sentinel results, GATE-004 | No producer self-certification |
| RELEASE | OU | S10 | Approve; execute when eligible | R3 manifest | Verified repaired SHA pinned |
| COMPLETE | OU | S07 / S01 | Inspect forensic history | Defect → failure → intent → repair → proof → R3 | Failure evidence reachable after repair |
