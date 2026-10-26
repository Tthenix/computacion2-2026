"""Estado de la plataforma: registro de tareas + cola + pool de workers.

Flujo: `crear` registra la tarea y pone su id en la cola (sin esperar); N
workers (corrutinas) sacan ids de la cola y ejecutan la tarea.

Sin Lock a propósito: hay un solo hilo y el event loop solo cambia de
corrutina en un `await`. Ninguna sección "leer-modificar-escribir" del
registro tiene un `await` en el medio, así que nadie se le cruza.
"""
import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import time

import httpx

import tareas
from modelos import ESTADOS, Tarea, TareaNueva


class ColaLlena(Exception):
    """La cola alcanzó su máximo: el POST responde 503 (backpressure)."""


class Plataforma:
    def __init__(self, n_workers: int = 2, cola_max: int = 100,
                 timeout_default: float | None = 60, transporte: httpx.AsyncBaseTransport | None = None,
                 usar_executor: bool = True, procesos_hash: int | None = None):
        self.n_workers = n_workers
        self.cola_max = cola_max
        self.timeout_default = timeout_default  # None = sin límite
        self.transporte = transporte  # None = red real; los tests enchufan uno falso
        self.usar_executor = usar_executor  # False = hashear dentro del loop (solo la medición 2)
        self.procesos_hash = procesos_hash  # None = uno por CPU
        self.reiniciar()

    def reiniciar(self):
        """Vacía el registro (los tests lo usan). Conserva la configuración."""
        self.tareas: dict[int, Tarea] = {}
        self._proximo_id = 1
        self.ocupados = 0
        self.cola: asyncio.Queue[int] | None = None
        self._workers: list[asyncio.Task] = []
        self.cliente: httpx.AsyncClient | None = None  # compartido, vive entre iniciar y detener
        self.pool: ProcessPoolExecutor | None = None  # procesos para hashear (CPU-bound)
        # id → asyncio.Task que está corriendo esa tarea. Es el "botón" de cancelar.
        self.en_curso: dict[int, asyncio.Task] = {}

    # ---------- ciclo de vida (lo llama el lifespan) ----------

    def iniciar(self):
        """Crea la cola, el cliente httpx y los workers. Hay que llamarlo con el loop andando."""
        # UN cliente para todas las tareas: reusa conexiones (pool) en vez de abrir
        # un socket nuevo por pedido.
        self.cliente = httpx.AsyncClient(transport=self.transporte, timeout=30)
        if self.usar_executor:
            # spawn: arranca procesos limpios (igual en Linux y Windows); por eso main.py
            # necesita la guarda `if __name__ == "__main__"`. Los procesos nacen al primer uso.
            self.pool = ProcessPoolExecutor(
                max_workers=self.procesos_hash, mp_context=multiprocessing.get_context("spawn"))
        self.cola = asyncio.Queue(maxsize=self.cola_max)
        self._workers = [asyncio.create_task(self._worker()) for _ in range(self.n_workers)]

    async def detener(self):
        """Cancela los workers, espera a que terminen y cierra cliente y pool. (Apagado ordenado: fase 6.)"""
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        if self.cliente:
            await self.cliente.aclose()  # recién ahora: ya no hay tareas usándolo
        if self.pool:
            # wait=True: espera a que cada hijo termine su bloque en curso (<= ~0,1 s).
            self.pool.shutdown(wait=True, cancel_futures=True)

    # ---------- registro ----------

    def crear(self, nueva: TareaNueva) -> Tarea:
        """Registra y encola. Levanta ColaLlena SIN registrar si no hay lugar."""
        if self.cola.full():
            raise ColaLlena(f"cola llena ({self.cola_max} tareas esperando)")
        tarea = Tarea(id=self._proximo_id, creada=time.time(), **nueva.model_dump())
        self.tareas[tarea.id] = tarea
        self._proximo_id += 1
        self.cola.put_nowait(tarea.id)  # no bloquea: ya chequeamos que hay lugar
        return tarea

    def obtener(self, id: int) -> Tarea | None:
        return self.tareas.get(id)

    def listar(self, estado: str | None = None) -> list[Tarea]:
        return [t for t in self.tareas.values() if estado is None or t.estado == estado]

    def cancelar(self, id: int) -> Tarea | None:
        """Cancela una tarea pendiente o en ejecución. None si no existe.

        - pendiente: se marca cancelada; su id sigue en la cola y el worker la
          saltea al sacarla.
        - ejecutando: se le hace `.cancel()` a SU asyncio.Task (no al worker). El
          CancelledError llega al `await` de `_ejecutar`, que libera todo.
        Levanta ValueError si ya terminó (o está terminando).
        """
        tarea = self.tareas.get(id)
        if tarea is None:
            return None
        if tarea.estado == "pendiente":
            tarea.estado = "cancelada"
        elif tarea.estado == "ejecutando" and self.en_curso[id].cancel():
            # cancel() devuelve False si la Task ya terminó y el worker todavía no
            # lo registró: en ese caso es tarde para cancelar.
            tarea.estado = "cancelada"  # ya, para que la respuesta del DELETE lo muestre
        else:
            raise ValueError(f"la tarea {id} está '{tarea.estado}', no se puede cancelar")
        return tarea

    # ---------- workers ----------

    async def _worker(self):
        """Loop del worker: sacar id → ejecutar → avisar que terminó. Para siempre."""
        while True:
            id = await self.cola.get()  # acá se SUSPENDE si la cola está vacía
            try:
                tarea = self.tareas[id]
                if tarea.estado == "pendiente":  # si no, la cancelaron esperando
                    await self._ejecutar(tarea)
            finally:
                self.cola.task_done()  # siempre, o cola.join() quedaría colgado

    async def _ejecutar(self, tarea: Tarea):
        tarea.estado = "ejecutando"
        tarea.inicio = time.time()
        self.ocupados += 1
        limite = tarea.timeout if tarea.timeout is not None else self.timeout_default
        # La tarea corre como su propio asyncio.Task: así DELETE puede cancelarla a
        # ella sin tocar al worker. El worker solo espera (await) su resultado.
        trabajo = asyncio.create_task(tareas.EJECUTORES[tarea.tipo](tarea, self))
        self.en_curso[tarea.id] = trabajo
        try:
            async with asyncio.timeout(limite):  # None = sin límite
                tarea.resultado = await trabajo
            tarea.estado = "completada"
        except TimeoutError:
            # asyncio.timeout canceló el await (y por propagación a `trabajo`) y
            # convirtió ese CancelledError en TimeoutError.
            tarea.estado = "fallida"
            tarea.error = f"timeout tras {limite}s"
        except asyncio.CancelledError:
            tarea.estado = "cancelada"
            # ¿Me cancelaron a la tarea (DELETE) o al worker (apagado)? Si hay una
            # cancelación pendiente sobre el worker mismo, hay que re-lanzar: tragarla
            # dejaría un worker inmortal que el apagado no puede parar.
            if asyncio.current_task().cancelling() > 0:
                raise
        except Exception as e:  # CancelledError NO es Exception: va en su propio except
            tarea.estado = "fallida"
            tarea.error = repr(e)
        finally:
            del self.en_curso[tarea.id]
            tarea.fin = time.time()
            self.ocupados -= 1

    # ---------- estadísticas ----------

    def estadisticas(self) -> dict:
        conteo = {e: 0 for e in ESTADOS}
        for t in self.tareas.values():
            conteo[t.estado] += 1
        corridas = [t for t in self.tareas.values() if t.inicio is not None and t.fin is not None]
        return {
            "por_estado": conteo,
            "workers": self.n_workers,
            "ocupados": self.ocupados,
            "en_cola": self.cola.qsize() if self.cola else 0,
            "tiempo_promedio_espera": _promedio([t.inicio - t.creada for t in corridas]),
            "tiempo_promedio_ejecucion": _promedio([t.fin - t.inicio for t in corridas]),
        }


def _promedio(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None
