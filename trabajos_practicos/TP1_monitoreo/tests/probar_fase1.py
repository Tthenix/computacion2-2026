#!/usr/bin/env python3
"""
Verificación Fase 1: imprime tabla PID | estado | threads | comando
leyendo /proc a mano. Comparar con `ps -e` o `ps aux`.

Correr DENTRO del contenedor:
    python3 tests/probar_fase1.py
"""
import os
import sys

# permitir importar src/ sin instalar nada
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import procfs  # noqa: E402


def main():
    pids = sorted(procfs.listar_pids())
    print(f"{'PID':>7}  {'EST':>3}  {'THR':>4}  COMANDO")
    print("-" * 60)

    for pid in pids:
        stat = procfs.leer_stat(pid)
        if stat is None:
            continue  # murió mientras lo leíamos

        status = procfs.leer_status(pid)
        threads = status.get("Threads", "?") if status else "?"

        cmd = procfs.leer_cmdline(pid)
        if not cmd:
            # kernel thread: sin cmdline -> usar comm entre corchetes
            cmd = f"[{stat['comm']}]"

        print(f"{pid:>7}  {stat['state']:>3}  {threads:>4}  {cmd[:60]}")

    print("-" * 60)
    print(f"Total procesos: {len(pids)}")
    print("Comparar con:  ps -e --no-headers | wc -l")


if __name__ == "__main__":
    main()
