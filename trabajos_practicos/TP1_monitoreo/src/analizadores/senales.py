"""
Analizador Señales (FASE 5): máscaras de señales de cada proceso.

Lee de /proc/<pid>/status las máscaras hexadecimales de 64 bits:
    SigBlk (bloqueadas), SigIgn (ignoradas), SigCgt (con handler propio),
    SigPnd (pendientes del thread), ShdPnd (pendientes del proceso/grupo).

FASE 5: se guardan en hex CRUDO. La decodificación a nombres legibles
(SIGTERM, SIGINT...) se hace en FASE 8 (cada bit = una señal).

Devuelve dict por PID: { pid: {comm, SigBlk, SigIgn, SigCgt, SigPnd, ShdPnd} }.
"""
import procfs
from analizadores.base import bucle

NOMBRE = "senales"
_CLAVES = ["SigBlk", "SigIgn", "SigCgt", "SigPnd", "ShdPnd"]


def extraer():
    res = {}
    for pid in procfs.listar_pids():
        status = procfs.leer_status(pid)
        if status is None:
            continue
        entrada = {"comm": status.get("Name", "?")}
        for clave in _CLAVES:
            entrada[clave] = status.get(clave, "0")  # hex crudo, ej. "0000000000010000"
        res[pid] = entrada
    return res


def correr(snapshot, intervalo, corriendo):
    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer)
