#!/usr/bin/env python3
"""
Entry point del monitor.

FASE 2: monolito (Sistema + Resumen) con CPU% por delta de jiffies.
FASE 3: señales con self-pipe (senales.py).
FASE 4: memoria compartida (Manager.dict); 1 analizador en su proceso.
FASE 5: los 7 analizadores, cada uno en SU proceso, con su intervalo, todos
        escribiendo al snapshot. El display solo lee.

Arquitectura:

     snapshot = Manager.dict()
     { resumen, memoria, fds, threads, senales, scheduling, sistema }
        ▲  ▲  ▲  ▲  ▲  ▲  ▲                     │ lee
        │  │  │  │  │  │  │                     │
      7 procesos analizadores (cada uno su    display / main (este proceso)
      intervalo vía Value compartido)          + manejo de señales

La TUI con las 7 vistas navegables es FASE 6; acá el display muestra Resumen +
Sistema + un pie con el estado de los 7 analizadores (para verificar que corren).
"""
import json
import multiprocessing as mp
import os
import select
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from senales import GestorSenales
from analizadores import (resumen, memoria, fds, threads, senales as an_senales,
                          scheduling, sistema)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
REFRESCO_DISPLAY = 1.0

# Registro de los 7 analizadores: (módulo, clave de intervalo en config.json).
# El orden es el de las vistas del TP.
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


def cargar_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"intervalos": {}, "verbose": False}


def _fmt_mb(kb):
    return f"{kb / 1024:.1f} MB"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render_sistema(sis, verbose, ultima_senal):
    if sis is None:
        return Panel(Text("esperando datos del analizador de sistema...",
                          style="yellow"), title="Sistema", border_style="cyan")
    cpu = sis["cpu_desglose"]
    mem_usada = sis["mem_total_kb"] - sis["mem_disp_kb"]
    load = sis["load"]

    txt = Text()
    txt.append("CPU  ", style="bold")
    txt.append(f"{sis['cpu_uso']:.1f}% ", style="bold cyan")
    txt.append(f"(user {cpu['user']}%  sys {cpu['system']}%  "
               f"idle {cpu['idle']}%  iowait {cpu['iowait']}%)   ")
    txt.append(f"{sis['ncpus']} cores\n")
    txt.append("MEM  ", style="bold")
    txt.append(f"{_fmt_mb(mem_usada)} / {_fmt_mb(sis['mem_total_kb'])}   ")
    txt.append(f"cache {_fmt_mb(sis['cached_kb'])}   "
               f"swap {_fmt_mb(sis['swap_total_kb'] - sis['swap_libre_kb'])}"
               f" / {_fmt_mb(sis['swap_total_kb'])}\n")
    txt.append("LOAD ", style="bold")
    txt.append(f"{load['load_1']}  {load['load_5']}  {load['load_15']}   ")
    txt.append("PROC ", style="bold")
    estados = "  ".join(f"{k}:{v}" for k, v in sorted(sis["por_estado"].items()))
    txt.append(f"{sis['procs_total']} total  ({estados})   ")
    z = sis["zombies"]
    txt.append(f"zombies:{z}", style="bold red" if z else "dim")

    sub = f"uptime {sis['uptime_seg'] / 3600:.1f} h"
    if verbose:
        sub += "  |  VERBOSE"
    if ultima_senal:
        sub += f"  |  señal: {ultima_senal}"
    return Panel(txt, title="Sistema", subtitle=sub, border_style="cyan")


def render_procesos(procesos, verbose):
    tabla = Table(expand=True, header_style="bold", title="Resumen (vista 1)",
                  title_justify="left")
    tabla.add_column("PID", justify="right", style="dim", width=7)
    tabla.add_column("PPID", justify="right", style="dim", width=7)
    tabla.add_column("USUARIO", width=10)
    tabla.add_column("EST", justify="center", width=3)
    tabla.add_column("CPU%", justify="right", width=6)
    tabla.add_column("RSS", justify="right", width=10)
    tabla.add_column("THR", justify="right", width=4)
    tabla.add_column("COMANDO", ratio=1, no_wrap=True)

    procesos = sorted(procesos, key=lambda p: p["cpu"], reverse=True)
    limite = 40 if verbose else 20
    for p in procesos[:limite]:
        est = p["estado"]
        estilo = {"R": "green", "Z": "bold red", "D": "yellow"}.get(est, "")
        tabla.add_row(
            str(p["pid"]), str(p["ppid"]), p["usuario"],
            Text(est, style=estilo), f"{p['cpu']:.1f}",
            _fmt_mb(p["rss_kb"]), str(p["threads"]), p["comando"],
        )
    return tabla


