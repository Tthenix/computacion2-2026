# Justificación simple — repaso rápido

Versión corta para leer antes de la defensa. Cada punto = una respuesta lista.
Versión larga: `justificacion_tecnica.md`.

---

## Fase 0 — Docker

- **¿Por qué Docker?** `/proc` solo existe en Linux. Docker da un Linux real e
  igual para todos. El corrector hace `docker compose up --build` y anda.
- **`tty: true` / `stdin_open: true`**: la TUI necesita terminal interactiva
  (leer teclas, redibujar).

---

## Fase 1 — Leer `/proc`

- **¿Qué es `/proc`?** Filesystem virtual que genera el kernel. Cada
  `/proc/<pid>/` = estado de un proceso vivo. Leerlo = preguntarle al kernel.
- **`procfs.py`**: único módulo que toca `/proc`. Todo lo demás lo usa.

**4 funciones:**

| Función | Archivo | Truco |
|---------|---------|-------|
| `listar_pids()` | `/proc` | carpetas `.isdigit()` (el resto son archivos del sistema) |
| `leer_status()` | `status` | líneas `Clave: valor`, fácil |
| `leer_stat()` | `stat` | **el traicionero**, ver abajo |
| `leer_cmdline()` | `cmdline` | args separados por `\0`, no espacios |

**El truco de `stat` (te lo preguntan seguro):**
- El comando (`comm`) va entre `()` y puede tener espacios: `1234 (mi (raro)) S...`
- `split(" ")` normal → se rompe.
- Solución: pid = antes del primer `(`; comm = entre primer `(` y **último** `)`;
  el resto se splitea **después del último `)`**.

**`cmdline`**: separado por byte nulo `\0`. Vacío = kernel thread → uso `[comm]`.

**Todas devuelven `None` si el proceso murió.** `/proc` es volátil: un PID
desaparece en cualquier momento. Es una race del SO, no un bug mío.

---

### Respuestas de bolsillo

- *"¿parseo de stat con espacios?"* → desde el último `)`.
- *"¿por qué no psutil?"* → prohibido; abstrae lo que hay que aprender.
- *"¿proceso muere mientras leés?"* → devuelvo None, lo salteo.
