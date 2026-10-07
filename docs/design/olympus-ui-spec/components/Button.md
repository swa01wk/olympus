# Button

Command trigger; at most one `primary` per view, for the thing the view is for (Open contextual detail, Approve, Execute release).

- **Provide:** `variant` (`primary` | `quiet` | `ghost`), optional `size="sm"`, `disabled`, `title`, `onClick`, children (verb-first label).
- A disabled command must say why — set `title` and, where space allows, a caption ("2 eligibility predicates unmet").
- Never use a button to change lifecycle state directly; it opens a dialog or sends a typed command.
