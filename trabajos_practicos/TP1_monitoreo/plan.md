# Plan de desarrollo — TP1 Monitor de Procesos

Roadmap por fases. Estrategia: **construir monolito primero, partir a multiproceso después**.
No arrancar con 7 procesos en paralelo — eso es debug infernal. Primero leer `/proc` y
mostrar algo; después escalar.

Cada fase = código + tema a estudiar + cómo verificar + pregunta típica de corrección.

Decisiones tomadas:
- TUI: **rich**
- Se construye dentro de `trabajos_practicos/TP1_monitoreo/` (mover a repo propio en la entrega).

---

## Fase 0 — Setup  ✅ (en progreso)

**Hacer:**
- Estructura de carpetas (ver consigna).
- `Dockerfile` + `docker-compose.yml` con `tty: true`, `stdin_open: true`.
- `requirements.txt` (`rich`).
- `config.json` inicial.
- Stubs de cada módulo.

**Estudiar:** Docker básico — imagen, `docker compose up --build`. Por qué Docker: el TP es
Linux-only y leés `/proc`, que en Windows/Mac no existe igual.

**Verificar:** `docker compose up --build` entra al contenedor y `main.py` imprime versión de
Python + cantidad de procesos en `/proc`.

---

## Fase 1 — Leer `/proc` a mano (`procfs.py` + recolector)

**Hacer:** helpers que parsean un solo proceso. Sin TUI, sin multiproceso. Funciones que
devuelven dicts.
- Listar PIDs: `os.listdir('/proc')` filtrando numéricos.
- Parsear `/proc/<pid>/status` (líneas `clave: valor`).
- Parsear `/proc/<pid>/stat` (campos por posición — ojo el `comm` entre paréntesis con espacios).
- Leer `/proc/<pid>/cmdline` (separado por `\0`).

**Estudiar:** clase 3 (anatomía, `/proc`), clase 4 (PID/PPID, estados R/S/D/T/Z, zombies).
Qué es un jiffy y cómo calcular CPU% (delta entre 2 lecturas).

**Verificar:** script que imprime tabla `PID | estado | comando`. Comparar con `ps aux`.

**Corrección:** *"¿cómo parseás `stat` si el comando tiene espacios o paréntesis?"* → desde el último `)`.

---

## Fase 2 — Monolito: 2 vistas en un solo proceso

**Hacer:** loop que cada N segundos relee `/proc`, calcula CPU% (delta), dibuja. Solo vista
**Resumen** + **Sistema** (`/proc/stat`, `/proc/meminfo`, `/proc/loadavg`). Todavía 1 proceso.

**Estudiar:** CPU% global y por proceso con deltas de jiffies. `/proc/meminfo`, load average.

**Verificar:** lista de procesos refrescándose, CPU% parecido a `htop`.

**Hito:** algo que funciona y se ve. Lo demás es escalarlo.

---

## Fase 3 — Señales (self-pipe)

**Hacer:** manejador de señales en el monolito. SIGINT/TERM (salir limpio), SIGHUP (releer
`config.json`), SIGUSR1 (dump snapshot a JSON), SIGUSR2 (toggle verbose).

**Estudiar:** clase 6 — async-signal-safe, **self-pipe pattern**, `signal.set_wakeup_fd`.
Base ya hecha en `clase_05_senales/servidor_signals.py`; acá se agrega self-pipe.

**Verificar:** `kill -USR1 <pid>` genera `dump_<ts>.json` válido. `kill -HUP` recarga sin reiniciar.

**Corrección:** *"¿por qué self-pipe y no solo una bandera?"*

---

## Fase 4 — Memoria compartida + agregador

**Hacer:** snapshot a `Manager().dict()`. Separar **un** analizador a su propio proceso que
escribe al dict; el display lee.

**Estudiar:** clase 7 (mmap, memoria compartida), clase 9 (`Manager` vs `Value`/`Array`).
Por qué `Manager.dict` para estructuras anidadas y `Value` para un int (el intervalo).

**Verificar:** matar el proceso analizador con `kill` → el display sigue vivo con datos viejos.

**Corrección:** *"¿por qué `Manager.dict` y no un dict normal?"*

---

## Fase 5 — Los 7 analizadores en paralelo

**Hacer:** partir en 7 procesos (resumen, memoria, fds, threads, senales, scheduling, sistema),
cada uno con su intervalo, todos escribiendo al snapshot. Recolector distribuye trabajo.

**Estudiar:** clase 8 (`Process`, `Queue`, `Pipe`, daemons), clase 9 (`Pool`).

**Verificar:** `ps` muestra ~8 hijos. Cada vista con datos frescos a su ritmo.

**Corrección:** *"si lanzo 100 procesos nuevos, ¿escala?"*

---

## Fase 6 — TUI completa (7 vistas + keybindings)

**Hacer:** 7 vistas alternables, navegación `↑↓`, pin `Enter`, filtros `/` y `u`, orden `c`,
intervalo `+/-`, ayuda `h`.

**Estudiar:** `rich.Live` / `Layout`. Entrada de teclado sin bloquear (thread interno en display).

**Verificar:** las 7 teclas cambian vista, navegación responde.

---

## Fase 7 — Vista Threads + intervalos ajustables en vivo

**Hacer:** vista de LWPs (`/proc/<pid>/task/<tid>/...`). `+/-` ajusta el intervalo del
analizador activo vía `Value` compartido.

**Estudiar:** clase 10 — GIL, threads como LWPs. Diferencia PID vs TID.

**Corrección:** *"diferencia PID/TID"*, *"¿qué es un context switch involuntario?"*

---

## Fase 8 — Race conditions + sincronización

**Hacer:** auditar accesos compartidos, meter `Lock` donde haga falta. Decodificar máscaras de
señales (`SigBlk` etc.) a nombres.

**Estudiar:** clase 11 — race conditions, locks. Decodificar hex de 64 bits a `SIGTERM` (bit N = señal N+1).

**Corrección:** *"mostrame una race condition y cómo la prevenís"*, *"¿cómo decodificás SigBlk?"*

---

## Fase 9 — README + dudas + entrega

**Hacer:** README (15% de la nota, central). Diagrama, decisiones argumentadas, conceptos del
curso conectados al código, limitaciones, cómo correr. `dudas.md`. Capturas/GIF.

---

## Mapa fases ↔ clases ↔ semanas

| Fase | Clase | Semana |
|------|-------|--------|
| 0-1 | 3, 4, 5 | 1 |
| 2-3 | 6 | 2 |
| 4 | 7 | 3 |
| 5 | 8, 9 | 4 |
| 6-7 | 10 | 5 |
| 8-9 | 11 | 6 |
