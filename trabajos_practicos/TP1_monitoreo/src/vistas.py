"""
Renderizadores puros con Rich para las 7 vistas del monitor (FASE 6).

Cada función recibe los datos del snapshot correspondiente y los parámetros
de navegación (pid_seleccionado, filtros, etc.) y devuelve un Panel o Tabla
listo para ser mostrado en la TUI.
"""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def _fmt_mb(kb: float) -> str:
    """Formatea kilobytes a MB con 1 decimal."""
    return f"{kb / 1024:.1f} MB"


def render_sistema(sis: dict, verbose: bool, ultima_senal: str) -> Panel:
    """Vista 7 / Panel Superior: Info global del sistema (CPU, Mem, Load)."""
    if sis is None:
        return Panel(
            Text("Esperando datos del analizador de sistema...", style="yellow"),
            title="Sistema (Vista 7)", border_style="cyan"
        )
    cpu = sis["cpu_desglose"]
    mem_usada = sis["mem_total_kb"] - sis["mem_disp_kb"]
    load = sis["load"]

    txt = Text()
    txt.append("CPU  ", style="bold")
    txt.append(f"{sis['cpu_uso']:.1f}% ", style="bold cyan")
    txt.append(f"(user {cpu['user']}% sys {cpu['system']}% idle {cpu['idle']}% iowait {cpu['iowait']}%) ")
    txt.append(f"{sis['ncpus']} cores\n")
    txt.append("MEM  ", style="bold")
    txt.append(f"{_fmt_mb(mem_usada)} / {_fmt_mb(sis['mem_total_kb'])} ")
    txt.append(f"cache {_fmt_mb(sis['cached_kb'])} swap {_fmt_mb(sis['swap_total_kb'] - sis['swap_libre_kb'])} / {_fmt_mb(sis['swap_total_kb'])}\n")
    txt.append("LOAD ", style="bold")
    txt.append(f"{load['load_1']}  {load['load_5']}  {load['load_15']}   ")
    txt.append("PROC ", style="bold")
    estados = " ".join(f"{k}:{v}" for k, v in sorted(sis["por_estado"].items()))
    txt.append(f"{sis['procs_total']} total ({estados}) ")
    z = sis["zombies"]
    txt.append(f"zombies:{z}", style="bold red" if z else "dim")

    sub = f"uptime {sis['uptime_seg'] / 3600:.1f} h"
    if verbose:
        sub += " | VERBOSE"
    if ultima_senal:
        sub += f" | última señal: {ultima_senal}"
    return Panel(txt, title="Sistema (Vista 7 · g)", subtitle=sub, border_style="cyan")


def filtrar_ordenar(procesos: list, filtro_texto: str, filtro_usuario: str,
                    orden: str) -> list:
    """
    Filtra y ordena la lista de procesos. Función PURA compartida por la vista
    Resumen (para dibujar) y por el display (para navegar): así el cursor ↑↓
    indexa EXACTAMENTE la misma lista que se ve en pantalla. Sin esto, el orden
    de navegación y el de dibujo se desincronizan y Enter selecciona otro PID.
    """
    res = procesos
    if filtro_texto:
        res = [p for p in res if filtro_texto.lower() in p["comando"].lower()]
    if filtro_usuario:
        res = [p for p in res if filtro_usuario.lower() in p["usuario"].lower()]
    if orden == "pid":
        res = sorted(res, key=lambda p: p["pid"])
    elif orden == "rss":
        res = sorted(res, key=lambda p: p["rss_kb"], reverse=True)
    else:  # 'cpu' por defecto
        res = sorted(res, key=lambda p: p["cpu"], reverse=True)
    return res


