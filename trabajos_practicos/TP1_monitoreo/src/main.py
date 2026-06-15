#!/usr/bin/env python3
"""
Entry point del monitor.

FASE 0: solo verifica el entorno — versión de Python y acceso a /proc.
En fases siguientes acá se va a levantar el recolector, los analizadores,
el agregador y el display.
"""
import os
import sys


def contar_procesos():
    """Cuenta cuántos PIDs hay en /proc (carpetas numéricas)."""
    return sum(1 for n in os.listdir("/proc") if n.isdigit())


def main():
    print("=== Monitor de Procesos — Fase 0 (setup) ===")
    print(f"Python: {sys.version.split()[0]}")
    try:
        n = contar_procesos()
        print(f"Procesos visibles en /proc: {n}")
        print("Entorno OK: /proc accesible.")
    except FileNotFoundError:
        print("ERROR: /proc no existe. ¿Estás en Linux/Docker?", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
