#!/usr/bin/env python3
"""
Ejercicio 5 (obligatorio) - Servidor que responde a señales.

Uso:
    python3 servidor_signals.py

Señales (desde otra terminal, reemplazá <pid> por el que imprime el server):
    kill -HUP  <pid>   -> Recargar configuración
    kill -USR1 <pid>   -> Mostrar estadísticas
    kill -USR2 <pid>   -> Rotar logs (simulado)
    kill       <pid>   -> Shutdown limpio (SIGTERM)
    Ctrl+C             -> Shutdown limpio (SIGINT)

NOTA: SIGHUP/SIGUSR1/SIGUSR2 son señales POSIX. Esto corre en Linux
(o WSL/Docker), NO en Windows nativo.
"""
import signal
import time
import os


class Servidor:
    def __init__(self):
        self.ejecutando = True
        self.config = {"max_conexiones": 100, "timeout": 30}
        self.stats = {"requests": 0, "errores": 0, "inicio": time.time()}
        self.log_seq = 0  # contador de rotaciones de log

        self._registrar_manejadores()

    def _registrar_manejadores(self):
        # Cada señal queda asociada a un handler. El kernel interrumpe el
        # loop principal y ejecuta la función cuando llega la señal.
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGHUP, self._reload_config)
        signal.signal(signal.SIGUSR1, self._mostrar_stats)
        signal.signal(signal.SIGUSR2, self._rotar_logs)

    # --- Handlers -----------------------------------------------------------

    def _shutdown(self, sig, frame):
        nombre = signal.Signals(sig).name
        print(f"\n[{nombre}] Iniciando shutdown...")
        # Solo bajamos la bandera: el cleanup real lo hace run() al salir
        # del loop. Mantiene el handler corto (async-signal-safe).
        self.ejecutando = False

    def _reload_config(self, sig, frame):
        print("\n[SIGHUP] Recargando configuración...")
        # Simula releer un archivo de config en caliente.
        self.config["max_conexiones"] += 10
        self.config["recargado"] = time.ctime()
        print(f"[SIGHUP] Nueva config: {self.config}")

    def _mostrar_stats(self, sig, frame):
        uptime = time.time() - self.stats["inicio"]
        print("\n[SIGUSR1] === Estadísticas ===")
        print(f"  Uptime:   {uptime:.1f}s")
        print(f"  Requests: {self.stats['requests']}")
        print(f"  Errores:  {self.stats['errores']}")
        print(f"  Config:   {self.config}")

    def _rotar_logs(self, sig, frame):
        self.log_seq += 1
        print("\n[SIGUSR2] Rotando logs...")
        print(f"[SIGUSR2] Logs rotados a server.log.{int(time.time())} "
              f"(rotación #{self.log_seq})")

    # --- Trabajo ------------------------------------------------------------

    def procesar_request(self):
        """Simula procesar una request."""
        self.stats["requests"] += 1
        time.sleep(0.1)
        if self.stats["requests"] % 10 == 0:
            self.stats["errores"] += 1

    def run(self):
        pid = os.getpid()
        print(f"Servidor iniciado (PID {pid})")
        print("Comandos disponibles:")
        print(f"  kill -HUP  {pid}   -> Recargar config")
        print(f"  kill -USR1 {pid}   -> Ver stats")
        print(f"  kill -USR2 {pid}   -> Rotar logs")
        print(f"  kill       {pid}   -> Shutdown")
        print()

        while self.ejecutando:
            self.procesar_request()

        # Cleanup limpio antes de salir
        print("Realizando cleanup...")
        time.sleep(0.5)
        print(f"Servidor terminado. Requests procesadas: {self.stats['requests']}")


if __name__ == "__main__":
    Servidor().run()
