"""Tests del servidor lento (mediciones/servidor_lento.py).

Qué se prueba:
- Tarda lo que le pedimos (?seg=0.3 → al menos 0.3 s) y lo informa.
- Con seg=0 responde enseguida.
- Varios pedidos simultáneos esperan EN PARALELO: 5 pedidos de 0.3 s tardan
  ~0.3 s en total, no 1.5 s. Con time.sleep dentro de un `async def` este
  test falla: el event loop queda congelado y los atiende de a uno.
"""
import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from servidor_lento import app


def test_tarda_lo_pedido():
    with TestClient(app) as cliente:
        inicio = time.perf_counter()
        r = cliente.get("/lento", params={"seg": 0.3})
        duracion = time.perf_counter() - inicio
    assert r.status_code == 200
    assert r.json() == {"durmio": 0.3}
    assert duracion >= 0.3


def test_con_cero_responde_enseguida():
    with TestClient(app) as cliente:
        inicio = time.perf_counter()
        r = cliente.get("/lento", params={"seg": 0})
        duracion = time.perf_counter() - inicio
    assert r.json() == {"durmio": 0}
    assert duracion < 0.2


@pytest.mark.asyncio
async def test_pedidos_simultaneos_no_se_bloquean():
    # ASGITransport conecta el cliente async directo a la app, en el MISMO
    # event loop del test: si la app bloquea el loop, se nota en el tiempo.
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://test") as cliente:
        inicio = time.perf_counter()
        respuestas = await asyncio.gather(
            *(cliente.get("/lento", params={"seg": 0.3}) for _ in range(5))
        )
        duracion = time.perf_counter() - inicio
    assert all(r.status_code == 200 for r in respuestas)
    # Concurrente: ~0.3 s. Secuencial (loop bloqueado): ~1.5 s.
    assert duracion < 0.6
