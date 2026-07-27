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


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------
def _a_int(valor):
    """Convierte a int; si no se puede, devuelve el string tal cual."""
    try:
        return int(valor)
    except (ValueError, TypeError):
        return valor
