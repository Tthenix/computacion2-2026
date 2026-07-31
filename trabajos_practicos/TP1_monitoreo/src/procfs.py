"""
Helpers para parsear /proc por proceso (FASE 1 - Refactorizado para <300 líneas).

Toda la lectura de /proc por proceso pasa por acá.
Los lectores del sistema global (stat sistema, meminfo, loadavg, uptime, etc.)
fueron reubicados a `procfs_sistema.py` para cumplir la regla estricta de <300 líneas.
"""
import os

from procfs_sistema import (
    PROC, _a_int, leer_stat_sistema, leer_meminfo, leer_loadavg,
    leer_uptime, usuario_de_uid
)

_STAT_CAMPOS = [
    "state", "ppid", "pgrp", "session", "tty_nr", "tpgid", "flags",
    "minflt", "cminflt", "majflt", "cmajflt", "utime", "stime",
    "cutime", "cstime", "priority", "nice", "num_threads", "itrealvalue", "starttime"
]

POLITICAS_SCHED = {
    0: "OTHER", 1: "FIFO", 2: "RR", 3: "BATCH", 5: "IDLE", 6: "DEADLINE",
}

CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def listar_pids():
    """Devuelve la lista de PIDs vivos (entradas numéricas de /proc)."""
    pids = []
    try:
        for nombre in os.listdir(PROC):
            if nombre.isdigit():
                pids.append(int(nombre))
    except (FileNotFoundError, PermissionError):
        pass
    return pids


def leer_status(pid):
    """Parsea /proc/<pid>/status a un dict {clave: valor_str}."""
    datos = {}
    try:
        with open(f"{PROC}/{pid}/status", "r") as f:
            for linea in f:
                clave, sep, valor = linea.partition(":")
                if sep:
                    datos[clave.strip()] = valor.strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    return datos


def leer_stat(pid):
    """Parsea /proc/<pid>/stat manejando el comm entre paréntesis con espacios."""
    try:
        with open(f"{PROC}/{pid}/stat", "r") as f:
            contenido = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    return _parsear_stat(contenido)


def leer_stat_thread(pid, tid):
    """Parsea /proc/<pid>/task/<tid>/stat de un thread (LWP)."""
    try:
        with open(f"{PROC}/{pid}/task/{tid}/stat", "r") as f:
            contenido = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    return _parsear_stat(contenido)


def _parsear_stat(contenido):
    """Auxiliar interno para parsear contenido de stat."""
    abre = contenido.find("(")
    cierra = contenido.rfind(")")
    if abre == -1 or cierra == -1:
        return None

    pid_str = contenido[:abre].strip()
    comm = contenido[abre + 1:cierra]
    resto = contenido[cierra + 1:].split()

    datos = {"pid": int(pid_str), "comm": comm}
    for i, nombre in enumerate(_STAT_CAMPOS):
        if i < len(resto):
            datos[nombre] = resto[i] if nombre == "state" else _a_int(resto[i])

    datos["rt_priority"] = _a_int(resto[37]) if len(resto) > 37 else 0
    datos["policy"] = _a_int(resto[38]) if len(resto) > 38 else 0

    return datos


def leer_cmdline(pid):
    """Devuelve la línea de comandos de /proc/<pid>/cmdline."""
    try:
        with open(f"{PROC}/{pid}/cmdline", "rb") as f:
            crudo = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    if not crudo:
        return ""
    partes = [p.decode("utf-8", errors="replace") for p in crudo.split(b"\x00") if p]
    return " ".join(partes)


def leer_maps(pid):
    """Lee /proc/<pid>/maps y agrupa los segmentos de memoria."""
    cats = {"text_kb": 0, "data_kb": 0, "heap_kb": 0, "stack_kb": 0,
            "lib_kb": 0, "total_kb": 0, "n_segmentos": 0}
    try:
        with open(f"{PROC}/{pid}/maps", "r") as f:
            for linea in f:
                partes = linea.split()
                if len(partes) < 2:
                    continue
                rango = partes[0].split("-")
                if len(rango) != 2:
                    continue
                tam_kb = (int(rango[1], 16) - int(rango[0], 16)) // 1024
                perms = partes[1]
                path = partes[5] if len(partes) >= 6 else ""

                cats["total_kb"] += tam_kb
                cats["n_segmentos"] += 1

                if path == "[heap]":
                    cats["heap_kb"] += tam_kb
                elif path == "[stack]":
                    cats["stack_kb"] += tam_kb
                elif path.endswith(".so") or ".so." in path:
                    cats["lib_kb"] += tam_kb
                elif "x" in perms and path.startswith("/"):
                    cats["text_kb"] += tam_kb
                else:
                    cats["data_kb"] += tam_kb
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    return cats


def leer_fds(pid, limite=None):
    """Lista los file descriptors abiertos de /proc/<pid>/fd/."""
    base = f"{PROC}/{pid}/fd"
    lista = []
    try:
        nombres = os.listdir(base)
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    total = len(nombres)
    for nombre in sorted(nombres, key=lambda x: int(x) if x.isdigit() else 0):
        try:
            destino = os.readlink(f"{base}/{nombre}")
        except OSError:
            destino = "?"
        lista.append({"fd": nombre, "destino": destino, "tipo": _tipo_fd(destino)})
        if limite is not None and len(lista) >= limite:
            break
    return {"count": total, "lista": lista}


def _tipo_fd(destino):
    if destino.startswith("socket:"):
        return "socket"
    if destino.startswith("pipe:"):
        return "pipe"
    if destino.startswith("anon_inode:"):
        return "anon"
    if "/pts/" in destino or destino.startswith("/dev/tty"):
        return "tty"
    if destino.startswith("/dev/"):
        return "dev"
    if destino.startswith("/"):
        return "file"
    return "otro"


def listar_tids(pid):
    """Lista los TIDs (thread IDs) de /proc/<pid>/task/."""
    try:
        return [int(n) for n in os.listdir(f"{PROC}/{pid}/task") if n.isdigit()]
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return []


def leer_status_thread(pid, tid):
    """Parsea /proc/<pid>/task/<tid>/status."""
    datos = {}
    try:
        with open(f"{PROC}/{pid}/task/{tid}/status", "r") as f:
            for linea in f:
                clave, sep, valor = linea.partition(":")
                if sep:
                    datos[clave.strip()] = valor.strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    return datos
