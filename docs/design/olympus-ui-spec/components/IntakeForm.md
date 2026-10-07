# IntakeForm

New delivery cycle with journey-specific fields: product source (Greenfield), repository + branch + exact SHA (Brownfield), requested behaviour + baseline (Feature Change), observed result + reproduction steps + severity (Bug Fix).

- **Provide:** `initial` journey id, `open`, `onClose`, or `inline`.
- On submit: validate, send the typed create command, wait for the persisted acknowledgement, then navigate to the new cycle map.
