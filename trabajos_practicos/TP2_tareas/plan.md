# Plan de desarrollo — TP2 Plataforma de tareas distribuidas

> Archivo de continuidad: si se corta la sesión, pegale esto a la IA.

## Cómo trabajamos (reglas fijas)

- **Modo mixto guiado**: la IA escribe esqueleto y partes repetitivas, muy comentadas; cada fase
  tiene una **pieza tuya** que escribe el alumno, guiado. Si no hay tiempo o algo no cierra →
  "la IA escribe, el alumno estudia".
- **TDD**: primero el test que falla (RED), después el código mínimo (GREEN). Los tests de cada
  pieza son su especificación.
- **Nada está hecho hasta verificarlo en Docker** (tests + prueba manual con curl).
- **Una fase a la vez.** Al cerrar: `estudio/fase_N.md` (ignorado por git) + esta tabla +
  mensaje de commit sugerido → commitea el alumno.

## Progreso

| Fase | Qué es | Estado |
|---|---|---|
| 0 | Mapa mental + setup Docker | ✅ 20/10: 4/4 tests en Docker; `api` (8000) y `lento` (8001) responden desde el host; dependencias fijadas |
| 1 | API con estado en memoria | ✅ 24/10: 22/22 tests en Docker + prueba con curl; DELETE solo cancela `pendiente` (fase 3 suma `ejecutando`) |
| 2 | Cola + pool de workers (`esperar`) | ✅ 24/10: 32/32 tests en Docker; 4 tareas × 3 s con 2 workers → 2 ejecutan, 2 esperan, total ~6 s; 503 con cola llena |
| 3 | Cancelación y timeouts | ✅ 24/10: 40/40 tests en Docker; DELETE corta un `esperar 30` a mitad; timeout → `fallida` con motivo; `ocupados` vuelve a 0 |
| 4 | `descargar` (I/O-bound, httpx) | ✅ 24/10: 46/46 tests en Docker; 20 URLs × 1 s contra `lento` tardan 1,10 s; URL mala no tira a las demás; cancelar libera todo |
| 5 | `hashear` (CPU-bound, executor) | ⬜ |
| 6 | Apagado ordenado + volcado JSON | ⬜ |
| 7 | Las 3 mediciones | ⬜ |
| 8 | Bonus: WebSocket `/eventos` + tests | ⬜ |
| 9 | README + guía de defensa | ⬜ |

## Cómo probar

```bash
# tests (reconstruye la imagen si cambió algo)
docker compose run --rm --build api pytest -v

# levantar todo y probar desde el host
docker compose up --build
curl.exe localhost:8000/salud                 # PowerShell: curl.exe, no curl
curl.exe "localhost:8001/lento?seg=1"
```

## Próximo paso concreto

**Fase 5: `hashear` (CPU-bound + executor).** Antes, repasar con el alumno `estudio/fase_4.md` §8 (autoevaluación). Contexto previo (fase 0):
pregunta 1 de `estudio/fase_0.md` §9 ("¿quién duerme durante un `await asyncio.sleep`?"): en la
fase 0 la respondió mal, y es la base de todo lo que sigue.
**No empezar fase nueva sin pedido explícito.**

---


## Contexto

Hay que entregar el TP2 (`trabajos_practicos/TP2_tareas/consigna.md`) el **03/11/2026**. Hoy es 20/10, así que quedan 14 días y ya vamos una semana atrás del cronograma sugerido. El sistema es una API FastAPI que encola tareas en una `asyncio.Queue`. Las consume un pool de N corrutinas, que mandan el trabajo CPU-bound a un executor. Tiene que soportar cancelación, timeouts y un apagado ordenado que vuelque el estado a JSON, correr en Docker y venir con 3 mediciones y un README argumentado.

El alumno no siguió bien la materia y en la defensa le preguntan sobre **su** código. Por eso el plan separa el trabajo en fases con objetivos verificables. Cada fase cierra con un md de estudio **no trackeado por git**.

