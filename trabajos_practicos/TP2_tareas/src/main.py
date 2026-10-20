"""Plataforma de tareas distribuidas: punto de entrada de la API.

Fase 0: solo la prueba de vida. En las fases siguientes se suman los
endpoints de /tareas, el lifespan (cola + workers + executor) y el apagado
ordenado.
"""
import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Plataforma de tareas")


@app.get("/salud")
async def salud():
    """Prueba de vida: si responde, el event loop está vivo y atendiendo."""
    return {"estado": "ok"}


# La guarda importa: en la fase 5 el ProcessPoolExecutor arranca procesos
# hijos en modo spawn, y cada hijo RE-IMPORTA este módulo. Sin la guarda,
# cada hijo levantaría otro servidor más.
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
