# Defect report

**Title:** Updating a CLOSED ticket returns HTTP 500

**Description:** When PATCHing a ticket that is already CLOSED, the API returns HTTP 500 instead of rejecting the update. Expected behavior is HTTP 409 Conflict per product acceptance criteria.
