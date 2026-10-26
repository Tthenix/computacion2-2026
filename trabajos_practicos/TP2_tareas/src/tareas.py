"""Lo que hace cada tipo de tarea. Un ejecutor es `async def f(tarea, plat) -> resultado`.

`plat` es la Plataforma: de ahí salen los recursos compartidos (el cliente httpx
de `descargar`; el pool de procesos de `hashear`).
"""
import asyncio
import hashlib
import time

import httpx

from modelos import Tarea

# Vueltas de SHA-256 por bloque (~0,1 s de CPU). Más chico: corta más fino pero
# paga más viajes de ida y vuelta al proceso hijo. Más grande: al revés.
BLOQUE = 250_000

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

def hash_bloque(h: bytes, n: int) -> bytes:
    """`n` vueltas de SHA-256 sobre `h`. CPU puro, sin estado y a nivel de módulo:
    tiene que ser picklable para viajar al proceso hijo (por nombre, `tareas.hash_bloque`)."""
    for _ in range(n):
        h = hashlib.sha256(h).digest()
    return h

async def hashear(tarea: Tarea, plat):
    """SHA-256 iterado, partido en bloques para poder cortarlo.

    Cada bloque va a un PROCESO aparte (`run_in_executor`): ahí no hay GIL compartido
    y el event loop sigue libre. Entre bloque y bloque hay un `await`, que es el único
    punto donde cancelar/timeout pueden entrar: `future.cancel()` no frena un bloque
    que ya está corriendo en el hijo (clase 22), así que el proceso nunca pierde más
    de UN bloque de CPU por un resultado que nadie va a leer.
    """
    loop = asyncio.get_running_loop()
    h = tarea.texto.encode()
    restantes = tarea.iteraciones
    while restantes > 0:
        n = min(BLOQUE, restantes)
        if plat.pool:
            h = await loop.run_in_executor(plat.pool, hash_bloque, h, n)
        else:
            # USAR_EXECUTOR=0: calcula EN el loop y lo congela, a propósito (medición 2).
            # Sin ningún await acá, ni DELETE ni el timeout pueden cortarlo.
            h = hash_bloque(h, n)
        restantes -= n
    return {"hash": h.hex(), "iteraciones": tarea.iteraciones}

# tipo → ejecutor. La plataforma busca acá; no sabe qué hace cada tarea.
EJECUTORES = {
    "esperar": esperar,
    "descargar": descargar,
    "hashear": hashear,
}
