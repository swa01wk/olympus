# StatusBadge

Textual state chip: a glyph plus a word, toned by meaning, for every record state in Olympus.

- **Provide:** `status` (a key from `model.STATUS`, e.g. `running`, `missing`, `approval-pending`), optional `label` override, optional `size="sm"`.
- Tones: `success` recorded/approved/passed/released; `attention` waiting/review/blocked/missing/inference; `failure` failed/denied/rejected/failure evidence; `active` running/ready; `future` dashed for obligations; `muted` superseded/historical.
- Never rely on colour alone; never invent a new state word in a view — add it to the vocabulary.
- "Failure reproduced" is a successful investigation, not a pass. "Awaiting approval" means proof ready, approval pending — not eligible.
