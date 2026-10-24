"""Lo que hace cada tipo de tarea. Un ejecutor es `async def f(tarea) -> resultado`.

Fase 2: solo `esperar`. `descargar` (fase 4) y `hashear` (fase 5) fallan con
NotImplementedError, y la plataforma los deja `fallida` con ese motivo.
"""
import asyncio

from modelos import Tarea


async def esperar(tarea: Tarea):
    """Simula I/O: `asyncio.sleep` suspende ESTA corrutina; el loop sigue libre."""
    await asyncio.sleep(tarea.segundos)
    return {"durmio": tarea.segundos}


async def sin_implementar(tarea: Tarea):
    raise NotImplementedError(f"la tarea '{tarea.tipo}' llega en una fase posterior")


# tipo → ejecutor. La plataforma busca acá; no sabe qué hace cada tarea.
EJECUTORES = {
    "esperar": esperar,
    "descargar": sin_implementar,
    "hashear": sin_implementar,
}
