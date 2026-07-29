"""
Analizador Memoria (FASE 5): VmSize/VmRSS/VmData/VmStk/VmExe/VmLib, VmHWM,
VmSwap, page faults (minor/major) y segmentos agrupados desde /proc/<pid>/maps.

Devuelve un dict indexado por PID: { pid: {campos de memoria} }.
"""
import procfs
from analizadores.base import bucle

NOMBRE = "memoria"


def _kb(status, clave):
    """Extrae 'VmRSS: 1234 kB' -> 1234 (int). 0 si falta."""
    val = status.get(clave)
    if not val:
        return 0
    partes = val.split()
    return procfs._a_int(partes[0]) if partes else 0


def extraer():
    res = {}
    for pid in procfs.listar_pids():
        status = procfs.leer_status(pid)
        if status is None:
            continue
        stat = procfs.leer_stat(pid)
        maps = procfs.leer_maps(pid) or {}
        res[pid] = {
            "comm": stat["comm"] if stat else status.get("Name", "?"),
            "vmsize": _kb(status, "VmSize"),   # tamaño virtual total
            "vmrss": _kb(status, "VmRSS"),     # residente en RAM (lo que ocupa de verdad)
            "vmdata": _kb(status, "VmData"),
            "vmstk": _kb(status, "VmStk"),
            "vmexe": _kb(status, "VmExe"),
            "vmlib": _kb(status, "VmLib"),
            "vmhwm": _kb(status, "VmHWM"),     # pico histórico de RSS
            "vmswap": _kb(status, "VmSwap"),
            "minflt": stat.get("minflt", 0) if stat else 0,  # faults sin tocar disco
            "majflt": stat.get("majflt", 0) if stat else 0,  # faults que fueron a disco
            "segmentos": maps,
        }
    return res


def correr(snapshot, intervalo, corriendo):
    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer)
