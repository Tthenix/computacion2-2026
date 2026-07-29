"""
Analizador Scheduling (FASE 5): cómo el planificador trata a cada proceso.

Datos: nice, priority, scheduling policy (OTHER/FIFO/RR/...), RT priority,
CPU affinity, context switches voluntarios/involuntarios, utime/stime, SID/PGID.
Fuentes: /proc/<pid>/stat (posicional) y /proc/<pid>/status (etiquetado).

Devuelve dict por PID: { pid: {campos de scheduling} }.
"""
import procfs
from analizadores.base import bucle

NOMBRE = "scheduling"


def extraer():
    res = {}
    for pid in procfs.listar_pids():
        stat = procfs.leer_stat(pid)
        if stat is None:
            continue
        status = procfs.leer_status(pid) or {}
        policy_num = stat.get("policy", 0)
        res[pid] = {
            "comm": stat["comm"],
            "nice": stat.get("nice", 0),
            "priority": stat.get("priority", 0),
            "policy": procfs.POLITICAS_SCHED.get(policy_num, str(policy_num)),
            "rt_priority": stat.get("rt_priority", 0),
            "affinity": status.get("Cpus_allowed_list", "?"),
            "vol_ctxt": procfs._a_int(status.get("voluntary_ctxt_switches", 0)),
            "nonvol_ctxt": procfs._a_int(status.get("nonvoluntary_ctxt_switches", 0)),
            "utime": stat.get("utime", 0),
            "stime": stat.get("stime", 0),
            "sid": stat.get("session", 0),
            "pgid": stat.get("pgrp", 0),
        }
    return res


def correr(snapshot, intervalo, corriendo):
    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer)
