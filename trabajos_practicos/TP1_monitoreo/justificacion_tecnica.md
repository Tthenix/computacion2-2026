# Justificación técnica — TP1 Monitor de Procesos

Documento **para estudiar**. Explica a fondo cada decisión, el porqué del código y
los conceptos del curso detrás. Se va completando fase por fase.

> Complemento: `justificacion_simple.md` es la versión corta para repasar antes de la defensa.

---

## Fase 0 — Setup (Docker)

**Por qué Docker.** El TP lee `/proc`, un pseudo-filesystem que **solo existe en
Linux**. En Windows/Mac no está, o no tiene el mismo formato. Docker nos da un
Linux real y reproducible: el corrector corre `docker compose up --build` y le
funciona igual que a mí, sin "en mi máquina anda".

**`tty: true` + `stdin_open: true`** en `docker-compose.yml`: la TUI necesita una
terminal interactiva (leer teclas, redibujar). Sin esto el contenedor no tiene
TTY y la interfaz no funciona.

---

## Fase 1 — Leer `/proc` a mano (`procfs.py`)

Módulo central de lectura. **Ningún otro módulo abre archivos de `/proc`
directamente** — todo pasa por acá. Ventaja: si cambia un formato, se toca en un
solo lugar (principio DRY / punto único de cambio).

### Concepto base: qué es `/proc`

`/proc` es un **filesystem virtual** (procfs). No está en disco: el kernel lo
genera al vuelo. Cada `/proc/<pid>/` es una ventana al estado de un proceso vivo.
Leer esos archivos = preguntarle al kernel por el proceso. Esto es *inspeccionar
un proceso desde afuera* (objetivo pedagógico 1). Visto en **clase 3**.

### `listar_pids()`

`os.listdir('/proc')` filtrando `.isdigit()`. `/proc` mezcla carpetas numéricas
(una por PID) con archivos globales (`meminfo`, `stat`, `loadavg`, `self`, ...).
Solo las numéricas son procesos.

### `leer_status(pid)` — `/proc/<pid>/status`

El archivo **cómodo**: viene etiquetado, una línea por campo `Clave:\tvalor`.

```
State:  S (sleeping)
PPid:   1000
Threads:        1
VmRSS:  4096 kB
SigBlk: 0000000000010000
```

Parseo con `linea.partition(":")` — corta en el **primer** `:`, así aunque el
valor tenga otros `:` no se rompe. Devuelvo el dict con valores string crudos:
quien lo use decide cómo interpretarlos (int, hex, primer token...).

### `leer_stat(pid)` — `/proc/<pid>/stat` (EL TRAICIONERO)

Campos separados por espacio, **posicionales** (1-indexados como en `man 5 proc`):

| Campo | Dato | Campo | Dato |
|-------|------|-------|------|
| 1 | pid | 14 | utime (jiffies user) |
| 2 | comm | 15 | stime (jiffies kernel) |
| 3 | state | 18 | priority |
| 4 | ppid | 19 | nice |
| 6 | session (SID) | 20 | num_threads |
| 5 | pgrp (PGID) | 22 | starttime |
| 10,12 | min/maj page faults | 40,41 | rt_priority, policy |

**El problema.** El campo 2 (`comm`, nombre del ejecutable) va entre paréntesis y
**puede contener espacios y hasta paréntesis**:

```
1234 (mi proceso (raro)) S 1000 ...
```

Un `split(" ")` ingenuo corre todos los campos siguientes y rompe el parseo.

**Solución canónica** (la que usan htop, ps, etc.):

1. `pid` = todo lo anterior al **primer** `(`  → `contenido.find("(")`
2. `comm` = entre el primer `(` y el **último** `)`  → `contenido.rfind(")")`
3. resto (`state` en adelante) = `split()` normal **después** del último `)`

Por eso uso `rfind` y no `find` para el cierre: si el comm tiene `)` adentro,
solo el último cierra el nombre real.

Después mapeo `resto[i]` a nombres con la lista `_STAT_CAMPOS`. Los campos de
scheduling avanzado (rt_priority = campo 40, policy = campo 41) están más allá de
esa lista, los tomo por índice: **campo N de man proc → índice (N-3) en `resto`**
(porque `resto[0]` es el campo 3, `state`).

### `leer_cmdline(pid)` — `/proc/<pid>/cmdline`

Los argumentos (`argv`) van separados por `\0` (byte nulo), **no** por espacio, y
termina en `\0`:

```
python3\0-u\0script.py\0
```

Leo en **binario** (`"rb"`), `split(b"\x00")`, descarto vacíos, uno con espacios.

**Caso especial:** si `cmdline` está vacío, es un **kernel thread** (kworker,
ksoftirqd, migration...). Los procesos de kernel no tienen espacio de usuario ni
argv. Fallback: usar el `comm` de `stat` entre corchetes → `[kworker/0:1]`
(misma convención que `ps`).

### Decisión transversal: tolerancia a procesos que mueren

Todas las funciones devuelven `None` ante `FileNotFoundError` /
`ProcessLookupError` / `PermissionError`. **`/proc` es volátil**: un PID puede
desaparecer entre que lo listo y que lo leo (el proceso terminó). Es una **race
inherente al sistema operativo**, no un bug de mi código. Si no lo manejo, el
monitor crashea al azar cuando cualquier proceso del sistema termina. Quien llama
saltea los `None`.

---

## Preguntas de defensa cubiertas hasta acá

- *"¿Cómo parseás `stat` si el comando tiene espacios o paréntesis?"*
  → Desde el **último** `)`. pid antes del primer `(`, comm entre primer `(` y
  último `)`, el resto se splitea después.
- *"¿Por qué `/proc` y no `psutil`?"*
  → El TP exige leerlo a mano; `psutil` está prohibido porque abstrae justo lo que
  hay que aprender. Además `/proc` lo genera el kernel, es la fuente real.
- *"Si un proceso muere mientras lo leés, ¿qué pasa?"*
  → Devuelvo `None` y lo salteo. `/proc` es volátil por diseño.