def render_resumen(
    procesos: list,
    cursor_idx: int,
    pin_pid: int,
    filtro_texto: str,
    filtro_usuario: str,
    orden: str,
    verbose: bool
) -> Table:
    """
    Vista 1: tabla resumen estilo top/htop.

    - cursor_idx: fila resaltada (se mueve con ↑↓). Indexa la lista YA filtrada
      y ordenada (la que devuelve filtrar_ordenar).
    - pin_pid: PID fijado con Enter; se marca con 📌 aunque cambie de posición.
    """
    tabla = Table(expand=True, header_style="bold green",
                  title=f"Vista 1: Resumen  (filtro:'{filtro_texto}' user:'{filtro_usuario}' orden:{orden})")
    tabla.add_column("SEL", width=3, justify="center")
    tabla.add_column("PID", justify="right", style="dim", width=7)
    tabla.add_column("PPID", justify="right", style="dim", width=7)
    tabla.add_column("USUARIO", width=10)
    tabla.add_column("EST", justify="center", width=3)
    tabla.add_column("CPU%", justify="right", width=6)
    tabla.add_column("RSS", justify="right", width=10)
    tabla.add_column("THR", justify="right", width=4)
    tabla.add_column("COMANDO", ratio=1, no_wrap=True)

    filtrados = filtrar_ordenar(procesos, filtro_texto, filtro_usuario, orden)

    limite = 40 if verbose else 20
    for i, p in enumerate(filtrados[:limite]):
        es_cursor = (i == cursor_idx)
        es_pin = (p["pid"] == pin_pid)
        marca = "📌" if es_pin else (">" if es_cursor else " ")
        est = p["estado"]
        estilo_est = {"R": "green", "Z": "bold red", "D": "yellow"}.get(est, "")
        estilo_fila = "on blue" if es_cursor else ""

        tabla.add_row(
            Text(marca, style="bold yellow"),
            str(p["pid"]), str(p["ppid"]), p["usuario"],
            Text(est, style=estilo_est), f"{p['cpu']:.1f}",
            _fmt_mb(p["rss_kb"]), str(p["threads"]), p["comando"],
            style=estilo_fila
        )
    return tabla


def render_memoria(mem_dict: dict, selected_pid: int) -> Panel:
    """Vista 2: Mapa y consumo de memoria por proceso."""
    if not mem_dict:
        return Panel(Text("Esperando datos de memoria...", style="yellow"), title="Vista 2: Memoria (m)")
    
    if selected_pid not in mem_dict:
        pids = sorted(mem_dict.keys())
        pid_target = pids[0] if pids else None
    else:
        pid_target = selected_pid

    if not pid_target or pid_target not in mem_dict:
        return Panel(Text("Seleccione un PID válido con Enter", style="yellow"), title="Vista 2: Memoria")

    info = mem_dict[pid_target]
    seg = info.get("segmentos", {})

    txt = Text()
    txt.append(f"Proceso: {info['comm']} (PID {pid_target})\n\n", style="bold yellow")
    txt.append(f"VmSize (Virtual):  {_fmt_mb(info['vmsize'])}\n")
    txt.append(f"VmRSS (Física):     {_fmt_mb(info['vmrss'])}\n", style="bold green")
    txt.append(f"VmHWM (Pico RSS):  {_fmt_mb(info['vmhwm'])}\n")
    txt.append(f"VmSwap (Swap):     {_fmt_mb(info['vmswap'])}\n")
    txt.append(f"Page Faults:       Minoras (RAM): {info['minflt']}  |  Mayores (Disco): {info['majflt']}\n\n", style="cyan")
    txt.append("Segmentos Agrupados (/proc/<pid>/maps):\n", style="bold")
    txt.append(f"  Text (Código):  {_fmt_mb(seg.get('text_kb', 0))}\n")
    txt.append(f"  Data (Datos):   {_fmt_mb(seg.get('data_kb', 0))}\n")
    txt.append(f"  Heap (Pila D.): {_fmt_mb(seg.get('heap_kb', 0))}\n")
    txt.append(f"  Stack (Pila):   {_fmt_mb(seg.get('stack_kb', 0))}\n")
    txt.append(f"  Libs (.so):     {_fmt_mb(seg.get('lib_kb', 0))}\n")
    txt.append(f"  Total Mapeado:  {_fmt_mb(seg.get('total_kb', 0))} en {seg.get('n_segmentos', 0)} segmentos")

    return Panel(txt, title=f"Vista 2: Memoria — PID {pid_target}", border_style="green")


