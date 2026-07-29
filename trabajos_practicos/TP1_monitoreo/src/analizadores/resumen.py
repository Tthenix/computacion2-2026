"""
Analizador Resumen (FASE 4): corre en SU PROPIO PROCESO.

Estado, CPU%, RSS, threads, comando de cada proceso. En un loop:
  1. lee /proc y calcula el snapshot de procesos (con CPU% por delta de jiffies),
  2. lo escribe en el dict compartido bajo la clave "resumen",
  3. duerme su intervalo (ajustable en vivo vía Value compartido, fase 7).

=== POR QUÉ CADA ANALIZADOR ES UN PROCESO Y NO UN THREAD ===
(pregunta de corrección)
El TP pide arquitectura MULTIPROCESO. Con procesos, cada analizador tiene su
propio intérprete Python y su propio GIL: pueden correr CPU en paralelo real en
distintos cores. Con threads compartirían un solo GIL y no habría paralelismo
real para trabajo CPU-bound (leer y parsear /proc lo es). Además, si un analizador
crashea, no se lleva puesto al resto (aislamiento de procesos).

=== POR QUÉ EL RECOLECTOR VIVE ACÁ ADENTRO ===
El CPU% necesita recordar la lectura anterior de jiffies (delta). Como cada
analizador corre a su propio ritmo, cada uno tiene SU instancia de Recolector con
SU estado previo. Así el delta se calcula contra la lectura anterior de ESTE
analizador, coherente con su intervalo.
"""
import os
import time

from recolector import Recolector


def correr(snapshot, intervalo, corriendo):
    """
    Args:
        snapshot:  Manager().dict() compartido. Escribimos snapshot["resumen"].
        intervalo: multiprocessing.Value('d') con los segundos entre lecturas
                   (compartido para poder ajustarlo en vivo desde el display).
        corriendo: multiprocessing.Event(). Mientras esté "set", seguimos.
    """
    rec = Recolector()

    while corriendo.is_set():
        procesos = rec.snapshot_procesos()

        # Escribir el resultado completo de una: reemplazar el valor de la clave
        # es atómico a nivel del Manager (viaja como un objeto pickled único).
        # Guardamos también el timestamp para que el display sepa qué tan fresco
        # es el dato (clave para detectar si el analizador murió).
        snapshot["resumen"] = {
            "datos": procesos,
            "ts": time.time(),
            "pid": os.getpid(),   # PID de ESTE proceso analizador (para la prueba de matarlo)
        }

        # Dormir el intervalo actual (se puede cambiar en caliente por el Value).
        time.sleep(intervalo.value)
