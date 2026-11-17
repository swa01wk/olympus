from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import SessionLocal

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{ticket_id}/escalate", status_code=202)
def escalate_ticket(ticket_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return {"ticket_id": ticket_id, "escalated": True}