### Decisiones tomadas con el usuario
- **Modo mixto guiado.** Yo escribo el esqueleto y lo repetitivo, muy comentado. En cada fase hay una "pieza tuya" que escribís vos con mi guía. Si no hay tiempo o algo no se entiende, paso a "yo escribo, vos estudiás".
- **Un md de estudio por fase**, en `estudio/` (ignorado por git), más una `guia_defensa.md` consolidada al final.
- **Bonus:** tests con `pytest-asyncio` y WebSocket `/eventos`.
- **Todo se corre en Docker.** El host es Windows, donde no existe `add_signal_handler`; además, Python no está en el PATH de Git Bash.
- **URLs de prueba:** un servidor lento local, como segundo servicio de compose, más una corrida contra internet real para comparar.
- **Commits:** los hacés vos al cerrar cada fase. Yo te dejo el mensaje sugerido.
- **No uso OpenSpec ni subagentes para el código.** El modo tutor necesita que el hilo sea interactivo, y en el TP1 tampoco se usó OpenSpec. La continuidad entre sesiones queda en `plan.md` (trackeado, como en el TP1). Engram no conecta en esta sesión.

## Material del repo que se reutiliza (no reinventar)

| Pieza TP2 | Fuente |
|---|---|
| Arquitectura completa + esqueleto lifespan | `clase_21_asyncio_avanzado/contenido.md` §"Juntando todo: la arquitectura del TP2"; `ejercicios.md` Ej.5 |
| Worker / centinela / `task_done` | `clase_21_asyncio_avanzado/cola.py` (`worker`, `worker_con_centinela`, `reparto`) |
| Hash iterado + medidor de lag del loop | `clase_21_asyncio_avanzado/executor.py` (`hashear`, `medidor`, `medir`, `con_proceso`) |
| Modelos + endpoints | `clase_19_http_fastapi/api.py` (`TareaNueva`, `Tarea`, `listar/crear/obtener/borrar`) |
| Medición con carga concurrente | `clase_19_http_fastapi/medir.py` (`medir()` con httpx + gather) |
| Descargas secuencial/concurrente, timeout, cancelación | `clase_20_asyncio_red/descargas.py` (`secuencial`, `concurrente`, `con_timeout`, `demostrar_cancelacion`, versión httpx comentada) |
| Contador sin lock / apagado ordenado | `clase_20_asyncio_red/eco_async.py` (`manejar`, `servidor`) |
| Futures: `cancel()` no frena un proceso ya corriendo | `clase_22_concurrent_futures/futuros.py` (`cancelar`, `con_timeout`) |
| Productor-consumidor con threads (contraste) | `clase_11_sincronizacion_1/contenido.md` §Buffer acotado |
| Plantilla Docker | `trabajos_practicos/TP1_monitoreo/{Dockerfile,docker-compose.yml,.gitignore,.dockerignore}` |

Cliente HTTP: **httpx**, porque es el que usa el curso, sirve para los tests (`ASGITransport`/`TestClient`) y para las mediciones.

## Estructura final

```
trabajos_practicos/TP2_tareas/
├── consigna.md                 (ya existe)
├── plan.md                     trackeado: este plan + tabla de progreso
├── README.md                   informe (central en la nota)
├── dudas.md                    opcional
├── Dockerfile  docker-compose.yml  requirements.txt  .gitignore  .dockerignore
├── src/
│   ├── main.py        FastAPI: endpoints, lifespan, WebSocket, config por env, guarda __main__
│   ├── modelos.py     Pydantic: Estado, TareaNueva, Tarea
│   ├── plataforma.py  registro (dict) + cola + workers + cancelar + estadísticas + volcado
│   └── tareas.py      esperar / descargar / hashear (+ hash_bloque para el pool)
├── mediciones/        servidor_lento.py, medir_io.py, medir_loop.py, medir_techo.py
├── tests/             test_api.py, test_plataforma.py, test_tareas.py (pytest-asyncio)
├── datos/             (ignorado) estado_<timestamp>.json
└── estudio/           (ignorado) fase_0.md … fase_9.md + guia_defensa.md
```

