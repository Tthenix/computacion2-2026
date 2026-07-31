"""
Helpers para leedores del sistema global desde /proc (procfs_sistema).

Extraído de procfs.py para respetar el límite estricto de 300 líneas por archivo.
Contiene: /proc/stat global, /proc/meminfo, /proc/loadavg, /proc/uptime y /etc/passwd.
"""
import os

PROC = "/proc"


def _a_int(valor):
    """Convierte a int; si no se puede, devuelve el string tal cual."""
    try:
        return int(valor)
    except (ValueError, TypeError):
        return valor


def leer_stat_sistema():
    """
    Lee /proc/stat y devuelve la info global del sistema.
    Primera línea 'cpu' es el acumulado de TODOS los cores desde el boot.
    """
    campos_cpu = ["user", "nice", "system", "idle", "iowait",
                  "irq", "softirq", "steal", "guest", "guest_nice"]
    resultado = {"cpu": {}, "btime": 0, "procs_running": 0,
                 "procs_blocked": 0, "ctxt": 0}
    try:
        with open(f"{PROC}/stat", "r") as f:
            for linea in f:
                partes = linea.split()
                if not partes:
                    continue
                clave = partes[0]
                if clave == "cpu":
                    valores = [int(x) for x in partes[1:]]
                    d = {}
                    for i, nombre in enumerate(campos_cpu):
                        d[nombre] = valores[i] if i < len(valores) else 0
                    d["total"] = sum(valores)
                    d["idle_all"] = d["idle"] + d["iowait"]
                    resultado["cpu"] = d
                elif clave == "btime":
                    resultado["btime"] = int(partes[1])
                elif clave == "procs_running":
                    resultado["procs_running"] = int(partes[1])
                elif clave == "procs_blocked":
                    resultado["procs_blocked"] = int(partes[1])
                elif clave == "ctxt":
                    resultado["ctxt"] = int(partes[1])
    except (FileNotFoundError, PermissionError):
        return resultado
    return resultado


def leer_meminfo():
    """Lee /proc/meminfo. Formato 'Clave: N kB'. Devuelve dict {clave: kB(int)}."""
    datos = {}
    try:
        with open(f"{PROC}/meminfo", "r") as f:
            for linea in f:
                clave, sep, valor = linea.partition(":")
                if sep:
                    datos[clave.strip()] = _a_int(valor.split()[0]) if valor.split() else 0
    except (FileNotFoundError, PermissionError):
        return datos
    return datos


def leer_loadavg():
    """Lee /proc/loadavg. Devuelve dict con load_1, load_5, load_15, etc."""
    try:
        with open(f"{PROC}/loadavg", "r") as f:
            partes = f.read().split()
        run_total = partes[3].split("/")
        return {
            "load_1": float(partes[0]),
            "load_5": float(partes[1]),
            "load_15": float(partes[2]),
            "procs_ejecutando": int(run_total[0]),
            "procs_total": int(run_total[1]),
        }
    except (FileNotFoundError, PermissionError, IndexError):
        return {"load_1": 0.0, "load_5": 0.0, "load_15": 0.0,
                "procs_ejecutando": 0, "procs_total": 0}


def leer_uptime():
    """Lee /proc/uptime. Devuelve los segundos de uptime (float)."""
    try:
        with open(f"{PROC}/uptime", "r") as f:
            return float(f.read().split()[0])
    except (FileNotFoundError, PermissionError, IndexError):
        return 0.0


_passwd_cache = None


def usuario_de_uid(uid):
    """Traduce un UID numérico al nombre de usuario leyendo /etc/passwd."""
    global _passwd_cache
    if _passwd_cache is None:
        _passwd_cache = {}
        try:
            with open("/etc/passwd", "r") as f:
                for linea in f:
                    partes = linea.split(":")
                    if len(partes) >= 3:
                        _passwd_cache[int(partes[2])] = partes[0]
        except (FileNotFoundError, PermissionError, ValueError):
            pass
    try:
        return _passwd_cache.get(int(uid), str(uid))
    except (ValueError, TypeError):
        return str(uid)
