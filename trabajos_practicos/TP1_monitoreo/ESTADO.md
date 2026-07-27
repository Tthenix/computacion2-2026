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
| 1 | `procfs.py` — leer /proc a mano (listar_pids, leer_status, leer_stat, leer_cmdline) | ✅ código escrito — **falta probar en Linux** |
| 2 | Monolito: loop + CPU% (delta jiffies) + vistas Resumen y Sistema | ⬜ siguiente |
| 3 | Señales (self-pipe): SIGINT/TERM/HUP/USR1/USR2 | ⬜ |
| 4 | Memoria compartida (`Manager.dict`) + agregador | ⬜ |
| 5 | Los 7 analizadores en procesos paralelos | ⬜ |
| 6 | TUI completa (7 vistas + keybindings) | ⬜ |
| 7 | Vista Threads (LWPs) + intervalos en vivo (`Value`) | ⬜ |
| 8 | Race conditions + locks + decodificar máscaras de señales | ⬜ |
| 9 | README + dudas.md + entrega | ⬜ |

---

## Próximo paso concreto

1. Cambiar a Linux.
2. Probar Fase 1 dentro del contenedor:
   ```bash
   cd trabajos_practicos/TP1_monitoreo
   docker compose up --build -d
   docker compose exec <servicio> python3 tests/probar_fase1.py
   docker compose exec <servicio> ps -e     # comparar
   ```
3. Si la tabla PID/estado/comando coincide con `ps -e` → Fase 1 OK → arrancar Fase 2.
