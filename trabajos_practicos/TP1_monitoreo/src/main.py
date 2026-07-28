#!/usr/bin/env python3
"""
Entry point del monitor.

FASE 2: monolito. Un solo proceso que en loop relee /proc, calcula CPU% por
delta de jiffies, y dibuja dos vistas con rich: Sistema (arriba) + Resumen
(tabla de procesos). Todavía NO es multiproceso: eso llega en fases 4-5.

Salir: Ctrl+C (shutdown limpio real con self-pipe llega en fase 3).
"""
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from recolector import Recolector

# Intervalo de refresco del monolito (segundos). En fases siguientes cada vista
# tendrá el suyo propio; por ahora uno global.
INTERVALO = 2.0

console = Console()


def _fmt_mb(kb):
    """Formatea kilobytes como MB con 1 decimal."""
    return f"{kb / 1024:.1f} MB"


def render_sistema(sis):
    """Panel superior: stats globales del sistema (vista Sistema)."""
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

    uptime_h = sis["uptime_seg"] / 3600
    return Panel(txt, title="Sistema", subtitle=f"uptime {uptime_h:.1f} h",
                 border_style="cyan")


def render_procesos(procesos):
    """Tabla inferior: lista de procesos ordenada por CPU% (vista Resumen)."""
    tabla = Table(expand=True, header_style="bold")
    tabla.add_column("PID", justify="right", style="dim", width=7)
    tabla.add_column("USUARIO", width=10)
    tabla.add_column("EST", justify="center", width=3)
    tabla.add_column("CPU%", justify="right", width=6)
    tabla.add_column("RSS", justify="right", width=10)
    tabla.add_column("THR", justify="right", width=4)
    tabla.add_column("COMANDO", ratio=1, no_wrap=True)

    # ordenar por CPU% desc, mostrar top 25
    procesos = sorted(procesos, key=lambda p: p["cpu"], reverse=True)

    for p in procesos[:25]:
        est = p["estado"]
        # colorear estados relevantes
        estilo = {"R": "green", "Z": "bold red", "D": "yellow"}.get(est, "")
        tabla.add_row(
            str(p["pid"]),
            p["usuario"],
            Text(est, style=estilo),
            f"{p['cpu']:.1f}",
            _fmt_mb(p["rss_kb"]),
            str(p["threads"]),
            p["comando"],
        )
    return tabla


def render(recolector):
    """Arma la pantalla completa: Sistema arriba + Resumen abajo."""
    procesos = recolector.snapshot_procesos()
    sistema = recolector.snapshot_sistema(procesos)
    return Group(
        render_sistema(sistema),
        render_procesos(procesos),
    )


def main():
    recolector = Recolector()
    console.print("[dim]Monitor Fase 2 (monolito). Ctrl+C para salir.[/dim]")
    try:
        # Live redibuja en el lugar sin hacer scroll (base de la TUI de fase 6).
        with Live(render(recolector), console=console, screen=True,
                  refresh_per_second=4) as live:
            while True:
                time.sleep(INTERVALO)
                live.update(render(recolector))
    except KeyboardInterrupt:
        console.print("\n[dim]Saliendo...[/dim]")


if __name__ == "__main__":
    main()
