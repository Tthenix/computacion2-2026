"""
Analizador Sistema (FASE 5): stats globales de la máquina.

CPU global por modo (delta de /proc/stat), memoria (/proc/meminfo), load average,
uptime, totales de procesos por estado, zombies, threads totales y top 3 por
CPU/memoria.

Antes (fase 4) esto lo calculaba el display; ahora vive en su propio proceso,
como los demás. Mantiene un Recolector propio (para el delta de CPU global Y
para el delta de CPU% por proceso que necesita el top 3) — igual que hace
resumen.py con el suyo, cada uno con su propia lectura anterior.

Devuelve el dict de sistema (mismo formato que Recolector.snapshot_sistema).
"""
from recolector import Recolector
from analizadores.base import bucle

NOMBRE = "sistema"


def correr(snapshot, intervalo, corriendo, lock):
    rec = Recolector()

    def extraer():
        # Lista completa (con CPU%/RSS por proceso) para poder derivar el
        # top 3 por CPU y por memoria que pide la consigna.
        procesos = rec.snapshot_procesos()
        return rec.snapshot_sistema(procesos)

    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer, lock)
