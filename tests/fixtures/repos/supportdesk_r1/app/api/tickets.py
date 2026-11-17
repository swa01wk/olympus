from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.schemas.ticket import TicketCreate, TicketRead
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=TicketRead, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketRead:
    service = TicketService(db)
    ticket = service.create(payload)
    return TicketRead(id=ticket.id, title=ticket.title, status=ticket.status)