Estilo, igual que en el TP1: identificadores y comentarios en español, docstring por módulo y función, comentarios que expliquen el *por qué* y archivos de menos de 300 líneas. Tests con TDD estricto: primero el test que falla, después el código mínimo. Los tests además sirven como especificación legible.

## Decisiones de diseño clave (se justifican en el README y en los md)

1. **Cancelar una tarea sin matar al worker.** Cada tarea corre como su propio `asyncio.Task`, guardado en `en_curso[id]`. `DELETE` le hace `.cancel()` a ese Task. El worker distingue "cancelaron mi tarea" de "me cancelaron a mí", que pasa en el apagado. Si la tarea estaba pendiente, se marca `cancelada` y el worker la saltea cuando la saca de la cola.
2. **Timeout:** `async with asyncio.timeout(t.timeout)` dentro de la ejecución. `TimeoutError` → `fallida`, con "timeout tras Xs" como motivo.
3. **Excepción en una tarea:** `try/except Exception` alrededor de cada tarea → `fallida` con `repr(e)`. El worker sobrevive. `CancelledError` siempre se re-lanza y se libera en `finally`, con `task_done()` y `ocupados -= 1`.
4. **Hash cancelable.** `hashear` corre en un `ProcessPoolExecutor`, por **bloques**: `run_in_executor(pool, hash_bloque, h, BLOQUE)` en un loop. Así la cancelación o el timeout cortan entre bloques y el proceso no queda quemando CPU con un resultado que nadie va a leer. Lo vemos en clase 22: `future.cancel()` no detiene un proceso que ya arrancó. El pool usa `mp_context=spawn`, igual en todas las plataformas, y por eso la guarda `if __name__ == '__main__'` es necesaria de verdad.
5. **Flag `USAR_EXECUTOR=0`:** llama `hash_bloque` directo dentro de la corrutina y bloquea el loop a propósito. Sirve solo para la medición 2.
6. **Cola acotada (`COLA_MAX`).** El POST usa `put_nowait`, y si salta `QueueFull` responde **503** "cola llena". Esto contesta "¿qué se rompe con 10.000 tareas?".
7. **Señales:** uvicorn ya captura SIGINT/SIGTERM, deja de aceptar conexiones y después corre el *shutdown* del `lifespan`. Ese es nuestro gancho: marcamos `aceptando=False` (el POST devuelve 503), esperamos a las tareas en curso con un límite (`ESPERA_APAGADO`, usando `asyncio.wait`), cancelamos el resto, cancelamos los workers, cerramos el `httpx.AsyncClient` y el pool, y volcamos `datos/estado_<ts>.json`. En Docker: `CMD` en forma exec, para que Python sea PID 1 y reciba SIGTERM, y `stop_grace_period` mayor que `ESPERA_APAGADO`.
8. **Sin Lock:** un solo hilo, y el loop solo cambia de corrutina en los `await`. Ninguna sección "leer-modificar-escribir" del registro tiene un `await` en el medio. Esa regla se respeta a propósito y se documenta.
9. **Config por variables de entorno en compose:** `WORKERS`, `COLA_MAX`, `TIMEOUT_DEFAULT`, `USAR_EXECUTOR`, `PROCESOS_HASH`, `ESPERA_APAGADO`.

## Fases

Cada fase sigue el mismo ciclo: **test que falla → código → verificado en Docker → `estudio/fase_N.md` → actualizar la tabla de progreso en `plan.md` → mensaje de commit sugerido → commiteás vos**.

### Fase 0: Mapa mental + setup (20–21/10)
- **Objetivo:** `docker compose up --build` levanta `api` (con `GET /salud`) y `lento` (con `GET /lento?seg=1`), y las dos responden desde el host.
- **Hacer:** Dockerfile (`python:3.12-slim`), compose con los 2 servicios (el volumen `./datos` y `stop_grace_period` pasaron a la fase 6), `requirements.txt` con versiones exactas, `.gitignore` (`estudio/`, `datos/`), `.dockerignore`, `plan.md`, `mediciones/servidor_lento.py`, y un test trivial que corra con `docker compose run --rm api pytest`.
- **Pieza tuya:** escribir `servidor_lento.py`, unas 10 líneas con `asyncio.sleep`.
- **Estudio (`fase_0.md`):** el panorama completo explicado desde cero. Qué es el event loop, viniendo de `select` en la clase 17. Generador → corrutina (clase 18). `await` y Task. I/O-bound vs CPU-bound. GIL. Por qué asyncio no sirve para CPU. Un mapa de qué clase cubre cada pieza del TP2.

