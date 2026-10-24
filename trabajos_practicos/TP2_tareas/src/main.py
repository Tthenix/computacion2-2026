"""Plataforma de tareas distribuidas: punto de entrada de la API.

Fase 1: endpoints con el registro en memoria (todavía no se ejecuta nada).
Después: lifespan (cola + workers + executor) y apagado ordenado.
"""
import uvicorn
from fastapi import FastAPI, HTTPException

from modelos import Estado, Tarea, TareaNueva
from plataforma import Plataforma

app = FastAPI(title="Plataforma de tareas")
plataforma = Plataforma()


@app.get("/salud")
async def salud():
    """Prueba de vida: si responde, el event loop está vivo y atendiendo."""
    return {"estado": "ok"}


@app.post("/tareas", response_model=Tarea, status_code=201)
async def crear(nueva: TareaNueva):
    """Registra la tarea y responde ya (201 Created); no espera a que termine."""
    return plataforma.crear(nueva)


@app.get("/tareas", response_model=list[Tarea])
async def listar(estado: Estado | None = None):
    """Lista las tareas; `?estado=` filtra. Un estado inválido da 422 solo."""
    return plataforma.listar(estado)


@app.get("/tareas/{id}", response_model=Tarea)
async def obtener(id: int):
    tarea = plataforma.obtener(id)
    if tarea is None:
        raise HTTPException(404, f"no existe la tarea {id}")
    return tarea


@app.delete("/tareas/{id}", response_model=Tarea)
async def cancelar(id: int):
    try:
        tarea = plataforma.cancelar(id)
    except ValueError as e:
        raise HTTPException(409, str(e))  # 409 Conflict: el estado actual no lo permite
    if tarea is None:
        raise HTTPException(404, f"no existe la tarea {id}")
    return tarea


@app.get("/estadisticas")
async def estadisticas():
    return plataforma.estadisticas()


# La guarda importa: en la fase 5 el ProcessPoolExecutor arranca procesos
# hijos en modo spawn, y cada hijo RE-IMPORTA este módulo. Sin la guarda,
# cada hijo levantaría otro servidor más.
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
