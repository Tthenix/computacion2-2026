"""Estado de la plataforma: el registro de tareas.

Fase 1: solo un dict en memoria. La cola y los workers llegan en la fase 2.

Sin Lock a propósito: hay un solo hilo y el event loop solo cambia de
corrutina en un `await`. Ningún método de acá tiene `await`, así que cada
uno corre entero sin que nadie se le cruce.
"""
from modelos import ESTADOS, Tarea, TareaNueva


class Plataforma:
    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.tareas: dict[int, Tarea] = {}
        self._proximo_id = 1

    def crear(self, nueva: TareaNueva) -> Tarea:
        tarea = Tarea(id=self._proximo_id, **nueva.model_dump())
        self.tareas[tarea.id] = tarea
        self._proximo_id += 1
        return tarea

    def obtener(self, id: int) -> Tarea | None:
        return self.tareas.get(id)

    def listar(self, estado: str | None = None) -> list[Tarea]:
        return [t for t in self.tareas.values() if estado is None or t.estado == estado]

    def cancelar(self, id: int) -> Tarea | None:
        """Cancela una tarea pendiente. None si no existe.

        Levanta ValueError si ya no se puede cancelar (fase 3 suma 'ejecutando').
        """
        tarea = self.tareas.get(id)
        if tarea is None:
            return None
        if tarea.estado != "pendiente":
            raise ValueError(f"la tarea {id} está '{tarea.estado}', no se puede cancelar")
        tarea.estado = "cancelada"
        return tarea

    def estadisticas(self) -> dict:
        conteo = {e: 0 for e in ESTADOS}
        for t in self.tareas.values():
            conteo[t.estado] += 1
        return {"por_estado": conteo}