def render_fds(fds_dict: dict, selected_pid: int) -> Panel:
    """Vista 3: File Descriptors abiertos."""
    if not fds_dict:
        return Panel(Text("Esperando datos de FDs...", style="yellow"), title="Vista 3: File Descriptors (f)")

    pid_target = selected_pid if selected_pid in fds_dict else next(iter(fds_dict.keys()), None)
    if not pid_target or pid_target not in fds_dict:
        return Panel(Text("Seleccione un PID en Resumen con Enter", style="yellow"), title="Vista 3: File Descriptors")

    info = fds_dict[pid_target]
    tabla = Table(title=f"FDs abiertos por {info['comm']} (PID {pid_target}) — Total: {info['count']}", expand=True)
    tabla.add_column("FD", justify="right", width=6)
    tabla.add_column("TIPO", width=10, style="cyan")
    tabla.add_column("DESTINO (symlink)", ratio=1)

    for item in info.get("lista", []):
        tabla.add_row(str(item["fd"]), item["tipo"], item["destino"])

    return Panel(tabla, title=f"Vista 3: File Descriptors — PID {pid_target}", border_style="magenta")


def render_threads(threads_dict: dict, selected_pid: int) -> Panel:
    """Vista 4: Threads / LWPs del proceso."""
    if not threads_dict:
        return Panel(Text("Esperando datos de Threads...", style="yellow"), title="Vista 4: Threads / LWPs (t)")

    pid_target = selected_pid if selected_pid in threads_dict else next(iter(threads_dict.keys()), None)
    if not pid_target or pid_target not in threads_dict:
        return Panel(Text("Seleccione un PID en Resumen con Enter", style="yellow"), title="Vista 4: Threads")

    info = threads_dict[pid_target]
    tabla = Table(title=f"Hilos (LWPs) de {info['comm']} (PID {pid_target}) — Total: {info['count']}", expand=True)
    tabla.add_column("TID", justify="right", width=8, style="dim")
    tabla.add_column("NOMBRE", width=16)
    tabla.add_column("ESTADO", justify="center", width=8)
    tabla.add_column("CPU%", justify="right", width=6)
    tabla.add_column("CTXT VOL (I/O)", justify="right", width=16)
    tabla.add_column("CTXT INVOL (Quantum)", justify="right", width=20)

    # Ordenar por CPU% desc (el hilo más activo arriba).
    hilos = sorted(info.get("lista", []), key=lambda t: t.get("cpu", 0), reverse=True)
    for t in hilos:
        est = t["estado"]
        estilo_est = {"R": "green", "Z": "bold red", "D": "yellow"}.get(est, "")
        tabla.add_row(
            str(t["tid"]), t["nombre"], Text(est, style=estilo_est),
            f"{t.get('cpu', 0.0):.1f}",
            str(t["vol_ctxt"]), str(t["nonvol_ctxt"])
        )

    return Panel(tabla, title=f"Vista 4: Threads / LWPs — PID {pid_target}", border_style="blue")


