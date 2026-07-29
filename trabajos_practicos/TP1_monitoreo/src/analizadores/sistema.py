"""
Analizador Sistema (FASE 5): stats globales de la máquina.

CPU global por modo (delta de /proc/stat), memoria (/proc/meminfo), load average,
uptime, totales de procesos por estado, zombies y threads totales.

Antes (fase 4) esto lo calculaba el display; ahora vive en su propio proceso,
como los demás. Mantiene un Recolector para el delta de CPU global (necesita
recordar la lectura anterior de jiffies).

Devuelve el dict de sistema (mismo formato que Recolector.snapshot_sistema).
"""
import procfs
from recolector import Recolector
from analizadores.base import bucle

NOMBRE = "sistema"


def correr(snapshot, intervalo, corriendo):
    rec = Recolector()

    def extraer():
        # Lista liviana de procesos: solo estado y nº de threads, que es lo que
        # snapshot_sistema necesita para los totales (por_estado, zombies,
        # threads_total). No calculamos CPU% por proceso acá (eso es de resumen).
        lite = []
        for pid in procfs.listar_pids():
            stat = procfs.leer_stat(pid)
            if stat is None:
                continue
            lite.append({"estado": stat["state"],
                         "threads": stat.get("num_threads", 1)})
        return rec.snapshot_sistema(lite)

    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer)
