# UI concept

## The control plane is the product

Olympus' core claim is architectural: *AI reasons probabilistically; Olympus controls deterministically.* A UI built from conventional pages (Overview, Tasks, Executions, Code, Assurance) hides that claim. The operator sees a list of agent activity and has to reconstruct authority, lineage and blockers in their head. So the Olympus UI makes the control plane itself the workspace:

- **The Delivery Cycle map (S02) is home.** It shows the connected authoritative records of one bounded objective: what was requested, what work exists, which attempts ran, what code is canonical, what proves it and what the outcome is.
- **Every other screen is a drill-down** into one region of that map, entered from the map and returned to with "Back to cycle map". The rail keeps direct access for expert users. The ten screens are not a wizard.
- **Selecting is not acting.** Clicking a node only selects it. Commands live in the inspector and in dialogs, and they always go through the typed command API.

## Six lanes, fixed across all journeys

The map arranges records into six lanes, left to right, in the order authority flows. Lane positions never change between journeys, so the operator's spatial memory carries over from cycle to cycle.

| Code | Lane | Question it answers | Drill-down |
|---|---|---|---|
| `IN` | Intent & product | What is wanted, and which version is approved? | S03 Product / Specs |
| `WK` | Planned work | What durable work exists, and why is it ready or blocked? | S04 Task DAG |
| `EX` | Executions | Which bounded attempts ran, and what did they produce? | S05 Execution Inspector |
| `CD` | Canonical code | What does the repository structurally contain, at which SHA? | S06 Code Intelligence |
| `EV` | Evidence & decisions | What proves it, and who decided? | S09 Assurance |
| `OU` | Outcome | What was delivered, and is it eligible? | S10 Release |

Two screens cut across all lanes, so they are **lenses** on the same graph before they become full screens:

- **Trace lens → S07 Traceability**: the bidirectional lineage of the selected record.
- **Impact lens → S08 Impact Explorer**: direct and inferred impact, plus the bounded scope.

A fourth lens, **Blockers**, isolates the chain between now and the next stage.

## The journey spine: what makes each journey look different

Above the lanes, a row of numbered dots shows the order in which the journey's lifecycle stages move through the lanes. Done stages are filled, the current stage is in `active`, and future stages are dashed. Forward hops arc above and backward hops arc below. The spine is the visual signature of a journey:

- **Greenfield** runs left to right. Intent → work → execution → code → evidence → outcome.
- **Brownfield** starts in Code (RECON, CODE_INDEX), doubles back to Intent (RECOVERED_SPEC), then moves to Evidence and Outcome. There is no Execution-heavy middle and no new release.
- **Feature Change** makes one early hop to Code for IMPACT_ANALYSIS before planning, then runs forward.
- **Bug Fix** zig-zags. Intent (TRIAGE) → Evidence (REPRODUCTION) → Intent (EXPECTED_BEHAVIOR) → Code (ROOT_CAUSE) → forward again, with two Evidence stages (REGRESSION, ASSURANCE) at the end.

The lifecycle ribbon above the map says *when* the cycle is. The spine says *where* that is in the graph. The lane of the current stage is outlined in `active`.

## Map anatomy (S02)

1. **Cycle header**: objective as title; cycle ID, journey, direction and target outcome; lifecycle ribbon (each stage labelled with its lane code). Clicking a stage shows a design snapshot; in production that is history replay only.
2. **Attention strip**: the single highest-priority reason the operator is needed. The order is checkpointed → decision → missing evidence → review → pending approval. It has "Why this state?" and "Inspect <record>". When nothing needs the operator, it says so plainly.
3. **Graph panel**: lens switcher, legend, Graph / List toggle, journey spine, six lanes with typed edges.
4. **Object inspector (320px)**: type and lane; ID and version; title; state and provenance chips; *Why this state?* (predicates, blocking IDs, policy key, inputs, evaluation time, next); provenance and SHA scope; relations as sentences ("CODE-117 IMPLEMENTS SPEC-011 v2"; hover one to locate it on the map); permitted commands with their typed API preview; "Open in <drill-down> →".

## Drill-down anatomy (S03–S10)

Each drill-down keeps the cycle header and ribbon. It adds "← Back to cycle map" and a **lane strip**: a one-row mini-map of the six lanes with materialized/total counts and attention flags, the current lane outlined and the live-stage lane filled. The strip lets the operator move sideways between drill-downs without losing the cycle. A drill-down whose records have not materialized at the viewed stage shows an empty state that names the stage that will create them.
