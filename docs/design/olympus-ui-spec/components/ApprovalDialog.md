# ApprovalDialog

Explicit, attributable human decision: decision type, scope, exact version / SHA, reason and impact, risk, supporting records, required rationale, then Reject / Request changes / Approve.

- **Provide:** `subject` (`ApprovalSubject`), `open`, `onClose`, or `inline` for documentation.
- Full keyboard operation, focus containment and restoration. The server validates expected version and authorization. Never place an approval behind a chat transcript.
