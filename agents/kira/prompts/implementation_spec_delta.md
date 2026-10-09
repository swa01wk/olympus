---
id: kira.implementation_spec.delta
version: 3
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

{% if revision_feedback %}
## Revision request
A reviewer asked for changes to your previous output.
Reviewer's note:
{{ revision_feedback }}
Your previous output:
{{ previous_output_json }}
Produce a complete new output. Change only what the note asks for, keep everything else as it was, and do not reintroduce anything the note asks to remove.
{% endif %}

## Mode
DELTA — constrain `file_scope` to paths that must change. Include `data_changes` with defaults when adding DB columns. Address every DIRECT contract-surface impact item in components, apis, schemas, or data_changes.

## Rules (strict — output is validated)
- `components`: only names from `valid_component_names` in the architecture JSON, never module paths or class names.
- `apis[].contract_key`: only keys from `valid_contract_keys`.
- `file_scope`: only paths under architecture directories; each entry must end with `/**` or `/*.py`.
- `architecture_refs`: only values from `valid_architecture_refs`.
