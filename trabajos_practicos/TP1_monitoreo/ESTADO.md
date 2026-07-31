# ESTADO del TP1 — leer esto primero

Archivo de continuidad. Si abrís un chat nuevo con la IA, **pegale esto o pedile
que lo lea** para que retome sin perder contexto.

---

## Cómo trabajamos (reglas fijas)

1. **Modo:** la IA escribe el código muy comentado y me lo explica. Yo lo estudio.
   No importa quién escribe; importa que **yo lo entienda** (en la corrección me
   preguntan sobre mi propio código — si no lo explico, no apruebo).
2. **Tiene que andar de verdad.** Nada se da por terminado hasta correrlo en
   **Linux/Docker** contra `/proc` real y ver que funciona. `/proc` no existe en
   Windows: por eso se prueba siempre dentro del contenedor.
3. **Dos docs se actualizan por cada fase:**
   - `justificacion_tecnica.md` — a fondo, para estudiar.
   - `justificacion_simple.md` — repaso rápido para la defensa.
4. Se avanza **una fase por vez**. No se pasa a la siguiente hasta que la actual
   anda y la entiendo.

**Entrega:** ~03/08/2026 (1 semana). Plan completo de fases en `plan.md`.

---

## Progreso

| Fase | Qué es | Estado |
|------|--------|--------|
| 0 | Docker, estructura, config, stubs | ✅ hecho |
| 1 | `procfs.py` — leer /proc a mano (listar_pids, leer_status, leer_stat, leer_cmdline) | ✅ verificado en Docker (coincide con `ps -e`) |
| 2 | Monolito: loop + CPU% (delta jiffies) + vistas Resumen y Sistema | ✅ verificado en Docker (CPU% correcto con `yes`) |
| 3 | Señales (self-pipe): SIGINT/TERM/HUP/USR1/USR2 | ✅ verificado (dump generado, señales OK) |
| 4 | Memoria compartida (`Manager.dict`) + agregador | ✅ verificado (maté el analizador, display sobrevivió con dato viejo) |
| 5 | Los 7 analizadores en procesos paralelos | ✅ verificado (9 python3, los 7 escriben a su ritmo, dump con los 7) |
| 6 | TUI completa (7 vistas + keybindings) | ✅ verificado (7 vistas, flechas+k/j, pin con Enter, filtros / y u, orden c, ayuda h; teclado cbreak con os.read) |
| 7 | Vista Threads (LWPs) + intervalos en vivo (`Value`) | ⬜ |
| 8 | Race conditions + locks + decodificar máscaras de señales | ⬜ |
| 9 | README + dudas.md + entrega | ⬜ |

---

## Cómo probar (Docker Desktop en Windows sirve)

El servicio se llama `monitor`. Como `main.py` es un proceso largo (TUI), usar:
```bash
cd trabajos_practicos/TP1_monitoreo
docker compose run --rm --build monitor          # corre la TUI (Ctrl+C sale)
# para ver CPU% con carga:
docker compose run --rm --build monitor sh -c "yes >/dev/null & yes >/dev/null & python3 src/main.py"
# test de Fase 1:
docker compose run --rm monitor python3 tests/probar_fase1.py
```

Para probar señales (2 terminales): levantar `docker compose run --rm --name mon1 --build monitor`
y desde otra terminal `docker exec mon1 sh -c "kill -USR1 1"` (dump), `-USR2` (verbose),
`-HUP` (reload). Ctrl+C sale limpio.

## Próximo paso concreto

**Fase 7 — Vista Threads (LWPs) + intervalos en vivo (`Value`).** Calcular CPU% individual por Thread/LWP vía delta de jiffies en `task/<tid>/stat`. Ajuste de intervalos de recolección en tiempo real con las teclas `+` y `-` modificando el `mp.Value` compartido del analizador activo.


## Material de estudio que se mantiene al día

- `justificacion_tecnica.md` — a fondo.
- `justificacion_simple.md` — repaso rápido.
- `cuestionario_de_practica.md` — preguntas MC (para NotebookLM).
