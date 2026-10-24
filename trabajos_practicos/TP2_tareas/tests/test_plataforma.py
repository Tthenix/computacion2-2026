"""Tests de la Plataforma (cola + pool de workers), sin pasar por HTTP.

Qué se prueba (fase 2):
- Una tarea `esperar` recorre pendiente → ejecutando → completada.
- Con N workers corren N tareas a la vez; el resto espera en la cola.
- Una excepción en una tarea la deja `fallida` y el worker sigue vivo.
- Un worker saltea las tareas canceladas mientras estaban en la cola.
- Cola llena → ColaLlena (el POST lo traduce a 503) y la tarea no se registra.
- `ocupados` vuelve a 0 y las estadísticas informan workers y tiempos.
"""
import asyncio
import time

import pytest

import tareas
from modelos import TareaNueva
from plataforma import ColaLlena, Plataforma


def esperar(segundos):
    return TareaNueva(tipo="esperar", segundos=segundos)


async def hasta(condicion, limite=2.0):
    """Espera (cediendo el loop) a que `condicion()` sea verdadera."""
    fin = time.perf_counter() + limite
    while not condicion():
        assert time.perf_counter() < fin, "la condición no se cumplió a tiempo"
        await asyncio.sleep(0.01)


@pytest.fixture
async def plat():
    p = Plataforma(n_workers=2, cola_max=10)
    p.iniciar()
    yield p
    await p.detener()


async def test_esperar_pasa_por_los_tres_estados(plat):
    t = plat.crear(esperar(0.2))
    assert t.estado == "pendiente"
    await hasta(lambda: t.estado == "ejecutando")
    await hasta(lambda: t.estado == "completada")
    assert t.resultado == {"durmio": 0.2}
    assert t.creada <= t.inicio <= t.fin
    assert t.fin - t.inicio >= 0.2


async def test_con_dos_workers_corren_dos_y_el_resto_espera(plat):
    todas = [plat.crear(esperar(0.2)) for _ in range(4)]
    await hasta(lambda: plat.ocupados == 2)
    assert sorted(t.estado for t in todas) == ["ejecutando", "ejecutando", "pendiente", "pendiente"]
    inicio = time.perf_counter()
    await hasta(lambda: all(t.estado == "completada" for t in todas))
    # Las 2 de la segunda tanda arrancaron recién al liberarse un worker.
    assert time.perf_counter() - inicio >= 0.15


async def test_una_excepcion_deja_fallida_y_el_worker_sigue(monkeypatch):
    async def rota(tarea):
        raise RuntimeError("boom")

    p = Plataforma(n_workers=1, cola_max=10)
    p.iniciar()
    try:
        monkeypatch.setitem(tareas.EJECUTORES, "esperar", rota)
        mala = p.crear(esperar(0))
        await hasta(lambda: mala.estado == "fallida")
        assert "boom" in mala.error
        monkeypatch.undo()
        buena = p.crear(esperar(0))
        await hasta(lambda: buena.estado == "completada")  # el único worker sobrevivió
        assert p.ocupados == 0
    finally:
        await p.detener()


async def test_el_worker_saltea_las_canceladas_en_cola():
    p = Plataforma(n_workers=1, cola_max=10)
    p.iniciar()
    try:
        a = p.crear(esperar(0.2))
        b = p.crear(esperar(0.2))
        c = p.crear(esperar(0))
        await hasta(lambda: a.estado == "ejecutando")
        p.cancelar(b.id)
        await hasta(lambda: c.estado == "completada")
        assert b.estado == "cancelada"
        assert b.inicio is None  # nunca se ejecutó
    finally:
        await p.detener()


async def test_cola_llena_levanta_colallena_y_no_registra():
    p = Plataforma(n_workers=0, cola_max=2)  # sin workers nadie vacía la cola
    p.iniciar()
    try:
        p.crear(esperar(1))
        p.crear(esperar(1))
        with pytest.raises(ColaLlena):
            p.crear(esperar(1))
        assert len(p.tareas) == 2
    finally:
        await p.detener()


async def test_estadisticas_informan_workers_ocupados_y_tiempos(plat):
    e = plat.estadisticas()
    assert e["workers"] == 2 and e["ocupados"] == 0 and e["en_cola"] == 0
    assert e["tiempo_promedio_ejecucion"] is None  # todavía no terminó ninguna
    t = plat.crear(esperar(0.2))
    await hasta(lambda: plat.ocupados == 1)
    assert plat.estadisticas()["ocupados"] == 1
    await hasta(lambda: t.estado == "completada")
    e = plat.estadisticas()
    assert e["ocupados"] == 0
    assert e["tiempo_promedio_ejecucion"] >= 0.2
    assert e["tiempo_promedio_espera"] >= 0


async def test_detener_cancela_los_workers():
    p = Plataforma(n_workers=3, cola_max=10)
    p.iniciar()
    workers = list(p._workers)
    await p.detener()
    assert all(w.done() for w in workers)
