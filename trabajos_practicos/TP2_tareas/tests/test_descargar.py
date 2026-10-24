"""Tests de la tarea `descargar` (I/O-bound, httpx).

Qué se prueba (fase 4):
- Devuelve por cada URL: status, bytes y segundos.
- Es concurrente: N URLs lentas tardan ~lo de la más lenta, no la suma.
- Una URL que falla no tira abajo a las demás (queda con `error`).
- Cancelar (o vencer el timeout) a mitad de la descarga cancela TODOS los
  pedidos en vuelo: no queda ningún socket colgado.
- El cliente httpx es uno solo, compartido, y se cierra al detener.

Los pedidos no salen a internet: httpx permite enchufar un "transporte".
ASGITransport habla directo con servidor_lento (en memoria, mismo event loop);
MockTransport nos deja inventar respuestas y fallos.
"""
import asyncio
import time

import httpx
import pytest

from modelos import TareaNueva
from plataforma import Plataforma
from servidor_lento import app as app_lenta


def descargar(*urls, **extra):
    return TareaNueva(tipo="descargar", urls=list(urls), **extra)


async def hasta(condicion, limite=2.0):
    fin = time.perf_counter() + limite
    while not condicion():
        assert time.perf_counter() < fin, "la condición no se cumplió a tiempo"
        await asyncio.sleep(0.01)


@pytest.fixture
async def plat_lenta():
    p = Plataforma(n_workers=1, cola_max=10, transporte=httpx.ASGITransport(app=app_lenta))
    p.iniciar()
    yield p
    await p.detener()


def url(seg):
    return f"http://lento/lento?seg={seg}"


async def test_devuelve_status_bytes_y_segundos_por_url(plat_lenta):
    t = plat_lenta.crear(descargar(url(0.2), "http://lento/no_existe"))
    await hasta(lambda: t.estado == "completada")
    ok, mala = t.resultado
    assert ok["url"] == url(0.2) and ok["status"] == 200
    assert ok["bytes"] == len('{"durmio":0.2}') and ok["segundos"] >= 0.2
    assert mala["status"] == 404  # un 404 es una respuesta, no un fallo de red


async def test_es_concurrente_tarda_lo_de_la_mas_lenta(plat_lenta):
    t = plat_lenta.crear(descargar(*[url(0.3)] * 5))
    inicio = time.perf_counter()
    await hasta(lambda: t.estado == "completada")
    total = time.perf_counter() - inicio
    assert 0.3 <= total < 0.8  # secuencial serían 1.5 s


async def test_una_url_que_falla_no_tira_abajo_las_demas():
    def handler(request):
        if "mala" in str(request.url):
            raise httpx.ConnectError("sin red")
        return httpx.Response(200, content=b"hola")

    p = Plataforma(n_workers=1, cola_max=10, transporte=httpx.MockTransport(handler))
    p.iniciar()
    try:
        t = p.crear(descargar("http://x/buena", "http://x/mala", "http://x/buena2"))
        await hasta(lambda: t.estado == "completada")
        buena, mala, buena2 = t.resultado
        assert buena["status"] == 200 and buena2["bytes"] == 4
        assert "error" in mala and "status" not in mala
        assert "ConnectError" in mala["error"]
    finally:
        await p.detener()


def plataforma_con_pedidos_colgados(n_workers=1):
    """Plataforma cuyo servidor nunca responde; cuenta cuántos pedidos se cancelaron."""
    estado = {"en_vuelo": 0, "cancelados": 0}

    async def handler(request):
        estado["en_vuelo"] += 1
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            estado["cancelados"] += 1
            raise
        return httpx.Response(200)

    p = Plataforma(n_workers=n_workers, cola_max=10, transporte=httpx.MockTransport(handler))
    return p, estado


async def test_cancelar_a_mitad_cancela_todos_los_pedidos_en_vuelo():
    p, estado = plataforma_con_pedidos_colgados()
    p.iniciar()
    try:
        t = p.crear(descargar(*[f"http://x/{i}" for i in range(5)]))
        await hasta(lambda: estado["en_vuelo"] == 5)
        p.cancelar(t.id)
        await hasta(lambda: estado["cancelados"] == 5)
        await hasta(lambda: p.ocupados == 0)
        assert t.estado == "cancelada"
    finally:
        await p.detener()


async def test_el_timeout_tambien_cancela_los_pedidos_en_vuelo():
    p, estado = plataforma_con_pedidos_colgados()
    p.iniciar()
    try:
        t = p.crear(descargar(*[f"http://x/{i}" for i in range(3)], timeout=0.1))
        await hasta(lambda: t.estado == "fallida")
        await hasta(lambda: estado["cancelados"] == 3)
        assert "timeout" in t.error
    finally:
        await p.detener()


async def test_hay_un_solo_cliente_compartido_y_se_cierra_al_detener():
    p = Plataforma(n_workers=1, cola_max=10, transporte=httpx.ASGITransport(app=app_lenta))
    p.iniciar()
    cliente = p.cliente
    assert isinstance(cliente, httpx.AsyncClient) and not cliente.is_closed
    a = p.crear(descargar(url(0)))
    b = p.crear(descargar(url(0)))
    await hasta(lambda: a.estado == b.estado == "completada")
    assert p.cliente is cliente  # el mismo para las dos tareas
    await p.detener()
    assert cliente.is_closed
