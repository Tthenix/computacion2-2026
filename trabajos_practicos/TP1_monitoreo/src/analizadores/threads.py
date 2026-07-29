"""
Analizador Threads / LWPs (FASE 5, se enriquece en FASE 7).

Un thread en Linux es un LWP (Light Weight Process): comparte memoria con su
proceso pero tiene su propio TID y su propia entrada en /proc/<pid>/task/<tid>/.
Acá listamos, por proceso, sus threads con TID, nombre, estado y context
switches. El CPU% por thread (delta de jiffies por TID) se agrega en fase 7.

Devuelve dict por PID: { pid: {comm, count, lista:[{tid, nombre, estado,
                          vol_ctxt, nonvol_ctxt}]} }.
"""
import procfs
from analizadores.base import bucle

NOMBRE = "threads"


def extraer():
    res = {}
    for pid in procfs.listar_pids():
        tids = procfs.listar_tids(pid)
        if not tids:
            continue
        lista = []
        for tid in sorted(tids):
            st = procfs.leer_stat_thread(pid, tid)
            if st is None:
                continue
            status = procfs.leer_status_thread(pid, tid) or {}
            lista.append({
                "tid": tid,
                "nombre": st["comm"],
                "estado": st["state"],
                "vol_ctxt": procfs._a_int(status.get("voluntary_ctxt_switches", 0)),
                "nonvol_ctxt": procfs._a_int(status.get("nonvoluntary_ctxt_switches", 0)),
            })
        # comm del proceso = el thread principal (tid == pid)
        comm = next((t["nombre"] for t in lista if t["tid"] == pid), "?")
        res[pid] = {"comm": comm, "count": len(lista), "lista": lista}
    return res


def correr(snapshot, intervalo, corriendo):
    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer)