def render_pie(snapshot, ahora):
    """
    Pie de pantalla: estado de los 7 analizadores. Para cada uno muestra su PID
    y hace cuánto escribió (frescura). Sirve para VERIFICAR que los 7 procesos
    corren en paralelo a su ritmo, y para ver si alguno murió (se pone rojo).
    """
    txt = Text()
    txt.append("Analizadores: ", style="bold")
    for modulo, _ in ANALIZADORES:
        nombre = modulo.NOMBRE
        entrada = snapshot.get(nombre)
        if entrada is None:
            txt.append(f"{nombre}(--) ", style="yellow")
            continue
        edad = ahora - entrada["ts"]
        pid = entrada.get("pid", "?")
        estilo = "green" if edad < 15 else "bold red"
        txt.append(f"{nombre}[{pid}]{edad:.0f}s ", style=estilo)
    return Panel(txt, border_style="dim", title="Fase 5 · 7 procesos en paralelo")


def render(procesos, sistema_datos, snapshot, verbose, ultima_senal):
    return Group(
        render_sistema(sistema_datos, verbose, ultima_senal),
        render_procesos(procesos, verbose),
        render_pie(snapshot, time.time()),
    )


def hacer_dump(snapshot):
    """SIGUSR1: vuelca TODO el snapshot (los 7 analizadores) a dump_<ts>.json."""
    ts = int(time.time())
    nombre = f"dump_{ts}.json"
    # Copiar a un dict normal (el Manager.dict no es directamente serializable
    # con json). Las claves int de los sub-dicts se vuelven string en JSON.
    copia = {k: snapshot.get(k) for k in snapshot.keys()}
    with open(nombre, "w") as f:
        json.dump(copia, f, indent=2, ensure_ascii=False, default=str)
    return nombre


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    config = cargar_config()
    verbose = config.get("verbose", False)
    intervalos_cfg = config.get("intervalos", {})

    manager = mp.Manager()
    snapshot = manager.dict()
    corriendo = mp.Event()
    corriendo.set()

    # Un Value de intervalo por analizador (ajustable en vivo, fase 7).
    intervalos = {}
    procesos_hijos = []
    for modulo, clave in ANALIZADORES:
        intervalos[clave] = mp.Value("d", float(intervalos_cfg.get(clave, 2.0)))
        p = mp.Process(
            target=modulo.correr,
            args=(snapshot, intervalos[clave], corriendo),
            name=f"analizador-{clave}",
            daemon=True,
        )
        p.start()
        procesos_hijos.append(p)

    gestor = GestorSenales()
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
                        nombre = hacer_dump(snapshot)
                        ultima_senal = f"SIGUSR1 (dump -> {nombre})"
                    elif accion == "verbose":
                        verbose = not verbose
                        ultima_senal = f"SIGUSR2 (verbose={'ON' if verbose else 'OFF'})"
                    elif accion == "repaint":
                        ultima_senal = "SIGWINCH (repaint)"
                if not ejecutando:
                    break

            # Leer del snapshot (sin recalcular nada acá).
            entrada_resumen = snapshot.get("resumen")
            procesos = entrada_resumen["datos"] if entrada_resumen else []
            entrada_sistema = snapshot.get("sistema")
            sistema_datos = entrada_sistema["datos"] if entrada_sistema else None

            live.update(render(procesos, sistema_datos, snapshot, verbose, ultima_senal))

    # Shutdown limpio: avisar a todos y esperar.
    corriendo.clear()
    for p in procesos_hijos:
        p.join(timeout=2)
        if p.is_alive():
            p.terminate()
    gestor.cerrar()
    manager.shutdown()
    console.print("[dim]Monitor cerrado limpio (7 analizadores terminados).[/dim]")


if __name__ == "__main__":
    main()
