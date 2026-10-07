---
id: diagnostic.structured_echo
version: "1.0.0"
---

You are a diagnostic agent. Summarize the supplied text into a structured JSON object.

Requirements:
- `title`: short title for the passage
- `bullet_points`: between 1 and 5 concise bullets
- `word_count_estimate`: approximate word count of the source text

Source text:
{{ source_text }}
