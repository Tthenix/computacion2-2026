#!/usr/bin/env python3
"""
Entry point del monitor (FASE 6).

Arranca los 7 analizadores en procesos paralelos, registra el manejador de
señales POSIX con el patrón self-pipe y corre la TUI interactiva con 7 vistas
navegables usando `rich.Live`.
"""

import json
import multiprocessing as mp
import os
import select
import time

from rich.console import Console
from rich.live import Live

from senales import GestorSenales
from display import MonitorTUI
from analizadores import (resumen, memoria, fds, threads, senales as an_senales,
                          scheduling, sistema)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
REFRESCO_DISPLAY = 0.25  # 4 FPS para respuesta táctil rápida al teclado

ANALIZADORES = [
    (resumen, "resumen"),
    (memoria, "memoria"),
    (fds, "fds"),
    (threads, "threads"),
    (an_senales, "senales"),
    (scheduling, "scheduling"),
    (sistema, "sistema"),
]

console = Console()


def cargar_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"intervalos": {}, "verbose": False}


def hacer_dump(snapshot: dict, lock) -> str:
    """
    SIGUSR1: vuelca todo el snapshot (los 7 analizadores) a dump_<ts>.json.

    Toma el `lock` mientras copia las 7 claves: es la SECCIÓN CRÍTICA. Sin el
    lock, un analizador podría reescribir su clave justo entre que copiamos la
    clave A y la clave B, dejando un dump con datos de dos instantes mezclados
    (o media escritura). El lock hace que la copia sea un instante coherente.
    La copia es rápida, así que el lock se tiene muy poco tiempo.
    """
    ts = int(time.time())
    nombre = f"dump_{ts}.json"
    with lock:
        copia = {k: snapshot.get(k) for k in snapshot.keys()}
    with open(nombre, "w") as f:
        json.dump(copia, f, indent=2, ensure_ascii=False, default=str)
    return nombre


def main():
    config = cargar_config()
    verbose = config.get("verbose", False)
    intervalos_cfg = config.get("intervalos", {})

    manager = mp.Manager()
    snapshot = manager.dict()
    corriendo = mp.Event()
    corriendo.set()
    # Lock compartido: protege el snapshot durante el dump (SIGUSR1). Cada
    # analizador lo toma solo al ESCRIBIR su clave; el dump lo toma al leer las 7.
    lock_snapshot = mp.Lock()

    # Un Value de intervalo por analizador (ajustable en vivo)
    intervalos = {}
    procesos_hijos = []
    for modulo, clave in ANALIZADORES:
        intervalos[clave] = mp.Value("d", float(intervalos_cfg.get(clave, 2.0)))
        p = mp.Process(
            target=modulo.correr,
            args=(snapshot, intervalos[clave], corriendo, lock_snapshot),
            name=f"analizador-{clave}",
            daemon=True,
        )
        p.start()
        procesos_hijos.append(p)

    gestor = GestorSenales()
    tui = MonitorTUI(intervalos)   # pasar los Value para ajustar intervalos con +/-
    ultima_senal = ""
    ejecutando = True

    with Live(console=console, screen=True, refresh_per_second=4) as live:
        while ejecutando:
            legibles, _, _ = select.select([gestor.read_fd], [], [], REFRESCO_DISPLAY)

            if legibles:
                for accion in gestor.procesar_pendientes():
                    if accion == "shutdown":
                        ejecutando = False
                        ultima_senal = "SHUTDOWN"
                    elif accion == "reload":
                        config = cargar_config()
                        intervalos_cfg = config.get("intervalos", {})
                        for _, clave in ANALIZADORES:
                            if clave in intervalos_cfg:
                                intervalos[clave].value = float(intervalos_cfg[clave])
                        verbose = config.get("verbose", verbose)
                        ultima_senal = "SIGHUP (config recargada)"
                    elif accion == "dump":
                        nombre = hacer_dump(snapshot, lock_snapshot)
                        ultima_senal = f"SIGUSR1 (dump -> {nombre})"
                    elif accion == "verbose":
                        verbose = not verbose
                        ultima_senal = f"SIGUSR2 (verbose={'ON' if verbose else 'OFF'})"
                    elif accion == "repaint":
                        ultima_senal = "SIGWINCH (repaint)"

                if not ejecutando:
                    break

            # Extraer procesos actuales para la interacción de teclado
            e_resumen = snapshot.get("resumen")
            procesos = e_resumen["datos"] if e_resumen else []

            # Procesar eventos del teclado
            if not tui.procesar_teclas(procesos):
                ejecutando = False
                break

            # Renderizar la TUI completa
            live.update(tui.render(snapshot, verbose, ultima_senal, ANALIZADORES))

    # Apagado limpio
    corriendo.clear()
    for p in procesos_hijos:
        p.join(timeout=1.5)
        if p.is_alive():
            p.terminate()

    gestor.cerrar()
    manager.shutdown()
    console.print("[dim]Monitor cerrado limpiamente (7 analizadores terminados).[/dim]")


if __name__ == "__main__":
    main()
