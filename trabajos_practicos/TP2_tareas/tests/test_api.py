"""Tests de la API HTTP.

Qué se prueba:
- GET /salud responde: el servidor arranca y el event loop atiende pedidos.
- POST /tareas: 201, id, estado inicial `pendiente`, validación por tipo.
- GET /tareas: lista, filtro ?estado=, estado inválido → 422.
- GET /tareas/{id} y DELETE /tareas/{id}: 404 si no existe.
- GET /estadisticas: conteos por estado.
"""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def cliente():
    # Registro limpio por test: si no, el id y los conteos dependen del orden.
    # Sin workers: las tareas quedan `pendiente` y los tests son deterministas.
    main.plataforma.reiniciar()
    main.plataforma.n_workers = 0
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def cliente_con_workers():
    main.plataforma.reiniciar()
    main.plataforma.n_workers = 2
    with TestClient(main.app) as c:
        yield c


def crear(cliente, **cuerpo):
    cuerpo.setdefault("tipo", "esperar")
    if cuerpo["tipo"] == "esperar":
        cuerpo.setdefault("segundos", 1)
    return cliente.post("/tareas", json=cuerpo)


def test_salud_responde_ok(cliente):
    r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok"}


# ---------- POST /tareas ----------

def test_post_devuelve_201_con_id_y_estado_pendiente(cliente):
    r = crear(cliente)
    assert r.status_code == 201
    assert r.json()["id"] == 1
    assert r.json()["estado"] == "pendiente"
    assert r.json()["tipo"] == "esperar"


def test_post_asigna_ids_distintos_y_crecientes(cliente):
    assert crear(cliente).json()["id"] == 1
    assert crear(cliente).json()["id"] == 2


def test_post_tipo_desconocido_da_422(cliente):
    assert crear(cliente, tipo="volar").status_code == 422


def test_post_esperar_sin_segundos_da_422(cliente):
    r = cliente.post("/tareas", json={"tipo": "esperar"})
    assert r.status_code == 422


def test_post_hashear_valido_y_sin_iteraciones(cliente):
    ok = cliente.post("/tareas", json={"tipo": "hashear", "texto": "hola", "iteraciones": 1000})
    assert ok.status_code == 201
    mal = cliente.post("/tareas", json={"tipo": "hashear", "texto": "hola"})
    assert mal.status_code == 422


def test_post_descargar_exige_urls_no_vacias(cliente):
    ok = cliente.post("/tareas", json={"tipo": "descargar", "urls": ["http://x"]})
    assert ok.status_code == 201
    mal = cliente.post("/tareas", json={"tipo": "descargar", "urls": []})
    assert mal.status_code == 422


def test_post_segundos_negativos_da_422(cliente):
    assert crear(cliente, segundos=-1).status_code == 422


# ---------- GET /tareas/{id} ----------

def test_get_por_id_devuelve_la_tarea(cliente):
    crear(cliente, segundos=5)
    r = cliente.get("/tareas/1")
    assert r.status_code == 200
    assert r.json()["segundos"] == 5


def test_get_por_id_inexistente_da_404(cliente):
    assert cliente.get("/tareas/999").status_code == 404


# ---------- GET /tareas ----------

def test_listar_vacio(cliente):
    assert cliente.get("/tareas").json() == []


def test_listar_devuelve_todas(cliente):
    crear(cliente)
    crear(cliente)
    assert [t["id"] for t in cliente.get("/tareas").json()] == [1, 2]


def test_listar_filtra_por_estado(cliente):
    crear(cliente)
    crear(cliente)
    cliente.delete("/tareas/2")  # pendiente → cancelada
    pendientes = cliente.get("/tareas", params={"estado": "pendiente"}).json()
    canceladas = cliente.get("/tareas", params={"estado": "cancelada"}).json()
    assert [t["id"] for t in pendientes] == [1]
    assert [t["id"] for t in canceladas] == [2]


def test_listar_estado_invalido_da_422(cliente):
    assert cliente.get("/tareas", params={"estado": "dormida"}).status_code == 422


# ---------- DELETE /tareas/{id} ----------

def test_delete_pendiente_la_marca_cancelada(cliente):
    crear(cliente)
    r = cliente.delete("/tareas/1")
    assert r.status_code == 200
    assert r.json()["estado"] == "cancelada"
    assert cliente.get("/tareas/1").json()["estado"] == "cancelada"


def test_delete_inexistente_da_404(cliente):
    assert cliente.delete("/tareas/999").status_code == 404


def test_delete_ya_cancelada_da_409(cliente):
    crear(cliente)
    cliente.delete("/tareas/1")
    assert cliente.delete("/tareas/1").status_code == 409


# ---------- GET /estadisticas ----------

def test_estadisticas_sin_tareas_todo_en_cero(cliente):
    r = cliente.get("/estadisticas").json()
    assert r["por_estado"] == {
        "pendiente": 0, "ejecutando": 0, "completada": 0, "fallida": 0, "cancelada": 0,
    }


def test_estadisticas_cuenta_por_estado(cliente):
    for _ in range(3):
        crear(cliente)
    cliente.delete("/tareas/3")
    r = cliente.get("/estadisticas").json()
    assert r["por_estado"]["pendiente"] == 2
    assert r["por_estado"]["cancelada"] == 1


# ---------- fase 2: cola + workers ----------

def test_post_con_cola_llena_da_503(cliente):
    main.plataforma.cola_max = 1
    try:
        main.plataforma.reiniciar()
        with TestClient(main.app) as c:  # relanza el lifespan con cola de 1
            assert crear(c).status_code == 201
            r = crear(c)
            assert r.status_code == 503
            assert len(c.get("/tareas").json()) == 1  # la rechazada no se registró
    finally:
        main.plataforma.cola_max = 100


def test_la_tarea_se_ejecuta_sola_hasta_completada(cliente_con_workers):
    import time
    c = cliente_con_workers
    id = crear(c, segundos=0.1).json()["id"]
    fin = time.perf_counter() + 2
    while c.get(f"/tareas/{id}").json()["estado"] != "completada":
        assert time.perf_counter() < fin
        time.sleep(0.02)
    assert c.get(f"/tareas/{id}").json()["resultado"] == {"durmio": 0.1}


def test_estadisticas_incluyen_workers_y_ocupados(cliente_con_workers):
    r = cliente_con_workers.get("/estadisticas").json()
    assert r["workers"] == 2
    assert r["ocupados"] == 0
