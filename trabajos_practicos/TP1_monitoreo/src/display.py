"""
Gestor principal de la Interfaz de Usuario (TUI) para el Monitor (FASE 6).

Captura entradas de teclado no bloqueantes en Linux/POSIX (modo cbreak) en un
hilo interno, mantiene el estado de navegación (vista activa, cursor, pin,
filtros, orden) y compone las 7 vistas desde `vistas.py` sobre `rich.Live`.

Modelo de selección (según la consigna):
  - CURSOR: fila resaltada, se mueve con ↑↓. Indexa la lista YA filtrada/ordenada.
  - PIN:    con Enter se fija el PID del cursor; los paneles de detalle lo siguen
            aunque cambie de posición en la lista (se marca con 📌).
"""

import queue
import select
import sys
import threading
import time
from rich.console import Group
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

    # Flechas: ESC [ A/B/C/D  (modo normal) o ESC O A/B/C/D (modo "application").
    _FLECHAS = {0x41: "UP", 0x42: "DOWN", 0x43: "RIGHT", 0x44: "LEFT"}

    def run(self):
        try:
            import os
            import termios
            import tty
            fd = sys.stdin.fileno()
            viejos_atributos = termios.tcgetattr(fd)
        except Exception:
            return  # No hay TTY interactiva (ej. entorno de test sin terminal)

        try:
            tty.setcbreak(fd)
            while self.corriendo:
                r, _, _ = select.select([fd], [], [], 0.1)
                if not r:
                    continue
                try:
                    data = os.read(fd, 64)   # bytes crudos: robusto para secuencias de escape
                except OSError:
                    continue
                if data:
                    self._parsear(data)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, viejos_atributos)
            except Exception:
                pass

    def _parsear(self, data: bytes):
        """Convierte los bytes leídos en tokens ('UP', 'q', '\\r', ...) para la cola."""
        i, n = 0, len(data)
        while i < n:
            b = data[i]
            if b == 0x1b:  # ESC: puede ser flecha o Escape solo
                if i + 2 < n and data[i + 1] in (0x5b, 0x4f):  # '[' u 'O'
                    self.cola.put(self._FLECHAS.get(data[i + 2], "ESC"))
                    i += 3
                    continue
                self.cola.put("ESC")
                i += 1
                continue
            ch = bytes([b]).decode("utf-8", "ignore")
            if ch:
                self.cola.put(ch)
            i += 1


