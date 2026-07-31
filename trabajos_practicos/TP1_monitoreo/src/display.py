"""
Gestor principal de la Interfaz de Usuario (TUI) para el Monitor (FASE 6).

Captura entradas de teclado no bloqueantes en Linux/POSIX (modo cbreak)
y compone las vistas renderizadas desde `vistas.py` sobre `rich.Live`.
"""

import queue
import select
import sys
import threading
import time
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

import vistas

# Mapeo de teclas de vistas (1-7 y letras clave)
VISTAS_MAP = {
    "1": "resumen", "r": "resumen",
    "2": "memoria", "m": "memoria",
    "3": "fds", "f": "fds",
    "4": "threads", "t": "threads",
    "5": "senales", "s": "senales",
    "6": "scheduling", "p": "scheduling",
    "7": "sistema", "g": "sistema",
}


class HiloTeclado(threading.Thread):
    """Hilo daemon para capturar teclas individuales en modo cbreak no bloqueante."""

    def __init__(self, cola_eventos):
        super().__init__(daemon=True, name="teclado-tui")
        self.cola = cola_eventos
        self.corriendo = True

    def run(self):
        try:
            import termios
            import tty
            fd = sys.stdin.fileno()
            viejos_atributos = termios.tcgetattr(fd)
        except Exception:
            return  # No hay TTY interactiva (ej. entorno de test sin terminal)

        try:
            tty.setcbreak(fd)
            while self.corriendo:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if r:
                    char = sys.stdin.read(1)
                    if char == "\x1b":  # Secuencia de escape (flechas)
                        r2, _, _ = select.select([sys.stdin], [], [], 0.02)
                        if r2:
                            seq = sys.stdin.read(2)
                            if seq == "[A":
                                char = "UP"
                            elif seq == "[B":
                                char = "DOWN"
                    self.cola.put(char)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, viejos_atributos)
            except Exception:
                pass


class MonitorTUI:
    """Clase principal que administra el estado de navegación y renderizado."""

    def __init__(self):
        self.vista_activa = "resumen"
        self.pid_seleccionado = None
        self.cursor_idx = 0
        self.filtro_texto = ""
        self.filtro_usuario = ""
        self.orden = "cpu"  # 'cpu', 'rss', 'pid'
        self.mostrar_ayuda = False

        self.cola_teclas = queue.Queue()
        self.hilo_teclado = HiloTeclado(self.cola_teclas)
        self.hilo_teclado.start()

    def procesar_teclas(self, procesos: list) -> bool:
        """Procesa las teclas encoladas. Devuelve False si se presionó 'q' (salir)."""
        while not self.cola_teclas.empty():
            try:
                tecla = self.cola_teclas.get_nowait()
            except queue.Empty:
                break

            if tecla == "q":
                return False
            elif tecla in ("h", "H"):
                self.mostrar_ayuda = not self.mostrar_ayuda
            elif tecla in VISTAS_MAP:
                self.vista_activa = VISTAS_MAP[tecla]
                self.mostrar_ayuda = False
            elif tecla in ("UP", "k"):
                self.cursor_idx = max(0, self.cursor_idx - 1)
            elif tecla in ("DOWN", "j"):
                self.cursor_idx = min(len(procesos) - 1, self.cursor_idx + 1) if procesos else 0
            elif tecla == "\r" or tecla == "\n":  # Enter
                if procesos and 0 <= self.cursor_idx < len(procesos):
                    self.pid_seleccionado = procesos[self.cursor_idx]["pid"]
            elif tecla == "c":
                modos = ["cpu", "rss", "pid"]
                self.orden = modos[(modos.index(self.orden) + 1) % len(modos)]

        # Actualizar pid_seleccionado por defecto si no hay ninguno fijado
        if procesos and (self.pid_seleccionado is None or not any(p["pid"] == self.pid_seleccionado for p in procesos)):
            if 0 <= self.cursor_idx < len(procesos):
                self.pid_seleccionado = procesos[self.cursor_idx]["pid"]

        return True

    def render_pie_analizadores(self, snapshot: dict, analizadores_info: list) -> Panel:
        """Pie de pantalla que muestra la salud y frescura de los 7 procesos analizadores."""
        txt = Text()
        txt.append("Analizadores: ", style="bold")
        ahora = time.time()

        for modulo, clave in analizadores_info:
            nombre = modulo.NOMBRE
            entrada = snapshot.get(nombre)
            if entrada is None:
                txt.append(f"{nombre}(--) ", style="yellow")
                continue
            edad = ahora - entrada["ts"]
            pid = entrada.get("pid", "?")
            estilo = "green" if edad < 15 else "bold red"
            txt.append(f"{nombre}[{pid}]{edad:.0f}s ", style=estilo)

        sub = f"Vista activa: {self.vista_activa.upper()} | PID fijado: {self.pid_seleccionado or 'Ninguno'} | Tecla 'h': Ayuda"
        return Panel(txt, border_style="dim", subtitle=sub)

    def render(self, snapshot: dict, verbose: bool, ultima_senal: str, analizadores_info: list):
        """Compone la vista según el estado actual."""
        if self.mostrar_ayuda:
            return vistas.render_ayuda()

        # Extraer datos de los analizadores
        e_resumen = snapshot.get("resumen")
        procesos = e_resumen["datos"] if e_resumen else []
        e_sistema = snapshot.get("sistema")
        sis_datos = e_sistema["datos"] if e_sistema else None

        p_sistema = vistas.render_sistema(sis_datos, verbose, ultima_senal)
        p_pie = self.render_pie_analizadores(snapshot, analizadores_info)

        # Renderizar la vista central elegida
        if self.vista_activa == "resumen":
            cuerpo = vistas.render_resumen(
                procesos, self.pid_seleccionado, self.filtro_texto,
                self.filtro_usuario, self.orden, verbose
            )
        elif self.vista_activa == "memoria":
            cuerpo = vistas.render_memoria(snapshot.get("memoria", {}).get("datos", {}), self.pid_seleccionado)
        elif self.vista_activa == "fds":
            cuerpo = vistas.render_fds(snapshot.get("fds", {}).get("datos", {}), self.pid_seleccionado)
        elif self.vista_activa == "threads":
            cuerpo = vistas.render_threads(snapshot.get("threads", {}).get("datos", {}), self.pid_seleccionado)
        elif self.vista_activa == "senales":
            cuerpo = vistas.render_senales(snapshot.get("senales", {}).get("datos", {}), self.pid_seleccionado)
        elif self.vista_activa == "scheduling":
            cuerpo = vistas.render_scheduling(snapshot.get("scheduling", {}).get("datos", {}), self.pid_seleccionado)
        elif self.vista_activa == "sistema":
            cuerpo = vistas.render_sistema(sis_datos, verbose, ultima_senal)
        else:
            cuerpo = vistas.render_resumen(procesos, self.pid_seleccionado, "", "", self.orden, verbose)

        return Group(p_sistema, cuerpo, p_pie)
