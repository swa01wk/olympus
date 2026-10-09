---
id: kira.implementation_spec_repair
version: 3
---
Draft a minimal REPAIR ImplementationSpec for a defect fix.

Project: {{project_name}}
Root cause summary: {{root_cause_summary}}
Expected behavior: {{expected_behavior}}
Expected behavior AC ids: {{expected_ac_keys}}
Reproduction artifact: {{reproduction_artifact_ref}}
Impact assessment: {{impact_assessment_json}}

Root cause (faulty stable keys carry the source file path, e.g. `METHOD:<path>:<symbol>`):
```json
{{root_cause_json}}
```

Architecture:
```json
{{architecture_summary}}
```

Rules (strict — output is validated):
- `components`: only names from `valid_component_names`, choosing the components whose `directory` contains the faulty files. Never module or symbol names.
- `file_scope`: concrete repository paths (e.g. `app/services/example_service.py`) of the files to change, under architecture directories; at most {{max_repair_files}} non-test source files, plus the regression test file.
- `required_tests`: a regression test that reproduces the defect, at a concrete path under `tests/` (not `tests/olympus_repro/`), named in the description, e.g. `tests/test_<area>_regression.py`.
- `ac_coverage`: list that regression test path in `locations`.
- `apis[].contract_key`: only keys from `valid_contract_keys`, or null.
- `architecture_refs`: only values from `valid_architecture_refs`.

{% if revision_feedback %}
## Revision request
A reviewer asked for changes to your previous output.
Reviewer's note:
{{ revision_feedback }}
Your previous output:
{{ previous_output_json }}
Produce a complete new output. Change only what the note asks for, keep everything else as it was, and do not reintroduce anything the note asks to remove.
{% endif %}

Return ImplementationSpecDraft with open_questions if blocked.
