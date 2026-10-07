# Truth rules

Distinctions every screen must keep visible. If a design blurs one of these, it is wrong regardless of how it looks.

| Concept | Required visible distinction | Consequence |
|---|---|---|
| Task vs Execution | Durable work vs one immutable attempt | Failures and retries stay reachable; task completion requires validated outputs |
| Snapshot vs current project | Pinned inputs / contract / base SHA vs later state | Changed inputs make an attempt **Stale** and require revalidation |
| Candidate index | Execution-scoped provisional code | Never implies a released or canonical baseline |
| Canonical assurance index | Exact current IntegrationCandidate SHA | Independent gates and final proof target this SHA |
| Released baseline | Exact manifest SHA of the latest recorded release | Does not advance because a candidate integrated |
| Structural fact vs intent | AST / route / schema observation vs intended behaviour | Recovered product truth requires evidence-backed review / promotion |
| Evidence freshness | Target SHA, source version and obligation explicit | Old-SHA proof is history; it cannot satisfy the current target |
| Technical checks vs eligibility | Proof ready · approval pending · eligible · released are distinct | Required approvals are part of eligibility; approval never replaces proof |
| Release vs deployment | Recorded delivery outcome vs optional external deploy | No green deployment badge without an independent deployment result |
| Producer vs verifier | Forge produces; Warden / Sentinel recommend; Olympus finalizes | No self-certification; gate state is a server computation |

## Exceptional states

Same anatomy everywhere: textual state chip → reason → consequence → permitted next action. The **Exception states** page shows each one rendered.

| State / trigger | Visible reason and consequence | Permitted next action |
|---|---|---|
| Unknown expected behaviour | Bug repair waits; no invented semantics | Resolve from canonical spec / baseline, or request a human decision |
| Proposed Brownfield inference | Confidence and code evidence shown; not canonical intent | Review, request evidence, reject, or promote with authority |
| Dependency blocked | Unmet task / artifact / approval predicate with blocking IDs | Open the blocker; schedule only after eligibility recomputes |
| Out-of-scope tool action | Denied action logged with contract scope and policy | Request bounded scope change / approval; never retry wider |
| Execution failed / timed out | Attempt and artifacts retained; task not auto-completed | Inspect failure; create a policy-compliant retry |
| Checkpoint / lease expiry | Waiting question and worker ownership visible | Resolve, then resume / replan; history preserved |
| Stale snapshot / changed base | Pinned inputs differ from authoritative versions | Revalidate, or create a new contract / snapshot / attempt |
| Integration conflict | Conflict is a Finding, not a hidden merge success | Create remediation work and reintegrate |
| Missing or old-SHA evidence | Obligation, wrong SHA and current SHA visible | Request exact-target verification |
| Assurance failure | Gate cannot pass; finding linked to proof | Repair loop, then targeted revalidation |
| Approval pending / rejected | Technical readiness does not imply eligibility | Review the decision; revise scope when rejected |
| Connector outcome unknown | Possible external mutation; no blind retry | Reconcile provider state using the external correlation ID |
| Event stream disconnected | Last authoritative refresh time and disconnected state | Refetch current state; no optimistic green completion |
| Empty / loading / forbidden | Explains the unavailable object or action, keeps context | Upload / register a source, retry, or use an authorized account |
