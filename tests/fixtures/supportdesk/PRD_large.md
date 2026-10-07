# Large SupportDesk PRD (fixture)

Preamble describing the product at a high level for chunking tests.

## Create Ticket

Users create support tickets with a subject and description. Default status is OPEN.

## Update Ticket Status

Users change ticket status. Closed tickets must reject further updates with HTTP 409.

## List Tickets

Users browse tickets with pagination and optional status filter.

## Assign Ticket

Operators assign tickets to agents; assignment history is retained.

## Search Tickets

Full-text search across subject and description fields.

## Ticket Comments

Threaded comments on tickets with author and timestamp.

## Notifications

Email notifications on status changes and new assignments.

## Audit Log

Immutable audit trail for ticket and assignment changes.

## Reporting

Basic volume and SLA reports for managers.

## Admin Settings

Configure statuses, priorities, and notification templates.
