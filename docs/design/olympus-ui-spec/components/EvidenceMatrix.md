# EvidenceMatrix

Obligation × evidence × target SHA × result, grouped by obligation kind.

- **Provide:** `groups` (`{name, rows: [obligation, evidenceId, sha, status, note?]}`), `target` ("IC-003 · c83a12d"), `onRef`.
- Rows whose SHA is not the current target are shown as history ("not current target") and can never satisfy an obligation.
