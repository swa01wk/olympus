---
id: sentinel.reproduce
version: 1
---
Author a pytest reproduction test for the defect triage plan.

Triage JSON:
{{triage_json}}

Write test source for path under tests/olympus_repro/. Use TestClient(app, raise_server_exceptions=False) for HTTP steps. Return relative_path, test_source, and observed_symptom_signature.
