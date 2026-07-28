"""
Helpers para parsear /proc a mano (FASE 1).

Toda la lectura de /proc del monitor pasa por acá. Ningún otro módulo abre
archivos de /proc directamente: si mañana cambia el formato de un archivo,
se toca en un solo lugar.

Convención de diseño:
    - Cada función devuelve un dict (o lista) con datos ya parseados.
    - Si un proceso desaparece mientras lo leemos (murió entre listar y leer),
      devolvemos None o {} en vez de explotar. Esto es CLAVE: /proc es volátil,
      un PID puede dejar de existir en cualquier momento (race inherente al SO).

Referencia: man 5 proc.
"""
import os


PROC = "/proc"


# ---------------------------------------------------------------------------
# Listado de PIDs
# ---------------------------------------------------------------------------
def listar_pids():
    """
    Devuelve la lista de PIDs vivos: las carpetas de /proc cuyo nombre es
    numérico. /proc también tiene entradas no-numéricas (self, stat, meminfo,
    cpuinfo...) que hay que filtrar.
    """
    pids = []
    for nombre in os.listdir(PROC):
        if nombre.isdigit():
            pids.append(int(nombre))
    return pids


# ---------------------------------------------------------------------------
# /proc/<pid>/status  → líneas "Clave:\tvalor"
# ---------------------------------------------------------------------------
def leer_status(pid):
    """
    Parsea /proc/<pid>/status. Formato: una línea por campo, "Clave:\\tvalor".
    Ejemplo:
        Name:   bash
        State:  S (sleeping)
        Pid:    1234
        PPid:   1000
        Uid:    1000    1000    1000    1000
        Threads:        1
        VmRSS:  4096 kB
        SigBlk: 0000000000010000

    Devuelve un dict {clave: valor_str}. El valor queda como string crudo;
    quien lo use decide cómo interpretarlo (int, hex, primer campo, etc.).
    Es el archivo más cómodo de /proc porque ya viene etiquetado.
    """
    datos = {}
    try:
        with open(f"{PROC}/{pid}/status", "r") as f:
            for linea in f:
                # partition corta en el PRIMER ":" — robusto aunque el valor
                # tenga otros ":" adentro.
                clave, sep, valor = linea.partition(":")
                if sep:  # línea válida (tenía ":")
                    datos[clave.strip()] = valor.strip()
    except (FileNotFoundError, ProcessLookupError):
        # El proceso murió entre que lo listamos y lo leímos. Normal en /proc.
        return None
    except PermissionError:
        return None
    return datos


# ---------------------------------------------------------------------------
# /proc/<pid>/stat  → campos separados por espacio, POSICIONALES
# ---------------------------------------------------------------------------
#
# Este es el archivo traicionero. Formato (campos 1-indexados como en man proc):
#
#   1  pid          4  ppid        14 utime      18 priority
#   2  comm         5  pgrp        15 stime      19 nice
#   3  state        6  session     ...          20 num_threads
#                   7  tty_nr                    22 starttime
#
# El PROBLEMA: el campo 2 (comm, el nombre del ejecutable) va entre paréntesis
# y PUEDE contener espacios y hasta paréntesis:
#       1234 (mi proceso (raro)) S 1000 ...
# Si hacés un split(" ") ingenuo, todo se corre. La solución canónica:
#   - el pid es todo lo que hay antes del PRIMER "("
#   - el comm es lo que hay entre el primer "(" y el ÚLTIMO ")"
#   - el resto (state en adelante) se splitea normal DESPUÉS del último ")"
# ---------------------------------------------------------------------------

# Nombres de los campos DESPUÉS de comm, en orden. Índice 0 = campo 3 (state).
# (Solo mapeo los que usa el TP; el resto no hace falta nombrarlos.)
_STAT_CAMPOS = [
    "state",        # 3   R/S/D/T/Z/...
    "ppid",         # 4
    "pgrp",         # 5   PGID
    "session",      # 6   SID
    "tty_nr",       # 7
    "tpgid",        # 8
    "flags",        # 9
    "minflt",       # 10  minor page faults
    "cminflt",      # 11
    "majflt",       # 12  major page faults
    "cmajflt",      # 13
    "utime",        # 14  jiffies en user mode
    "stime",        # 15  jiffies en kernel mode
    "cutime",       # 16
    "cstime",       # 17
    "priority",     # 18
    "nice",         # 19
    "num_threads",  # 20
    "itrealvalue",  # 21
    "starttime",    # 22  jiffies desde el boot
]