class MonitorTUI:
    """Administra el estado de navegación y compone el render."""

    def __init__(self):
        self.vista_activa = "resumen"
        self.cursor_idx = 0            # fila resaltada (sobre la lista filtrada/ordenada)
        self.pin_pid = None           # PID fijado con Enter (los detalles lo siguen)
        self.pid_objetivo = None      # PID que muestran los paneles de detalle
        self.filtro_texto = ""        # filtro por comando (tecla /)
        self.filtro_usuario = ""      # filtro por usuario (tecla u)
        self.orden = "cpu"            # 'cpu', 'rss', 'pid'
        self.mostrar_ayuda = False
        self.modo_captura = None      # None | "texto" | "usuario" (escribiendo un filtro)

        self.cola_teclas = queue.Queue()
        self.hilo_teclado = HiloTeclado(self.cola_teclas)
        self.hilo_teclado.start()

    # -----------------------------------------------------------------------
    # Entrada de teclado
    # -----------------------------------------------------------------------
    def _tecla_captura(self, tecla):
        """Maneja una tecla mientras se escribe un filtro (modo captura)."""
        campo = "filtro_texto" if self.modo_captura == "texto" else "filtro_usuario"
        if tecla in ("\r", "\n"):          # Enter: confirmar
            self.modo_captura = None
        elif tecla == "ESC":               # Escape: cancelar y limpiar ese filtro
            setattr(self, campo, "")
            self.modo_captura = None
        elif tecla in ("\x7f", "\b"):      # Backspace: borrar último char
            setattr(self, campo, getattr(self, campo)[:-1])
        elif tecla in ("UP", "DOWN"):      # ignorar flechas mientras se escribe
            pass
        elif len(tecla) == 1 and tecla.isprintable():
            setattr(self, campo, getattr(self, campo) + tecla)

    def procesar_teclas(self, procesos: list) -> bool:
        """Procesa las teclas encoladas. Devuelve False si se pidió salir (q)."""
        while not self.cola_teclas.empty():
            try:
                tecla = self.cola_teclas.get_nowait()
            except queue.Empty:
                break

            # Si estamos escribiendo un filtro, todo va al buffer.
            if self.modo_captura:
                self._tecla_captura(tecla)
                continue

            if tecla == "q":
                return False
            elif tecla in ("h", "H", "?"):
                self.mostrar_ayuda = not self.mostrar_ayuda
            elif tecla == "/":
                self.modo_captura = "texto"
                self.filtro_texto = ""
            elif tecla == "u":
                self.modo_captura = "usuario"
                self.filtro_usuario = ""
            elif tecla in VISTAS_MAP:
                self.vista_activa = VISTAS_MAP[tecla]
                self.mostrar_ayuda = False
            elif tecla in ("UP", "k"):
                self.cursor_idx = max(0, self.cursor_idx - 1)
            elif tecla in ("DOWN", "j"):
                self.cursor_idx += 1
            elif tecla in ("\r", "\n"):    # Enter: fijar/soltar pin en el cursor
                self._toggle_pin(procesos)
            elif tecla == "c":
                modos = ["cpu", "rss", "pid"]
                self.orden = modos[(modos.index(self.orden) + 1) % len(modos)]

        # Recalcular cursor/pin/objetivo sobre la MISMA lista que se dibuja.
        visibles = vistas.filtrar_ordenar(
            procesos, self.filtro_texto, self.filtro_usuario, self.orden)
        if visibles:
            self.cursor_idx = max(0, min(self.cursor_idx, len(visibles) - 1))
            pid_cursor = visibles[self.cursor_idx]["pid"]
        else:
            self.cursor_idx = 0
            pid_cursor = None
        # Los detalles siguen al pin si hay; si no, al cursor.
        self.pid_objetivo = self.pin_pid if self.pin_pid is not None else pid_cursor
        return True

    def _toggle_pin(self, procesos):
        visibles = vistas.filtrar_ordenar(
            procesos, self.filtro_texto, self.filtro_usuario, self.orden)
        if not visibles or not (0 <= self.cursor_idx < len(visibles)):
            return
        pid_cursor = visibles[self.cursor_idx]["pid"]
        # Enter sobre el ya fijado => soltar; si no, fijar el del cursor.
        self.pin_pid = None if self.pin_pid == pid_cursor else pid_cursor

    # -----------------------------------------------------------------------
    # Pie de estado
    # -----------------------------------------------------------------------
    def render_pie(self, snapshot: dict, analizadores_info: list) -> Panel:
        txt = Text()
        txt.append("Analizadores: ", style="bold")
        ahora = time.time()
        for modulo, _clave in analizadores_info:
            nombre = modulo.NOMBRE
            entrada = snapshot.get(nombre)
            if entrada is None:
                txt.append(f"{nombre}(--) ", style="yellow")
                continue
            edad = ahora - entrada["ts"]
            pid = entrada.get("pid", "?")
            estilo = "green" if edad < 15 else "bold red"
            txt.append(f"{nombre}[{pid}]{edad:.0f}s ", style=estilo)

        if self.modo_captura:
            campo = self.filtro_texto if self.modo_captura == "texto" else self.filtro_usuario
            etiqueta = "comando" if self.modo_captura == "texto" else "usuario"
            sub = f"FILTRO {etiqueta}: {campo}_   (Enter=aplicar · Esc=cancelar)"
        else:
            sub = (f"vista: {self.vista_activa.upper()} | pin: {self.pin_pid or '—'} | "
                   f"orden: {self.orden} | h:ayuda  /:filtro  u:usuario  c:orden  q:salir")
        return Panel(txt, border_style="dim", subtitle=sub)

    # -----------------------------------------------------------------------
    # Render principal
    # -----------------------------------------------------------------------
    def render(self, snapshot: dict, verbose: bool, ultima_senal: str, analizadores_info: list):
        if self.mostrar_ayuda:
            return vistas.render_ayuda()

        e_resumen = snapshot.get("resumen")
        procesos = e_resumen["datos"] if e_resumen else []
        e_sistema = snapshot.get("sistema")
        sis_datos = e_sistema["datos"] if e_sistema else None

        p_sistema = vistas.render_sistema(sis_datos, verbose, ultima_senal)
        p_pie = self.render_pie(snapshot, analizadores_info)
        pid = self.pid_objetivo

        if self.vista_activa == "resumen":
            cuerpo = vistas.render_resumen(
                procesos, self.cursor_idx, self.pin_pid,
                self.filtro_texto, self.filtro_usuario, self.orden, verbose)
        elif self.vista_activa == "memoria":
            cuerpo = vistas.render_memoria(self._datos(snapshot, "memoria"), pid)
        elif self.vista_activa == "fds":
            cuerpo = vistas.render_fds(self._datos(snapshot, "fds"), pid)
        elif self.vista_activa == "threads":
            cuerpo = vistas.render_threads(self._datos(snapshot, "threads"), pid)
        elif self.vista_activa == "senales":
            cuerpo = vistas.render_senales(self._datos(snapshot, "senales"), pid)
        elif self.vista_activa == "scheduling":
            cuerpo = vistas.render_scheduling(self._datos(snapshot, "scheduling"), pid)
        else:  # sistema
            cuerpo = vistas.render_sistema(sis_datos, verbose, ultima_senal)

        return Group(p_sistema, cuerpo, p_pie)

    @staticmethod
    def _datos(snapshot, clave):
        """Extrae snapshot[clave]['datos'] o {} si el analizador aún no escribió."""
        entrada = snapshot.get(clave)
        return entrada["datos"] if entrada else {}
