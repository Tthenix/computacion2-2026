# Dudas y decisiones en zona gris

Cosas que me quedaron dando vueltas durante el desarrollo. Las dejo documentadas
por honestidad intelectual: no son bugs, son decisiones donde había más de una
lectura válida o donde el entorno metió ruido.

---

## 1. `docker compose up --build` vs `docker compose run`

La consigna pide *"un comando único de levantar todo: `docker compose up --build`"*
y que el contenedor sea interactivo (`tty: true`, `stdin_open: true`).

Puse esos flags, pero descubrí que **`docker compose up` no conecta el teclado
(stdin)** al contenedor: se queda en modo *logs* (con el prefijo `monitor-1 |`) y la
TUI parpadea sin responder a las teclas. La forma correcta de correr una app de
terminal interactiva en Docker es **`docker compose run`** (o `docker run -it`), que
sí da un TTY conectado.

**Duda:** ¿la cátedra espera que `docker compose up` sea plenamente interactivo (y
hay alguna config de compose que lo logre), o acepta documentar que la interacción
se hace con `docker compose run`? Opté por lo segundo y lo expliqué en el README,
porque es el comportamiento estándar de Docker.

---

## 2. `btime` varía entre lecturas bajo Docker Desktop / WSL2

`btime` (momento del boot, en `/proc/stat`) debería ser **constante**. En mi entorno
(Docker Desktop sobre WSL2 en Windows) varía unos segundos entre lecturas.

Investigando, parece un quirk del **reloj de la VM** de WSL2, no de mi parseo (leo el
campo tal cual). **Duda:** ¿en un Linux nativo esto sería 100% estable? Asumo que sí.

---

## 3. Modelo de CPU%: "100% = toda la máquina" vs "100% = 1 core"

Calculo el CPU% como `100 * delta_proc / delta_cpu_total`, donde el total suma todos
los cores. Entonces un proceso que satura 1 core en una máquina de 16 muestra ~6.25%,
no 100% (que sería el estilo `htop`, multiplicando por la cantidad de cores).

Elegí el modelo "toda la máquina" porque es coherente con el CPU% global del sistema.
**Duda:** ¿la cátedra prefería el estilo htop (por core)? Es un cambio de una línea
(multiplicar por `ncpus`), pero quería que proceso y sistema usaran la misma escala.

---

## 4. Analizadores autónomos vs un recolector central que reparte

La consigna dice *"Recolector: lista procesos vía /proc, distribuye trabajo a los
analizadores"* Y también *"cada analizador es un proceso independiente con su propio
intervalo"*. Esas dos ideas están un poco en tensión.

Elegí **analizadores autónomos**: cada uno lista `/proc` y extrae su dimensión por su
cuenta, a su ritmo. Ventaja: independencia real (matar uno no afecta al resto) e
intervalos por vista naturales. Costo: se lista `/proc` varias veces (barato, es un
tmpfs). La alternativa (un recolector central que lee todo y los analizadores
transforman) es más testeable pero acopla todo a una sola recolección y complica los
intervalos diferenciados.

**Duda:** ¿la cátedra esperaba el recolector central literal? Creo que mi lectura
cumple igual el objetivo (multiproceso + IPC + intervalos), pero es un punto opinable.

---

## 5. ¿Cuánto "más detalle" debe mostrar el modo verbose (SIGUSR2)?

La consigna da como ejemplo "más FDs visibles". Mi verbose aumenta la cantidad de
filas/procesos mostrados. **Duda:** ¿esperaban algo más específico por vista (ej. en
memoria mostrar cada segmento de `maps`, en fds levantar el tope de 40)? Lo dejé
simple; se podría enriquecer.

---

## 6. Overhead del `Manager.dict` con muchísimos procesos

Cada acceso al `Manager.dict` es una llamada IPC al proceso servidor. Con pocos
procesos va perfecto; leo el snapshot una vez por refresco para minimizarlo.
**Duda:** con miles de procesos y 7 analizadores escribiendo seguido, ¿el servidor
del Manager se vuelve cuello de botella? No llegué a estresarlo a esa escala.
