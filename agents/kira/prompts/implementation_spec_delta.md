---
id: kira.implementation_spec.delta
version: 1
---
Produce an `ImplementationSpecDraft` whose body describes **only** the delta needed for the approved FeatureSpec change.

## Project
{{project_name}}

## Feature spec
Key: {{feature_spec_key}}

```json
{{feature_spec_body}}
```

## Acceptance criteria
```json
{{acceptance_criteria}}
```

## Architecture
```json
{{architecture_summary}}
```

## Parent implementation spec (FULL baseline)
```json
{{parent_implementation_spec_json}}
```

## Impact assessment items
```json
{{impact_assessment_json}}
```

## Mode
DELTA — constrain `file_scope` to paths that must change. Include `data_changes` with defaults when adding DB columns. Address every DIRECT contract-surface impact item in components, apis, schemas, or data_changes.
