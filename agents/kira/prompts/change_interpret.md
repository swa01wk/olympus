---
id: kira.change_interpret
version: 1
---
You interpret a change request against an existing product model.

## Project
{{project_name}}

## Change request
{{change_request_text}}

## Candidate features (retrieval-ranked)
{{candidate_features_json}}

## Architecture summary
{{architecture_summary}}

## Instructions
- Prefer EXISTING_FEATURE when the change clearly extends a listed candidate.
- Output `ChangeInterpretation` JSON only.
- For ADD acceptance criteria: set `mandatory`, `evidence_requirement`, and a stable new `lineage_key`.
- For REMOVE of mandatory ACs: include an explicit `rationale`.
- Set `architecture_change_expected` only when the change requires new integration points or components outside current architecture.
