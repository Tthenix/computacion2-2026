"""
Helpers de test: arman un /proc de MENTIRA en un directorio temporal y apuntan
los módulos a ese directorio (parcheando la constante PROC). Así los tests corren
en cualquier lado (incluso Windows), sin /proc real ni Docker.

Esto es justo lo que pide la consigna: "tests del parseo de /proc con archivos de
muestra".
"""
import os

import procfs
import procfs_sistema


def montar(tmp):
    """Apunta procfs y procfs_sistema al /proc falso en `tmp`."""
    procfs.PROC = tmp
    procfs_sistema.PROC = tmp


def _w(path, content, binary=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if binary else "w") as f:
        f.write(content)


def sistema(tmp,
            cpu="cpu 500 0 200 300 0 0 0\nbtime 1000\nprocs_running 1\nctxt 5\n",
            meminfo=("MemTotal: 2048 kB\nMemFree: 1024 kB\nMemAvailable: 1500 kB\n"
                     "Buffers: 10 kB\nCached: 100 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n"),
            loadavg="0.50 0.40 0.30 1/100 1234\n",
            uptime="100.0 50.0\n"):
    """Escribe /proc/stat, meminfo, loadavg, uptime de muestra."""
    _w(os.path.join(tmp, "stat"), cpu)
    _w(os.path.join(tmp, "meminfo"), meminfo)
    _w(os.path.join(tmp, "loadavg"), loadavg)
    _w(os.path.join(tmp, "uptime"), uptime)


def construir_stat(pid=1234, comm="a b)c", state="R", ppid=1000, utime=0, stime=0,
                   nice=0, threads=5, policy=0, rt_priority=0):
    """
    Arma una línea /proc/<pid>/stat de muestra. El comm por defecto tiene un
    espacio Y un paréntesis a propósito, para testear el parseo difícil.
    """
    resto = [state, str(ppid), "1234", "1234", "0", "-1", "0", "200", "0", "3",
             "0", str(utime), str(stime), "0", "0", "20", str(nice), str(threads),
             "0", "111"] + ["0"] * 22
    resto[37] = str(rt_priority)
    resto[38] = str(policy)
    return f"{pid} ({comm}) " + " ".join(resto) + "\n"


def construir_status(name="proc", ppid=1000, threads=5, uid=1000, rss=2048,
                     extra=""):
    return (f"Name:\t{name}\nState:\tR (running)\nPPid:\t{ppid}\n"
            f"Threads:\t{threads}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
            f"VmRSS:\t{rss} kB\n" + extra)


def proceso(tmp, pid, stat=None, status=None, cmdline=b"proc\x00", maps=None,
            tasks=None):
    """Crea /proc/<pid>/ con los archivos que se pasen."""
    d = os.path.join(tmp, str(pid))
    if stat is not None:
        _w(os.path.join(d, "stat"), stat)
    if status is not None:
        _w(os.path.join(d, "status"), status)
    if cmdline is not None:
        _w(os.path.join(d, "cmdline"), cmdline, binary=True)
    if maps is not None:
        _w(os.path.join(d, "maps"), maps)
    if tasks:
        for tid, tstat, tstatus in tasks:
            _w(os.path.join(d, "task", str(tid), "stat"), tstat)
            if tstatus is not None:
                _w(os.path.join(d, "task", str(tid), "status"), tstatus)
