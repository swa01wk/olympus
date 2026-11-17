from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketCreate, TicketStatus


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
        ticket.status = status.value
        self._session.commit()
        return ticket
