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

Return ImplementationSpecDraft with open_questions if blocked.
