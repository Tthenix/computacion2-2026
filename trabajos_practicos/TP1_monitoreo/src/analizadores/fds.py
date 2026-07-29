"""
Analizador File Descriptors (FASE 5): lista los FDs abiertos de cada proceso y
el destino de cada uno (archivo, socket, pipe, tty...), leyendo los symlinks de
/proc/<pid>/fd/.

Devuelve dict por PID: { pid: {comm, count, lista:[{fd, destino, tipo}]} }.
Guardo hasta 40 FDs por proceso para no inflar el snapshot; `count` es el total.
"""
import procfs
from analizadores.base import bucle

NOMBRE = "fds"
TOPE_POR_PROC = 40


def extraer():
    res = {}
    for pid in procfs.listar_pids():
        fds = procfs.leer_fds(pid, limite=TOPE_POR_PROC)
        if fds is None:
            continue
        stat = procfs.leer_stat(pid)
        res[pid] = {
            "comm": stat["comm"] if stat else "?",
            "count": fds["count"],
            "lista": fds["lista"],
        }
    return res


def correr(snapshot, intervalo, corriendo):
    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer)