def render_senales(senales_dict: dict, selected_pid: int) -> Panel:
    """Vista 5: Máscaras de señales."""
    if not senales_dict:
        return Panel(Text("Esperando datos de señales...", style="yellow"), title="Vista 5: Máscaras de Señales (s)")

    pid_target = selected_pid if selected_pid in senales_dict else next(iter(senales_dict.keys()), None)
    if not pid_target or pid_target not in senales_dict:
        return Panel(Text("Seleccione un PID en Resumen con Enter", style="yellow"), title="Vista 5: Señales")

    info = senales_dict[pid_target]
    txt = Text()
    txt.append(f"Máscaras Hexadecimales (64-bit) — {info['comm']} (PID {pid_target})\n\n", style="bold yellow")
    txt.append(f"SigBlk (Bloqueadas):   {info.get('SigBlk', '0')}\n")
    txt.append(f"SigIgn (Ignoradas):    {info.get('SigIgn', '0')}\n")
    txt.append(f"SigCgt (Con Handler):  {info.get('SigCgt', '0')}\n")
    txt.append(f"SigPnd (Pend. Thread): {info.get('SigPnd', '0')}\n")
    txt.append(f"ShdPnd (Pend. Proceso):{info.get('ShdPnd', '0')}\n\n")
    txt.append("(En Fase 8 estas máscaras se decodifican bit a bit a nombres de señales POSIX)", style="dim")

    return Panel(txt, title=f"Vista 5: Señales — PID {pid_target}", border_style="yellow")


def render_scheduling(sched_dict: dict, selected_pid: int) -> Panel:
    """Vista 6: Parámetros de Scheduling del Kernel."""
    if not sched_dict:
        return Panel(Text("Esperando datos de scheduling...", style="yellow"), title="Vista 6: Scheduling (p)")

    pid_target = selected_pid if selected_pid in sched_dict else next(iter(sched_dict.keys()), None)
    if not pid_target or pid_target not in sched_dict:
        return Panel(Text("Seleccione un PID en Resumen con Enter", style="yellow"), title="Vista 6: Scheduling")

    info = sched_dict[pid_target]
    txt = Text()
    txt.append(f"Planificación del Kernel — {info['comm']} (PID {pid_target})\n\n", style="bold yellow")
    txt.append(f"Política (Policy):     {info['policy']}\n", style="bold cyan")
    txt.append(f"Prioridad Dinámica:    {info['priority']}\n")
    txt.append(f"Valor Nice:            {info['nice']}\n")
    txt.append(f"Prioridad Real-Time:   {info['rt_priority']}\n")
    txt.append(f"Afinidad CPU:          {info['affinity']}\n")
    txt.append(f"PGID / SID:            {info['pgid']} / {info['sid']}\n\n")
    txt.append(f"Context Switches:      Voluntarios (I/O): {info['vol_ctxt']} | Involuntarios: {info['nonvol_ctxt']}\n")

    return Panel(txt, title=f"Vista 6: Scheduling — PID {pid_target}", border_style="cyan")


def render_ayuda() -> Panel:
    """Overlay / Pantalla de ayuda con todos los atajos de teclado."""
    txt = Text()
    txt.append("TECLAS Y ATAJOS DE NAVEGACIÓN EN LA TUI\n\n", style="bold yellow")
    txt.append("1 .. 7 / r,m,f,t,s,p,g : Cambiar Vista Activa\n", style="bold green")
    txt.append("  1/r: Resumen | 2/m: Memoria | 3/f: FDs | 4/t: Threads\n")
    txt.append("  5/s: Señales | 6/p: Scheduling | 7/g: Sistema Global\n\n")
    txt.append("↑ / ↓  o  k / j       : Mover cursor de selección en la tabla\n")
    txt.append("Enter                 : Fijar/Pin PID seleccionado para ver sus detalles\n")
    txt.append("/                     : Ingresar filtro de texto por comando\n")
    txt.append("u                     : Ingresar filtro por usuario\n")
    txt.append("c                     : Alternar ordenamiento (CPU / RSS / PID)\n")
    txt.append("+ / -                 : Incrementar / Decrementar intervalo del analizador activo\n")
    txt.append("h                     : Mostrar / Ocultar esta pantalla de ayuda\n")
    txt.append("q                     : Salir del monitor limpiamente\n")
    return Panel(txt, title="Ayuda (Presione cualquier tecla para cerrar)", border_style="bold yellow")
