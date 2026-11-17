from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketCreate, TicketStatus

TRANSITIONS: dict[str, set[str]] = {
    TicketStatus.OPEN.value: {TicketStatus.CLOSED.value},
}


class TicketService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = TicketRepository(session)

    def create(self, payload: TicketCreate) -> Ticket:
        ticket = Ticket(title=payload.title, status=payload.status.value)
        return self._repo.add(ticket)

    def update_status(self, ticket_id: int, status: TicketStatus) -> Ticket | None:
        ticket = self._session.get(Ticket, ticket_id)
        if ticket is None:
            return None
        allowed = TRANSITIONS[ticket.status]
        if status.value not in allowed:
            raise HTTPException(status_code=409, detail="invalid status transition")
        ticket.status = status.value
        self._session.commit()
        return ticket
