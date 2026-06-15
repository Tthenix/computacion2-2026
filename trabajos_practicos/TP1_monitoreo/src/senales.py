"""
Manejador de señales del monitor.  (se implementa en FASE 3)

Señales:
    SIGINT/SIGTERM -> shutdown limpio (terminar hijos, flush, persistir)
    SIGHUP         -> recargar config.json
    SIGUSR1        -> dump del snapshot a dump_<timestamp>.json
    SIGUSR2        -> toggle modo verbose
    SIGWINCH       -> repintar (opcional)

Patrón: self-pipe / signal.set_wakeup_fd para handlers async-signal-safe.
Base conceptual: clase_05_senales/servidor_signals.py
"""