### Fase 1: API con estado en memoria, sin ejecutar nada (21–22/10)
- **Objetivo:** los 5 endpoints responden con datos reales del registro. El POST devuelve 201 con `id` y estado `pendiente`. GET acepta `?estado=`. Los 404 son correctos. `/estadisticas` devuelve conteos.
- **Hacer:** `modelos.py`, el registro en `plataforma.py`, los endpoints en `main.py` y `test_api.py`.
- **Pieza tuya:** `GET /tareas` con el filtro por estado.
- **Estudio:** HTTP (métodos y códigos), FastAPI + Pydantic, `async def` vs `def` en FastAPI, dónde corre el event loop (uvicorn).

### Fase 2: Cola + pool de workers, con la tarea `esperar` (22–24/10)
- **Objetivo:** `POST esperar 3s` → `pendiente` → `ejecutando` → `completada`. Con N=2 y 4 tareas, se ve la cola trabajando. Si una tarea lanza una excepción, no mata al worker. `/estadisticas` muestra los workers ocupados y los tiempos promedio.
- **Hacer:** `asyncio.Queue(maxsize)`, los N workers creados en el `lifespan`, transiciones de estado, timestamps, el 503 por cola llena y `test_plataforma.py`.
- **Pieza tuya:** el loop `while True` del worker (get → ejecutar → `finally task_done`), guiado.
- **Estudio:** productor-consumidor (clase 11 vs ahora). `asyncio.Queue` vs `queue.Queue`. Por qué no hace falta Lock. Backpressure. `gather` vs un `for` con `await`.

### Fase 3: Cancelación y timeouts (24–25/10)
- **Objetivo:** `DELETE` cancela tanto una tarea pendiente como una en ejecución (un `esperar 30` a la mitad). El timeout vence → `fallida`, con el motivo. Ningún worker se pierde y `ocupados` vuelve a 0.
- **Hacer:** Task por tarea, `en_curso`, distinguir los dos tipos de cancelación, `asyncio.timeout` y tests de cancelación a mitad de ejecución y de timeout.
- **Pieza tuya:** el branch del timeout (`except TimeoutError` → `fallida`).
- **Estudio:** cómo funciona `CancelledError` por dentro. Por qué se re-lanza. `finally` como liberador de recursos. Corrutinas huérfanas. `Task.cancelling()`.

### Fase 4: `descargar` de verdad, I/O-bound (25–27/10)
- **Objetivo:** una tarea con 20 URLs al servidor lento tarda lo mismo que la más lenta, no la suma. Por cada URL devuelve `status`, `bytes` y `segundos`. Si una URL falla, no tira abajo las demás. Cancelar a mitad de la descarga cierra las conexiones.
- **Hacer:** un `httpx.AsyncClient` compartido, creado y cerrado en el `lifespan`, y `gather` con try por URL.
- **Pieza tuya:** la función que baja una URL y mide su tiempo.
- **Estudio:** httpx vs aiohttp vs requests. Por qué un cliente compartido (pool de conexiones). `gather` y `return_exceptions`. Qué pasa con un socket a medio leer cuando se cancela.

### Fase 5: `hashear`, CPU-bound + executor (27–28/10)
- **Objetivo:** mientras corre un hash pesado, `GET /tareas` responde en ms. Con `USAR_EXECUTOR=0` se congela, como prueba manual. Cancelar o hacer timeout de un hash lo corta en menos de 1 bloque.
- **Hacer:** `ProcessPoolExecutor(spawn)` en el `lifespan`, `hash_bloque` en `tareas.py` (picklable) y el flag.
- **Pieza tuya:** la línea `run_in_executor` y medir vos el lag con y sin ella.
- **Estudio:** GIL. Threads vs procesos para CPU. fork vs spawn y la guarda `__main__`. Pickling. Por qué el hash va por bloques.

