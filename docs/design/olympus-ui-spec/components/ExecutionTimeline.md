# ExecutionTimeline

Governed tool events for one attempt with the ToolGateway decision on each row.

- **Provide:** `events` (`[time, text, action, decision]`, decision ∈ allowed | denied | failed | passed | platform).
- Denied actions stay in the log with their scope reason; a failed step keeps its evidence.
