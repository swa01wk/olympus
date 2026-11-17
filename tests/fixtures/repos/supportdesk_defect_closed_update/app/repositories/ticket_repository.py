from sqlalchemy.orm import Session

from app.models.ticket import Ticket


class TicketRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, ticket: Ticket) -> Ticket:
        self._session.add(ticket)
        self._session.commit()
        self._session.refresh(ticket)
        return ticket