### Fase 6: Apagado ordenado + volcado (28–29/10)
- **Objetivo:** `docker compose stop` con tareas en curso → espera hasta el límite, cancela el resto, deja `datos/estado_<ts>.json`. Al volver a levantar, el log reporta el volcado previo. Ctrl+C (SIGINT) hace lo mismo.
- **Hacer:** el shutdown del `lifespan`, `aceptando=False`, `asyncio.wait(timeout)`, el volcado a JSON y la lectura del último volcado al arrancar.
- **Pieza tuya:** la función que vuelca el estado a JSON.
- **Estudio:** señales (de la clase 05 a uvicorn), PID 1 en Docker, forma exec vs shell del `CMD`, `stop_grace_period`, lifespan.

### Fase 7: Las 3 mediciones (30–31/10)
- **Objetivo:** números propios, cargados en tablas.
  1. `medir_io.py`: 20 descargas secuenciales vs 20 concurrentes contra `lento` (+1 corrida a internet), con el speedup.
  2. `medir_loop.py`: latencia de `GET /tareas` durante un hash pesado, con y sin executor.
  3. `medir_techo.py`: subir K tareas concurrentes (1 → 1000+) con N workers y ver dónde se degrada y por qué (workers, cola, CPU del loop, procesos del pool).
- **Pieza tuya:** correr las mediciones y escribir vos la interpretación. Yo la reviso.
- **Estudio:** cómo medir bien (warm-up, varias corridas, mediana) y cómo se lee cada resultado.

### Fase 8: Bonus (31/10–01/11)
- **WebSocket `/eventos`:** cada cliente tiene una `asyncio.Queue` acotada y la plataforma publica cada cambio de estado. Un cliente lento descarta eventos y no frena al resto.
- **Tests:** completar la suite de pytest-asyncio, sobre todo cancelación, timeout y apagado.
- **Estudio:** WebSocket vs polling, fan-out, por qué la cola por cliente.

### Fase 9: README + defensa (01–02/11; el 03/11 queda de colchón)
- README con las 7 secciones que pide la consigna: uso con `curl`, diagrama, las 4 decisiones argumentadas, las mediciones, la relación con las clases, las limitaciones y lo aprendido. **"Lo que aprendiste" lo escribís vos.**
- `dudas.md`. `estudio/guia_defensa.md`: las 6 preguntas de corrección con respuesta corta y larga, más "dónde podría bloquearse mi loop", señalando archivo:línea.

## Formato de cada `estudio/fase_N.md`

1. **Qué funciona al terminar la fase.**
2. **Conceptos desde cero**, con la ruta a la clase del repo que lo cubre (por ejemplo `clase_21_asyncio_avanzado/contenido.md §Queue`).
3. **Recorrido del código**, archivo:línea, explicando el por qué.
4. **Tu pieza:** qué escribiste, una versión de referencia comentada y en qué difiere.
5. **Cómo lo probé:** comandos + salida esperada.
6. **Preguntas de defensa** de esta fase, con respuesta de bolsillo y respuesta a fondo.
7. **Trampas comunes.**
8. **Autoevaluación:** 5 preguntas, con las respuestas al final, y qué preguntas de `clase_XX/autoevaluacion.md` repasar.

## Verificación

- Por fase: `docker compose run --rm api pytest -v` en verde, y después la prueba manual con `curl` desde el host contra `localhost:8000`, que queda descrita en el md de la fase.
- Al final, de punta a punta: clonar limpio → `docker compose up --build` → crear las 3 clases de tarea con `curl` → cancelar una en ejecución → verificar estados y `/estadisticas` → `docker compose stop` con una tarea en curso → existe `datos/estado_*.json` → `up` de nuevo → el log reporta el volcado. Las 3 mediciones se pueden reproducir con los scripts de `mediciones/`.
