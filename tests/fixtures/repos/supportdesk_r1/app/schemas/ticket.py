from enum import StrEnum

from pydantic import BaseModel


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class TicketCreate(BaseModel):
    title: str
    status: TicketStatus = TicketStatus.OPEN


class TicketRead(BaseModel):
    id: int
    title: str
    status: TicketStatus
