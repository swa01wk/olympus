---
id: atlas.architecture_delta
version: 3
---
{{ decision_context }}

# Architecture delta (Atlas)

Propose a minimal architecture **delta** when the feature change requires new components, contracts, or decisions.

## Project
{{project_name}}

## Current architecture
```json
{{architecture_summary}}
```

## Impact / change context
{{impact_summary}}

{% if revision_feedback %}
## Revision request
A reviewer asked for changes to your previous output.
Reviewer's note:
{{ revision_feedback }}
Your previous output:
{{ previous_output_json }}
Produce a complete new output. Change only what the note asks for, keep everything else as it was, and do not reintroduce anything the note asks to remove.
{% endif %}

Return `ArchitectureDeltaProposal` with only changed/added components and contracts.
