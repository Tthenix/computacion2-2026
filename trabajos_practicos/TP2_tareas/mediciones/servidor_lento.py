"""Servidor de pruebas para la tarea `descargar` y la medición 1.

Simula "internet lento" de forma controlada: GET /lento?seg=N responde después
de N segundos. Corre como servicio aparte en docker-compose (puerto 8001).
Su especificación son los tests de tests/test_servidor_lento.py.
"""
import asyncio

from fastapi import FastAPI

app = FastAPI(title="Servidor lento")


@app.get("/lento")
async def lento(seg: float = 1.0):
    """Responde después de `seg` segundos, sin bloquear el event loop."""
    # asyncio.sleep cede el control: mientras este pedido espera, el loop
    # atiende a los demás. time.sleep dormiría el hilo único y los congelaría.
    await asyncio.sleep(seg)
    return {"durmio": seg}
