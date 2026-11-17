from fastapi import FastAPI

from app.api.escalate import router as escalate_router
from app.api.tickets import router as tickets_router

app = FastAPI(title="SupportDesk")
app.include_router(tickets_router)
app.include_router(escalate_router)
