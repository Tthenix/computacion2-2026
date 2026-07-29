"""
Manejador de señales del monitor (FASE 3) — patrón self-pipe.

Señales que maneja el monitor cuando las RECIBE él mismo:
    SIGINT / SIGTERM -> shutdown limpio (salir del loop, terminar hijos, flush)
    SIGHUP           -> recargar config.json en caliente
    SIGUSR1          -> dump del snapshot actual a dump_<timestamp>.json
    SIGUSR2          -> toggle modo verbose
    SIGWINCH         -> repintar (terminal redimensionada) [opcional]

=== POR QUÉ SELF-PIPE Y NO SOLO UNA BANDERA ===
(pregunta típica de corrección)

Un handler de señal puede interrumpir tu programa EN CUALQUIER PUNTO, incluso en
medio de una operación. Por eso desde un handler solo se pueden llamar funciones
"async-signal-safe" (una lista corta del POSIX). print(), logging, malloc, casi
todo Python NO es seguro: si la señal llega justo cuando el intérprete estaba a
medio modificar una estructura, se corrompe.

Solución mínima: el handler solo baja una bandera (`self.ejecutando = False`) y el
loop principal la chequea. Funciona para "salir", pero tiene un problema: si el
loop está BLOQUEADO esperando (ej. en select/read/sleep largo), la bandera no se
mira hasta que el bloqueo termina. La señal "se siente tarde".

El **self-pipe** resuelve las dos cosas a la vez:
  1. Creamos un pipe (dos extremos: read_fd, write_fd).
  2. El handler hace UNA sola cosa async-signal-safe: os.write(write_fd, 1 byte).
  3. El loop principal, en vez de sleep(), hace select() sobre read_fd. Cuando
     llega la señal, el pipe se vuelve "legible" y select() DESPIERTA al instante.
Así convertimos una señal asíncrona (que puede llegar en cualquier momento) en un
evento de I/O ordinario que el loop atiende cuando está listo y seguro. El trabajo
pesado (recargar config, escribir el dump) se hace en el loop, NO en el handler.

Base conceptual: clase 5 (contenido.md y extra_manijas.md, "patrón self-pipe").
"""
import errno
import fcntl
import os
import signal


# Señales que nos interesan y su acción (el nombre se resuelve en el loop).
SENALES = {
    signal.SIGINT: "shutdown",
    signal.SIGTERM: "shutdown",
    signal.SIGHUP: "reload",
    signal.SIGUSR1: "dump",
    signal.SIGUSR2: "verbose",
}
# SIGWINCH puede no existir en algunas plataformas; se agrega si está.
if hasattr(signal, "SIGWINCH"):
    SENALES[signal.SIGWINCH] = "repaint"


class GestorSenales:
    def __init__(self):
        # 1) El pipe self-pipe. read_fd lo vigila el loop; write_fd lo usa el handler.
        self._read_fd, self._write_fd = os.pipe()

        # 2) Ambos extremos en modo NO bloqueante:
        #    - write_fd: si el pipe se llena (muchas señales), el os.write NO debe
        #      bloquear dentro del handler (sería catastrófico). Preferimos perder
        #      un byte antes que colgar el handler.
        #    - read_fd: para drenarlo sin bloquear cuando ya no queda nada.
        for fd in (self._read_fd, self._write_fd):
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # 3) Cola de señales recibidas. append() de un int es atómico en CPython
        #    (una sola operación de bytecode), así que es seguro desde el handler.
        self._cola = []

        self._registrar()

    def _registrar(self):
        """Asocia cada señal a nuestro handler crudo."""
        for sig in SENALES:
            signal.signal(sig, self._handler)

    # -----------------------------------------------------------------------
    # HANDLER: corre en contexto de señal -> mínimo y async-signal-safe
    # -----------------------------------------------------------------------
    def _handler(self, sig, frame):
        # Guardar qué señal llegó (append de int = atómico).
        self._cola.append(sig)
        # Despertar al loop escribiendo 1 byte al pipe. os.write es
        # async-signal-safe. Si el pipe está lleno o interrumpido, ignoramos:
        # ya hay un byte que va a despertar al loop igual.
        try:
            os.write(self._write_fd, b"\x00")
        except OSError as e:
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR):
                raise  # error inesperado

    # -----------------------------------------------------------------------
    # API para el loop principal
    # -----------------------------------------------------------------------
    @property
    def read_fd(self):
        """FD que el loop pasa a select() para despertarse cuando llega señal."""
        return self._read_fd

    def procesar_pendientes(self):
        """
        Drena el pipe y devuelve la lista de ACCIONES pendientes (str) en orden
        de llegada. Se llama desde el loop principal cuando select() indicó que
        read_fd es legible. Acá SÍ podemos hacer trabajo pesado: estamos en el
        flujo normal del programa, no en el handler.
        """
        # 1) Vaciar el pipe (los bytes son solo "despertadores", no llevan info).
        try:
            while os.read(self._read_fd, 4096):
                pass
        except OSError as e:
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise

        # 2) Traducir las señales encoladas a acciones.
        acciones = []
        while self._cola:
            sig = self._cola.pop(0)
            acciones.append(SENALES.get(sig, "desconocida"))
        return acciones

    def cerrar(self):
        """Cierra los extremos del pipe (cleanup al salir)."""
        for fd in (self._read_fd, self._write_fd):
            try:
                os.close(fd)
            except OSError:
                pass