def leer_stat(pid):
    """
    Parsea /proc/<pid>/stat manejando el comm entre paréntesis con espacios.

    Devuelve dict con: pid, comm, state, ppid, pgrp, session, minflt, majflt,
    utime, stime, priority, nice, num_threads, starttime, y todos los de
    _STAT_CAMPOS. Los numéricos se convierten a int; los que fallan quedan str.

    Los campos de scheduling avanzado (rt_priority campo 40, policy campo 41)
    los agrego indexados por posición porque están más allá de _STAT_CAMPOS.
    """
    try:
        with open(f"{PROC}/{pid}/stat", "r") as f:
            contenido = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    # 1) pid = antes del primer "("
    # 2) comm = entre primer "(" y último ")"
    # 3) resto = después del último ")"
    abre = contenido.find("(")
    cierra = contenido.rfind(")")
    if abre == -1 or cierra == -1:
        return None

    pid_str = contenido[:abre].strip()
    comm = contenido[abre + 1:cierra]                # nombre real, con espacios si los tiene
    resto = contenido[cierra + 1:].split()           # ['S', '1000', '1000', ...]

    datos = {"pid": int(pid_str), "comm": comm}

    # Mapear resto[i] al nombre de _STAT_CAMPOS[i]
    for i, nombre in enumerate(_STAT_CAMPOS):
        if i < len(resto):
            valor = resto[i]
            if nombre == "state":
                datos[nombre] = valor            # 'R', 'S', ... queda string
            else:
                datos[nombre] = _a_int(valor)

    # Campos de scheduling más allá de _STAT_CAMPOS (posición en 'resto'):
    #   resto está 0-indexado empezando en el campo 3 (state).
    #   => campo N de man proc  ->  índice (N - 3) en resto.
    # rt_priority = campo 40 -> índice 37 ; policy = campo 41 -> índice 38.
    datos["rt_priority"] = _a_int(resto[37]) if len(resto) > 37 else 0
    datos["policy"] = _a_int(resto[38]) if len(resto) > 38 else 0

    return datos


# ---------------------------------------------------------------------------
# /proc/<pid>/cmdline  → argumentos separados por '\0'
# ---------------------------------------------------------------------------
def leer_cmdline(pid):
    """
    Devuelve el comando completo con argumentos. cmdline usa '\\0' (byte nulo)
    como separador de argv, y termina en '\\0'. Ejemplo crudo:
        python3\\x00-u\\x00script.py\\x00

    Si está vacío (cmdline vacío) es un proceso de kernel (kthread): en ese caso
    el "comando" real es el comm de stat entre corchetes, ej. [kworker/0:1].
    Acá devolvemos "" y quien llama decide usar el comm como fallback.
    """
    try:
        with open(f"{PROC}/{pid}/cmdline", "rb") as f:
            crudo = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    if not crudo:
        return ""  # kernel thread: sin cmdline

    # split por '\0', descartar el vacío final, unir con espacios.
    partes = crudo.split(b"\x00")
    partes = [p.decode("utf-8", errors="replace") for p in partes if p]
    return " ".join(partes)


# ===========================================================================
# LECTORES DEL SISTEMA GLOBAL (FASE 2) — no son por-proceso
# ===========================================================================

def leer_stat_sistema():
    """
    Lee /proc/stat y devuelve la info global del sistema.

    La primera línea 'cpu' es el acumulado de TODOS los cores desde el boot,
    en jiffies, repartido por modo:
        cpu  user nice system idle iowait irq softirq steal guest guest_nice

    Devuelve:
        {
          'cpu': {'user':N,'nice':N,'system':N,'idle':N,'iowait':N, ...,
                  'total': suma_de_todos, 'idle_all': idle+iowait},
          'btime': segundos epoch del boot,
          'procs_running': N, 'procs_blocked': N,
          'ctxt': switches totales,
        }
    Igual que en un proceso: el CPU% global se calcula con el DELTA de estos
    acumulados entre dos lecturas (ver recolector).
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
                if clave == "cpu":  # línea agregada de todos los cores
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
    """
    Lee /proc/meminfo. Formato 'Clave:   N kB'. Devuelve dict {clave: kB(int)}.
    Claves útiles: MemTotal, MemFree, MemAvailable, Buffers, Cached, SwapTotal,
    SwapFree.
    """
    datos = {}
    try:
        with open(f"{PROC}/meminfo", "r") as f:
            for linea in f:
                clave, sep, valor = linea.partition(":")
                if sep:
                    # valor viene como '  4096 kB' -> tomar el número
                    datos[clave.strip()] = _a_int(valor.split()[0]) if valor.split() else 0
    except (FileNotFoundError, PermissionError):
        return datos
    return datos


def leer_loadavg():
    """
    Lee /proc/loadavg. Formato:
        0.52 0.58 0.59 2/1234 5678
        └load 1m,5m,15m┘ └run/total┘ └último pid┘
    Devuelve dict con load_1, load_5, load_15, procs_ejecutando, procs_total.
    """
    try:
        with open(f"{PROC}/loadavg", "r") as f:
            partes = f.read().split()
        run_total = partes[3].split("/")  # 'running/total'
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
    """
    Lee /proc/uptime. Formato: 'segundos_arriba segundos_idle'.
    Devuelve los segundos que el sistema lleva encendido (float).
    """
    try:
        with open(f"{PROC}/uptime", "r") as f:
            return float(f.read().split()[0])
    except (FileNotFoundError, PermissionError, IndexError):
        return 0.0


# Cache de /etc/passwd para no releer el archivo por cada proceso.
_passwd_cache = None


def usuario_de_uid(uid):
    """
    Traduce un UID numérico al nombre de usuario leyendo /etc/passwd.
    Formato de /etc/passwd: 'nombre:x:UID:GID:...'. Cacheo el mapa la 1ra vez.
    No uso el módulo `pwd` a propósito: se ve el mecanismo (parsear el archivo),
    que es la gracia del TP. Si no se encuentra, devuelvo el UID como string.
    """
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


# Jiffies por segundo (frecuencia del reloj del kernel). Casi siempre 100.
# Se usa para convertir jiffies <-> segundos.
CLK_TCK = os.sysconf("SC_CLK_TCK")


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------
def _a_int(valor):
    """Convierte a int; si no se puede, devuelve el string tal cual."""
    try:
        return int(valor)
    except (ValueError, TypeError):
        return valor
