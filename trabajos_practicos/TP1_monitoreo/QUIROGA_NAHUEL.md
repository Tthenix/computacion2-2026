# TP1 — Monitor de Procesos y Threads

**Nahuel Quiroga** · Computación II · Cohorte 2026

## Resultado: APROBADO

---

## Lo que hiciste bien

**Verificaste tu desarrollo fase por fase, en Docker, con experimentos reales.
Esto es lo primero que quiero nombrarte.**
Tu `ESTADO.md` no dice "hecho", dice qué probaste y cómo. Fase 1: "coincide con
`ps -e`". Fase 2: "CPU% correcto con `yes`" — o sea, levantaste un proceso que
quema CPU a propósito para tener un valor conocido contra el cual comparar
(`ESTADO.md:32`, y el comando exacto en la línea 50). Fase 4: "maté el analizador,
display sobrevivió con dato viejo" (`ESTADO.md:34`). Fase 8: "SigCgt de PID 1 =
handlers de fase 3" (`ESTADO.md:38`), o sea que decodificaste la máscara de tu
propio proceso y verificaste que diera justo las señales que vos habías
registrado. Eso es exactamente el tipo de verificación empírica que la cátedra
quiere ver: no confiar en que el código "debería" andar, sino construir la
situación donde se ve si anda. Vale más que cualquier feature extra.

**Los comentarios de `senales.py:11-34` son los mejores del curso.**
No explican qué hace el código: explican por qué el código es así. Planteás la
alternativa simple (el handler baja una bandera, el loop la chequea), decís por
qué no alcanza — "si el loop está BLOQUEADO esperando, la bandera no se mira
hasta que el bloqueo termina, la señal se siente tarde" — y de ahí derivás el
self-pipe como la solución que resuelve las dos cosas: async-signal-safety y
despertar inmediato. Esa es la respuesta completa a una pregunta que la consigna
anunciaba, escrita antes de que nadie te la hiciera.

**El manejo de race conditions es el más fino que vi (`base.py:43-49`).**
Tomás el lock SOLO para la asignación `snapshot[nombre] = entrada`, y dejás el
`extraer()` — que es todo el trabajo pesado de leer `/proc` — afuera de la
sección crítica. El comentario lo dice: "no serializamos a los analizadores entre
sí". Es la diferencia entre un lock que protege y un lock que convierte tu
sistema paralelo en uno secuencial. Y en `main.py:60-61` tomás el mismo lock para
copiar el snapshot del dump, con el razonamiento correcto escrito arriba: sin eso
el JSON podría capturar una escritura a medias.

**`base.py` elimina la duplicación entre los 7 analizadores.**
Un solo `bucle()` parametrizado, y cada analizador aporta solo su función de
extracción. Menos líneas haciendo lo mismo es mejor ingeniería.

**8 archivos de tests, uno por fase, más fixtures.**
`tests/test_fase1.py` a `test_fase8.py`. Es el único del grupo con tests
organizados según cómo desarrollaste, que es la forma que hace que efectivamente
los corras a medida que avanzás en vez de escribirlos todos al final.

**Guardás `ts` y `pid` en cada entrada del snapshot (`base.py:42`).**
Eso permite detectar analizadores caídos por dato viejo: si la marca de tiempo de
una sección no avanza, algo se murió. Es la infraestructura para la supervisión,
aunque todavía no la uses.

---

## Lo que falta, y el concepto detrás

**No hay proceso Recolector ni Agregador, y la consigna los lista como
componentes mínimos.**
A tu favor: lo argumentás en vez de disimularlo (`README.md:144-168` y el párrafo
personal de `README.md:350`), y el argumento tiene mérito real — si el Recolector
es un proceso y falla, se caen los 7 analizadores con él; con cada analizador
dueño de su propia clave, matás uno y el resto sigue. Eso es un tradeoff genuino
y lo probaste. Pero el costo es medible: `listar_pids()` se llama desde
`fds.py:18`, `scheduling.py:18`, `senales.py:51`, `memoria.py:24`,
`threads.py:35` y `recolector.py:53`. `/proc` se recorre hasta 7 veces por ciclo,
y cada analizador después abre `status` y `stat` de cada PID. Tu conclusión de
`README.md:350` es que "como mi PC tiene 40 GB de RAM, esa decisión no tenía
costo real para mí": ahí está el punto débil del razonamiento. El costo no es
memoria, es syscalls y latencia, y no escala con la RAM sino con la cantidad de
procesos. En una máquina con 2000 procesos son 14000 lecturas de `/proc` por
ciclo en vez de 2000.

**Los mínimos por vista no se respetan (`base.py:52`).**
Usás un piso genérico de 0.1s para todas las vistas. La tabla de la consigna
especifica mínimos distintos (2s para FDs, 5s para Señales y Scheduling) y la
razón es el costo: FDs cada 0.1s significa abrir y listar un directorio entero
por proceso diez veces por segundo. El mínimo por vista es la forma de que el
usuario no pueda pedirle al monitor algo que cuesta más de lo que vale.

**El display corre en el proceso principal junto con el loop de señales.**
El diagrama de la consigna lo pone como un proceso más. No rompe nada, pero
significa que un render lento te retrasa el atendido de las señales, que es
justamente lo que el self-pipe estaba pensado para evitar.

**Commiteaste `.claude/` con `SKILL.md` y `settings.json`.**
Sacalo del repo. No es una objeción al uso de IA — la cátedra lo fomenta y tu
`SKILL.md` es un tutor pedagógicamente legítimo, en el espíritu del
`prompt_tutor_ia.md` que dimos nosotros. Es que la configuración de tu editor no
es parte del entregable, igual que no entregarías tu `.vscode/`.

---

## Para la próxima

Una sola cosa: **implementá los mínimos por vista en `base.py:52`.** Pasá el
mínimo de cada vista al `bucle()` desde `config.json` y usalo en lugar del 0.1
fijo. Es un cambio de pocas líneas, pero el valor está en el paso siguiente:
medir cuánto tarda un ciclo de FDs con 300 procesos y ver por qué el mínimo de la
consigna es 2s y no 0.1s.

---

## Cierre

Tenés la mejor documentación interna del grupo: los comentarios de `senales.py` y
`base.py` explican el porqué de cada decisión al nivel que se espera en un
coloquio, escritos antes de que nadie preguntara. Y el manejo de races —lock solo
en la escritura, trabajo pesado afuera— es el más fino del curso. Pero lo que más
quiero que te lleves es el método: desarrollaste por fases y verificaste cada una
contra Docker real, matando un analizador para probar el aislamiento y usando
`yes` para tener un CPU% conocido contra el cual comparar. Esa forma de trabajar
es la que hace que después puedas defender lo que escribiste, y es la que quiero
ver en el TP2.
