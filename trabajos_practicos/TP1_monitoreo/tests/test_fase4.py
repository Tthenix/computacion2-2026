"""
Tests Fase 4 — el bucle de los analizadores (base.bucle) y su robustez.

Qué se prueba (corre en cualquier lado):
  1. El bucle escribe en el snapshot una entrada con la forma {datos, ts, pid}.
  2. Si extraer() lanza una excepción, NO se cae: guarda {"error": ...} y sigue.
     (aislamiento: un fallo leyendo /proc no tumba al analizador).
  3. El lock (opcional) se toma al escribir si se pasa.

No usamos procesos reales: pasamos un dict común como snapshot y un "corriendo"
falso que corta después de N vueltas, para que el loop termine.
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analizadores.base import bucle  # noqa: E402


class CorrenNVeces:
    """Stub de Event: is_set() devuelve True las primeras n veces, luego False."""
    def __init__(self, n):
        self.n = n

    def is_set(self):
        self.n -= 1
        return self.n >= 0


class LockFalso:
    def __init__(self):
        self.tomado = 0

    def __enter__(self):
        self.tomado += 1

    def __exit__(self, *a):
        return False


class TestBucle(unittest.TestCase):
    def _intervalo(self):
        return types.SimpleNamespace(value=0.01)  # dormir poquito

    def test_escribe_entrada_bien_formada(self):
        snap = {}
        bucle("prueba", snap, self._intervalo(), CorrenNVeces(1),
              lambda: {"x": 42})
        self.assertIn("prueba", snap)
        entrada = snap["prueba"]
        self.assertEqual(entrada["datos"], {"x": 42})
        self.assertIn("ts", entrada)
        self.assertIn("pid", entrada)

    def test_robustez_extraer_falla(self):
        """Si extraer revienta, el bucle guarda el error y no crashea."""
        def extraer_roto():
            raise ValueError("proceso murió a mitad de lectura")
        snap = {}
        bucle("prueba", snap, self._intervalo(), CorrenNVeces(1), extraer_roto)
        self.assertIn("error", snap["prueba"]["datos"])
        self.assertIn("murió", snap["prueba"]["datos"]["error"])

    def test_toma_el_lock_al_escribir(self):
        snap = {}
        lock = LockFalso()
        bucle("prueba", snap, self._intervalo(), CorrenNVeces(1),
              lambda: {"ok": True}, lock)
        self.assertEqual(lock.tomado, 1)  # se tomó exactamente 1 vez (al escribir)


if __name__ == "__main__":
    unittest.main(verbosity=2)
