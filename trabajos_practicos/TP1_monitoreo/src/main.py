#!/usr/bin/env python3
"""
Entry point del monitor.

FASE 2: monolito (Sistema + Resumen) con CPU% por delta de jiffies.
FASE 3: señales con self-pipe (senales.py).
FASE 4: memoria compartida. El snapshot vive en un Manager().dict(); el
        analizador "resumen" corre en SU PROPIO PROCESO y escribe al dict; el
        display (este proceso) solo LEE y dibuja.

Arquitectura actual:

    ┌─────────────────────────────┐
    │   snapshot = Manager.dict    │
    │   { "resumen": {datos, ts} } │
    └──────▲───────────────┬──────┘
           │ escribe       │ lee
     ┌─────┴──────┐   ┌────▼─────────┐
     │ analizador │   │  display     │
     │  resumen   │   │ (este proc)  │
     │ (proc hijo)│   │ + señales    │
     └────────────┘   └──────────────┘

Prueba clave (fase 4): matar el proceso analizador con `kill` -> el display
sigue vivo mostrando el último dato (que se vuelve "viejo"/stale).
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

from recolector import Recolector
from senales import GestorSenales
from analizadores import resumen as analizador_resumen

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

# Cada cuánto REDIBUJA el display (independiente del ritmo del analizador).
REFRESCO_DISPLAY = 1.0

console = Console()


def cargar_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"intervalos": {"resumen": 2.0}, "verbose": False}


def _fmt_mb(kb):
    return f"{kb / 1024:.1f} MB"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render_sistema(sis, verbose, ultima_senal, edad_resumen):
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


def render_procesos(procesos, verbose, edad_resumen):
    # Título con la "frescura" del dato del analizador (clave para la prueba de
    # matar el analizador: si el dato envejece, se ve acá).
    if edad_resumen is None:
        estado_dato = Text("sin datos del analizador todavía", style="yellow")
    elif edad_resumen > 5:
        estado_dato = Text(f"⚠ DATO VIEJO ({edad_resumen:.0f}s) "
                           f"— ¿analizador caído?", style="bold red")
    else:
        estado_dato = Text(f"actualizado hace {edad_resumen:.1f}s", style="green")

    tabla = Table(expand=True, header_style="bold", title=estado_dato,
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
    limite = 45 if verbose else 25
    for p in procesos[:limite]:
        est = p["estado"]
        estilo = {"R": "green", "Z": "bold red", "D": "yellow"}.get(est, "")
        tabla.add_row(
            str(p["pid"]), str(p["ppid"]), p["usuario"],
            Text(est, style=estilo), f"{p['cpu']:.1f}",
            _fmt_mb(p["rss_kb"]), str(p["threads"]), p["comando"],
        )
    return tabla


def render(procesos, sistema, verbose, ultima_senal, edad_resumen):
    return Group(
        render_sistema(sistema, verbose, ultima_senal, edad_resumen),
        render_procesos(procesos, verbose, edad_resumen),
    )


def hacer_dump(procesos, sistema):
    ts = int(time.time())
    nombre = f"dump_{ts}.json"
    with open(nombre, "w") as f:
        json.dump({"timestamp": ts, "sistema": sistema, "procesos": procesos},
                  f, indent=2, ensure_ascii=False)
    return nombre


# ---------------------------------------------------------------------------
# Main: orquesta procesos + display + señales
# ---------------------------------------------------------------------------
def main():
    config = cargar_config()
    verbose = config.get("verbose", False)

    # --- Memoria compartida ---
    manager = mp.Manager()
    snapshot = manager.dict()          # el "snapshot global" compartido
    intervalo_resumen = mp.Value("d", config.get("intervalos", {}).get("resumen", 2.0))
    corriendo = mp.Event()
    corriendo.set()

    # --- Lanzar el analizador en su propio proceso ---
    p_resumen = mp.Process(
        target=analizador_resumen.correr,
        args=(snapshot, intervalo_resumen, corriendo),
        name="analizador-resumen",
        daemon=True,   # si el padre muere, el hijo no queda huérfano colgado
    )
    p_resumen.start()

    # El display calcula la vista Sistema con su propio Recolector (fase 4;
    # en fase 5 esto también pasa a un analizador aparte).
    recolector_sistema = Recolector()
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
                        intervalo_resumen.value = config.get("intervalos", {}).get("resumen", 2.0)
                        verbose = config.get("verbose", verbose)
                        ultima_senal = "SIGHUP (config recargada)"
                    elif accion == "dump":
                        entrada = snapshot.get("resumen", {})
                        nombre = hacer_dump(entrada.get("datos", []),
                                            recolector_sistema.snapshot_sistema(
                                                entrada.get("datos", [])))
                        ultima_senal = f"SIGUSR1 (dump -> {nombre})"
                    elif accion == "verbose":
                        verbose = not verbose
                        ultima_senal = f"SIGUSR2 (verbose={'ON' if verbose else 'OFF'})"
                    elif accion == "repaint":
                        ultima_senal = "SIGWINCH (repaint)"
                if not ejecutando:
                    break

            # --- LEER del snapshot compartido (no recalculamos procesos acá) ---
            entrada = snapshot.get("resumen")
            if entrada is None:
                procesos = []
                edad = None
                pid_analizador = None
            else:
                procesos = entrada["datos"]
                edad = time.time() - entrada["ts"]
                pid_analizador = entrada.get("pid")

            sistema = recolector_sistema.snapshot_sistema(procesos)
            senal_mostrar = ultima_senal
            if pid_analizador:
                senal_mostrar = (ultima_senal + "  |  " if ultima_senal else "") + \
                    f"analizador PID {pid_analizador}"
            live.update(render(procesos, sistema, verbose, senal_mostrar, edad))

    # --- Shutdown limpio ---
    corriendo.clear()               # avisar al analizador que pare
    p_resumen.join(timeout=2)       # esperar a que termine
    if p_resumen.is_alive():
        p_resumen.terminate()       # por las dudas
    gestor.cerrar()
    manager.shutdown()
    console.print("[dim]Monitor cerrado limpio.[/dim]")


if __name__ == "__main__":
    main()
