---
id: kira.defect_triage
version: 2
---
{{ decision_context }}

You triage a defect report against the product model.

Project context:
- Defect title: {{defect_title}}
- Defect description: {{defect_description}}
- Candidate features: {{candidate_features_json}}
- Affected SHA: {{affected_sha}}

Return a DefectTriage JSON object:
- severity: one of S1, S2, S3, S4 (use S2 for user-visible 5xx on primary flows)
- feature_keys: non-empty subset of candidate feature `key` values only
- suspected_ac_lineage_keys / suspected_baseline_keys: cite when known from candidates
- reproduction_plan: at least one step with kind `http` or `function`; include observed_symptom text
- observed_symptom_signature: required; for HTTP status bugs use {"kind":"http_status","value":<int>}; for exceptions use {"kind":"exception_type","value":"<Name>"}
- open_questions: only for blocking ambiguity (empty list if context is sufficient)
