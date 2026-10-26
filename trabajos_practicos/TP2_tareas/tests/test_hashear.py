"""Tests de la tarea `hashear` (CPU-bound, ProcessPoolExecutor).

Qué se prueba (fase 5):
- `hash_bloque` es SHA-256 iterado, y hashear (por bloques) da lo mismo que
  hacerlo de una, incluso si N no es múltiplo del tamaño de bloque.
- Con executor el event loop sigue respondiendo mientras se calcula; con
  USAR_EXECUTOR=0 se congela (es la prueba de que asyncio no sirve para CPU).
- Cancelar o vencer el timeout corta el hash entre bloques: el proceso no queda
  quemando CPU y el pool queda libre para la tarea siguiente.
- El pool de procesos se cierra en detener().
"""
import asyncio
import hashlib
import time

import pytest

import tareas
from modelos import TareaNueva
from plataforma import Plataforma


def iterado(texto: bytes, n: int) -> bytes:
    h = texto
    for _ in range(n):
        h = hashlib.sha256(h).digest()
    return h


def hashear(texto="hola", iteraciones=1000, **extra):
    return TareaNueva(tipo="hashear", texto=texto, iteraciones=iteraciones, **extra)


async def hasta(condicion, limite=5.0):
    fin = time.perf_counter() + limite
    while not condicion():
        assert time.perf_counter() < fin, "la condición no se cumplió a tiempo"
        await asyncio.sleep(0.01)


@pytest.fixture
async def plat():
    p = Plataforma(n_workers=2, cola_max=10, procesos_hash=2)
    p.iniciar()
    yield p
    await p.detener()


# ---------- corrección ----------

def test_hash_bloque_es_sha256_iterado():
    assert tareas.hash_bloque(b"a", 1) == hashlib.sha256(b"a").digest()
    assert tareas.hash_bloque(b"a", 3) == iterado(b"a", 3)
    assert tareas.hash_bloque(b"a", 0) == b"a"


@pytest.mark.parametrize("n", [1, 500, 1000, 2503])  # 2503 no es múltiplo del bloque
async def test_hashear_por_bloques_da_lo_mismo_que_de_una(plat, monkeypatch, n):
    monkeypatch.setattr(tareas, "BLOQUE", 500)
    t = plat.crear(hashear("hola", n))
    await hasta(lambda: t.estado == "completada")
    assert t.resultado == {"hash": iterado(b"hola", n).hex(), "iteraciones": n}


# ---------- el event loop ----------

async def peor_atraso(plat, n):
    """Corre un hash de `n` vueltas y devuelve el peor atraso (s) de un latido de 10 ms."""
    t = plat.crear(hashear("x", n))
    peor = 0.0
    while t.estado not in ("completada", "fallida"):
        t0 = time.perf_counter()
        await asyncio.sleep(0.01)
        peor = max(peor, time.perf_counter() - t0 - 0.01)
    assert t.estado == "completada"
    return peor


def vueltas_para(segundos):
    """Cuántas vueltas son ~`segundos` de CPU en esta máquina."""
    t0 = time.perf_counter()
    tareas.hash_bloque(b"x", 200_000)
    return int(200_000 * segundos / (time.perf_counter() - t0))


async def test_con_executor_el_loop_sigue_respondiendo(plat):
    await peor_atraso(plat, 1000)  # calentamiento: el pool arranca sus procesos
    assert await peor_atraso(plat, vueltas_para(0.8)) < 0.15


async def test_sin_executor_el_loop_se_congela():
    p = Plataforma(n_workers=1, cola_max=10, usar_executor=False)
    p.iniciar()
    try:
        assert await peor_atraso(p, vueltas_para(0.8)) > 0.4
    finally:
        await p.detener()


# ---------- cancelación: el corte es entre bloques ----------

async def test_cancelar_un_hash_libera_el_pool_enseguida(monkeypatch):
    monkeypatch.setattr(tareas, "BLOQUE", 100_000)
    p = Plataforma(n_workers=2, cola_max=10, procesos_hash=1)  # UN solo proceso
    p.iniciar()
    try:
        enorme = p.crear(hashear("x", 10**10))  # horas de CPU si nadie lo corta
        await hasta(lambda: enorme.estado == "ejecutando")
        await asyncio.sleep(0.3)
        p.cancelar(enorme.id)
        await hasta(lambda: enorme.fin is not None, limite=1)
        # Si el proceso siguiera con el hash gigante, esta tarea nunca entraría.
        chica = p.crear(hashear("y", 1000))
        await hasta(lambda: chica.estado == "completada", limite=3)
        assert enorme.estado == "cancelada"
    finally:
        await p.detener()


async def test_el_timeout_corta_un_hash(monkeypatch):
    monkeypatch.setattr(tareas, "BLOQUE", 100_000)
    p = Plataforma(n_workers=1, cola_max=10, procesos_hash=1)
    p.iniciar()
    try:
        t = p.crear(hashear("x", 10**10, timeout=0.5))
        await hasta(lambda: t.estado == "fallida", limite=3)
        assert "timeout" in t.error
        chica = p.crear(hashear("y", 1000))
        await hasta(lambda: chica.estado == "completada", limite=3)
    finally:
        await p.detener()


# ---------- ciclo de vida ----------

async def test_detener_cierra_el_pool():
    p = Plataforma(n_workers=1, cola_max=10, procesos_hash=1)
    p.iniciar()
    pool = p.pool
    await p.detener()
    with pytest.raises(RuntimeError):
        pool.submit(int)  # un pool cerrado no acepta trabajo


async def test_usar_executor_apagado_no_crea_pool():
    p = Plataforma(n_workers=1, usar_executor=False)
    p.iniciar()
    assert p.pool is None
    await p.detener()
