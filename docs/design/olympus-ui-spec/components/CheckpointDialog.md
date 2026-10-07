# CheckpointDialog

Clarification checkpoint: question ID, unknown intent, authoritative sources already checked, required answer, waiting execution.

- **Provide:** `c` (`CheckpointSubject`), `open`, `onClose`, or `inline`.
- The answer becomes a durable decision (and a spec version where needed); resume or replan follows policy, never the model transcript.
