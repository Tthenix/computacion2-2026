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


# ---------- fase 3: cancelación y timeouts ----------

async def test_cancelar_una_ejecutando_la_corta_y_libera_al_worker():
    p = Plataforma(n_workers=1, cola_max=10)
    p.iniciar()
    try:
        larga = p.crear(esperar(30))
        siguiente = p.crear(esperar(0))
        await hasta(lambda: larga.estado == "ejecutando")
        inicio = time.perf_counter()
        assert p.cancelar(larga.id).estado == "cancelada"
        await hasta(lambda: p.ocupados == 0)
        assert time.perf_counter() - inicio < 1  # no esperó los 30 s
        assert larga.fin is not None and p.en_curso == {}
        await hasta(lambda: siguiente.estado == "completada")  # el worker sigue vivo
    finally:
        await p.detener()


async def test_timeout_deja_fallida_con_el_motivo(plat):
    t = plat.crear(TareaNueva(tipo="esperar", segundos=30, timeout=0.1))
    await hasta(lambda: t.estado == "fallida")
    assert t.error == "timeout tras 0.1s"
    await hasta(lambda: plat.ocupados == 0)
    assert plat.en_curso == {}


async def test_timeout_por_defecto_se_aplica_si_la_tarea_no_trae_el_suyo():
    p = Plataforma(n_workers=1, cola_max=10, timeout_default=0.1)
    p.iniciar()
    try:
        t = p.crear(esperar(30))
        await hasta(lambda: t.estado == "fallida")
        assert "timeout" in t.error
        # y el timeout propio gana al default
        u = p.crear(TareaNueva(tipo="esperar", segundos=0.3, timeout=5))
        await hasta(lambda: u.estado == "completada")
    finally:
        await p.detener()


async def test_no_se_puede_cancelar_una_ya_completada(plat):
    t = plat.crear(esperar(0))
    await hasta(lambda: t.estado == "completada")
    with pytest.raises(ValueError):
        plat.cancelar(t.id)
    assert t.estado == "completada"


async def test_cancelar_el_worker_en_el_apagado_no_se_confunde_con_cancelar_la_tarea():
    p = Plataforma(n_workers=1, cola_max=10)
    p.iniciar()
    t = p.crear(esperar(30))
    await hasta(lambda: t.estado == "ejecutando")
    workers = list(p._workers)
    await p.detener()
    # El worker terminó cancelado (la cancelación se propagó) y no dejó nada colgado.
    assert all(w.cancelled() for w in workers)
    assert t.estado == "cancelada"
    assert p.ocupados == 0 and p.en_curso == {}
