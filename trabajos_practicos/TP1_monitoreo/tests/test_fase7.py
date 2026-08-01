"""
Tests Fase 7 — analizador de threads (LWPs) con CPU% por thread.

Corre en cualquier lado (con /proc de muestra).

Qué se prueba:
  1. El analizador arma, por PID, la lista de sus threads con tid/nombre/estado/cpu.
  2. En la PRIMERA pasada el CPU% por thread es 0.0 (sin lectura previa que restar),
     igual que el CPU% por proceso. No es bug.
"""
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from analizadores import threads  # noqa: E402
import _fixtures as fx            # noqa: E402


class CorrenNVeces:
    def __init__(self, n):
        self.n = n

    def is_set(self):
        self.n -= 1
        return self.n >= 0


class TestAnalizadorThreads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fx.montar(self.tmp)
        fx.sistema(self.tmp)  # /proc/stat para el CPU total
        tasks = [
            (1234, fx.construir_stat(pid=1234, comm="main", utime=10), None),
            (1240, fx.construir_stat(pid=1240, comm="worker", utime=5), None),
        ]
        fx.proceso(self.tmp, 1234, tasks=tasks)

    def test_estructura_y_primera_pasada_cero(self):
        snap = {}
        threads.correr(snap, types.SimpleNamespace(value=0.01),
                       CorrenNVeces(1), None)
        datos = snap["threads"]["datos"]
        self.assertIn(1234, datos)
        self.assertEqual(datos[1234]["count"], 2)
        tids = sorted(t["tid"] for t in datos[1234]["lista"])
        self.assertEqual(tids, [1234, 1240])
        # Primera pasada: CPU% de cada thread = 0.0 (sin foto previa que restar).
        for t in datos[1234]["lista"]:
            self.assertEqual(t["cpu"], 0.0)
            self.assertIn("nombre", t)
            self.assertIn("estado", t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
