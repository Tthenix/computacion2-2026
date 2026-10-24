"""Lo que hace cada tipo de tarea. Un ejecutor es `async def f(tarea, plat) -> resultado`.

`plat` es la Plataforma: de ahí salen los recursos compartidos (el cliente httpx
de `descargar`; en la fase 5, el pool de procesos de `hashear`).

`hashear` (fase 5) falla con NotImplementedError, y la plataforma lo deja
`fallida` con ese motivo.
"""
import asyncio
import time

import httpx

from modelos import Tarea


async def esperar(tarea: Tarea, plat):
    """Simula I/O: `asyncio.sleep` suspende ESTA corrutina; el loop sigue libre."""
    await asyncio.sleep(tarea.segundos)
    return {"durmio": tarea.segundos}


async def bajar_url(cliente: httpx.AsyncClient, url: str) -> dict:
    """Baja UNA url y mide cuánto tardó. Un fallo de red queda en el resultado.

    Solo atrapa httpx.HTTPError (conexión, timeout de httpx, URL inválida...):
    CancelledError no es HTTPError y sigue de largo, así cancelar funciona.
    Un 404 NO es un fallo: es una respuesta, se informa su status.
    """
    inicio = time.perf_counter()
    try:
        r = await cliente.get(url)
    except httpx.HTTPError as e:
        return {"url": url, "error": repr(e), "segundos": time.perf_counter() - inicio}
    return {
        "url": url,
        "status": r.status_code,
        "bytes": len(r.content),
        "segundos": time.perf_counter() - inicio,
    }


async def descargar(tarea: Tarea, plat):
    """Baja todas las URLs A LA VEZ: tarda lo de la más lenta, no la suma.

    Si cancelan la tarea (o vence el timeout), `gather` cancela a todos sus hijos
    y cada pedido en vuelo cierra su conexión.
    """
    return await asyncio.gather(*(bajar_url(plat.cliente, u) for u in tarea.urls))


async def sin_implementar(tarea: Tarea, plat):
    raise NotImplementedError(f"la tarea '{tarea.tipo}' llega en una fase posterior")


# tipo → ejecutor. La plataforma busca acá; no sabe qué hace cada tarea.
EJECUTORES = {
    "esperar": esperar,
    "descargar": descargar,
    "hashear": sin_implementar,
}
