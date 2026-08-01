"""
Analizador Señales (FASE 5 crudo, decodificado en FASE 8).

Lee de /proc/<pid>/status las máscaras de 64 bits:
    SigBlk (bloqueadas), SigIgn (ignoradas), SigCgt (con handler propio),
    SigPnd (pendientes del thread), ShdPnd (pendientes del proceso/grupo).

=== DECODIFICACIÓN (FASE 8) ===
La máscara es un número de 64 bits en hex. Cada BIT representa una señal:
    bit 0 (el menos significativo) -> señal 1 (SIGHUP)
    bit 1                          -> señal 2 (SIGINT)
    bit i                          -> señal (i+1)
Recorremos los 64 bits; los que están en 1, los traducimos a nombre con el
módulo `signal`. Guardamos el hex crudo Y la lista de nombres.

Ejemplo: SigCgt = 0000000000010000 (hex) = bit 16 en 1 -> señal 17 = SIGCHLD.

Devuelve dict por PID: { pid: {comm, SigBlk, SigBlk_nombres, ...} }.
"""
import signal as _signal

import procfs
from analizadores.base import bucle

NOMBRE = "senales"
_CLAVES = ["SigBlk", "SigIgn", "SigCgt", "SigPnd", "ShdPnd"]


def decodificar_mascara(hex_str):
    """
    Convierte una máscara hex de 64 bits (ej. '0000000000010000') a la lista de
    nombres de señales cuyos bits están en 1. bit i -> señal (i+1).
    """
    try:
        valor = int(hex_str, 16)
    except (ValueError, TypeError):
        return []
    nombres = []
    for i in range(64):
        if valor & (1 << i):
            num = i + 1
            try:
                nombres.append(_signal.Signals(num).name)  # ej. 'SIGCHLD'
            except ValueError:
                nombres.append(f"SIG{num}")  # tiempo real / desconocida
    return nombres


def extraer():
    res = {}
    for pid in procfs.listar_pids():
        status = procfs.leer_status(pid)
        if status is None:
            continue
        entrada = {"comm": status.get("Name", "?")}
        for clave in _CLAVES:
            hexv = status.get(clave, "0")
            entrada[clave] = hexv                                  # hex crudo
            entrada[clave + "_nombres"] = decodificar_mascara(hexv)  # legible
        res[pid] = entrada
    return res


def correr(snapshot, intervalo, corriendo, lock):
    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer, lock)
