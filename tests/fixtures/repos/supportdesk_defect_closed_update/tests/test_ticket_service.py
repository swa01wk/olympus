import app.models.ticket  # noqa: F401
from app.db import Base, SessionLocal, engine
from app.schemas.ticket import TicketCreate, TicketStatus
from app.services.ticket_service import TicketService

Base.metadata.create_all(bind=engine)


def test_update_status() -> None:
    db = SessionLocal()
    service = TicketService(db)
    created = service.create(TicketCreate(title="x", status=TicketStatus.OPEN))
    updated = service.update_status(created.id, TicketStatus.CLOSED)
    assert updated is not None
    assert updated.status == "CLOSED"
