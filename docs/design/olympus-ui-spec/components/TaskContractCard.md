# TaskContractCard

Immutable execution boundary for one task version: objective, work type, pinned inputs, base commit, allowed scope, prohibited operations, constraints, outputs, verification, escalation.

- **Provide:** `contract`, `taskId`.
- Versions are immutable; a revised contract is a new version and makes earlier attempts stale.
