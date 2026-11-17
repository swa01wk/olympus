import app.models.ticket  # noqa: F401
from app.db import Base, engine

Base.metadata.create_all(bind=engine)

from app.main import app
from fastapi.testclient import TestClient


def test_create_ticket() -> None:
    with TestClient(app) as client:
        response = client.post("/tickets", json={"title": "Help", "status": "OPEN"})
        assert response.status_code == 201
