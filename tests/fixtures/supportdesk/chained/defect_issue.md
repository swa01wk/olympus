# Defect: closed ticket update returns HTTP 500

When PATCHing a ticket that is already **CLOSED**, the API returns HTTP **500** instead of rejecting the update.

Expected behavior: HTTP **409 Conflict** per product acceptance criteria.

Label: `olympus:defect`
