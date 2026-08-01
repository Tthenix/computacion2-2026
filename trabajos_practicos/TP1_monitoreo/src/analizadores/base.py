"""
Base común de los analizadores (FASE 5).

Los 7 analizadores comparten el MISMO esqueleto: en un loop, extraer su dato y
escribirlo en el snapshot compartido con timestamp y PID. Lo único que cambia es
la función `extraer`. Para no repetir ese loop 7 veces, vive acá.

Cada entrada del snapshot tiene siempre la forma:
    snapshot[nombre] = {"datos": <lo que sea>, "ts": <cuándo>, "pid": <quién>}
El `ts` deja detectar analizadores caídos (dato viejo); el `pid` deja matarlos
para probar el aislamiento.
"""
import os
import time


def bucle(nombre, snapshot, intervalo, corriendo, extraer, lock=None):
    """
    Loop genérico de un analizador.

    Args:
        nombre:    clave bajo la que escribe en el snapshot (ej. "memoria").
        snapshot:  Manager().dict() compartido.
        intervalo: Value('d') con los segundos entre lecturas (ajustable en vivo).
        corriendo: Event(). Mientras esté set, seguimos.
        extraer:   función sin argumentos que devuelve el dato de este analizador.
        lock:      multiprocessing.Lock() compartido. Se toma SOLO al escribir la
                   entrada en el snapshot, para que el dump (SIGUSR1) pueda leer
                   las 7 claves sin que ninguna se esté escribiendo en el medio
                   (sección crítica). Ver justificación de race conditions.
    """
    pid = os.getpid()
    while corriendo.is_set():
        try:
            datos = extraer()
        except Exception as e:
            # Un analizador nunca debe tumbar todo por un error puntual leyendo
            # /proc (un proceso que muta a mitad de lectura, permisos, etc.).
            # Guardamos el error y seguimos: robustez > exactitud momentánea.
            datos = {"error": str(e)}

        entrada = {"datos": datos, "ts": time.time(), "pid": pid}
        # El grueso del trabajo (extraer()) queda FUERA del lock: no serializamos
        # a los analizadores entre sí. Solo la escritura, que es instantánea.
        if lock is not None:
            with lock:
                snapshot[nombre] = entrada
        else:
            snapshot[nombre] = entrada

        # Dormir el intervalo actual (puede cambiar en caliente por el Value).
        time.sleep(max(0.1, intervalo.value))
