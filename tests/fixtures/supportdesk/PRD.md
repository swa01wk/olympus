# SupportDesk — Product Requirements Document

## Overview

SupportDesk is a lightweight ticket management API for internal support teams. Operators create and track tickets through their lifecycle from OPEN to CLOSED.

**Stack (NFR):** FastAPI, SQLAlchemy, pytest; SQLite is acceptable for the SupportDesk application database.

## Capability: Ticket Management

End-to-end ticket CRUD and status workflow.

### Feature: Create Ticket

Users can open a new support ticket with a subject and description.

**Rules:**
- Subject and description are required.
- Default status is OPEN.

### Feature: List Tickets

Users can list all tickets with optional status filter.

### Feature: Get Ticket

Users can fetch a single ticket by id.

### Feature: Update Ticket Status

Users can change ticket status (e.g. OPEN → IN_PROGRESS → CLOSED).

**Rules:**
- Closed tickets cannot be modified.
- An update to a CLOSED ticket is rejected with HTTP 409 Conflict.

### Feature: Close Ticket

Users can close a ticket (terminal state CLOSED).

## Capability: API Platform

### Feature: Health Check

A health endpoint returns service readiness for load balancers.
