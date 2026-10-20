"""Tests de la API HTTP.

Qué se prueba (fase 0):
- GET /salud responde: el servidor arranca y el event loop atiende pedidos.
"""
from fastapi.testclient import TestClient

from main import app


def test_salud_responde_ok():
    # TestClient habla HTTP con la app en memoria, sin levantar uvicorn.
    with TestClient(app) as cliente:
        r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok"}
