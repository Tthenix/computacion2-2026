"""
Analizador Resumen (FASE 4-5): corre en SU PROPIO PROCESO.

Estado, CPU%, RSS, threads, comando de cada proceso. Usa el Recolector, que
mantiene el estado previo de jiffies para el CPU% por delta (por eso vive acá
adentro: cada analizador tiene su propio ritmo y su propia lectura anterior).

Por qué proceso y no thread: paralelismo real + aislamiento (ver base.py y el
doc de justificación).
"""
from recolector import Recolector
from analizadores.base import bucle

NOMBRE = "resumen"


def correr(snapshot, intervalo, corriendo):
    rec = Recolector()
    bucle(NOMBRE, snapshot, intervalo, corriendo, rec.snapshot_procesos)
