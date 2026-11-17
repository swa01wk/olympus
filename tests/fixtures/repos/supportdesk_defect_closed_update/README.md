# SupportDesk with a defect (fixture)

`supportdesk_r1` plus `PATCH /tickets/{ticket_id}`. Planted defect: updating a CLOSED ticket
returns HTTP 500 instead of 409, because the transition table has no entry for CLOSED.
