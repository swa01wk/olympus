---
id: kira.implementation_spec_repair
version: 2
---
Draft a minimal REPAIR ImplementationSpec for a defect fix.

Project: {{project_name}}
Root cause summary: {{root_cause_summary}}
Impact assessment: {{impact_assessment_json}}
Expected behavior AC keys: {{expected_ac_keys}}
Reproduction artifact: {{reproduction_artifact_ref}}

Constraints:
- file_scope must include at most {{max_repair_files}} non-test source files
- required_tests must describe a regression test under tests/ (not tests/olympus_repro/)
- components limited to faulty symbols' modules

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
