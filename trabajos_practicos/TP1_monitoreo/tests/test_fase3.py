"""
Tests Fase 3 — manejo de señales con self-pipe (GestorSenales).

Qué se prueba (corre en Linux/Docker; usa fcntl):
  1. Al "llegar" una señal, el handler la encola Y despierta el pipe (read_fd
     queda legible).
  2. procesar_pendientes() traduce la señal a la ACCIÓN correcta y drena la cola.
  3. Varias señales se traducen en orden.

No mandamos señales reales del SO: llamamos al handler directamente (que es lo que
haría el kernel), así el test es determinista.
"""
import os
import select
import signal
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from senales import GestorSenales  # noqa: E402


class TestGestorSenales(unittest.TestCase):
    def setUp(self):
        self.g = GestorSenales()

    def tearDown(self):
        self.g.cerrar()

    def test_signal_despierta_el_pipe(self):
        """Tras el handler, read_fd debe quedar legible (el 'timbre' del self-pipe)."""
        self.g._handler(signal.SIGUSR1, None)
        legibles, _, _ = select.select([self.g.read_fd], [], [], 0.5)
        self.assertIn(self.g.read_fd, legibles)

    def test_mapea_senal_a_accion(self):
        self.g._handler(signal.SIGUSR1, None)   # dump
        acciones = self.g.procesar_pendientes()
        self.assertEqual(acciones, ["dump"])

    def test_shutdown_y_reload(self):
        self.g._handler(signal.SIGTERM, None)   # shutdown
        self.g._handler(signal.SIGHUP, None)    # reload
        acciones = self.g.procesar_pendientes()
        self.assertEqual(acciones, ["shutdown", "reload"])

    def test_drena_la_cola(self):
        """Después de procesar, no debe quedar nada pendiente."""
        self.g._handler(signal.SIGUSR2, None)
        self.g.procesar_pendientes()
        self.assertEqual(self.g.procesar_pendientes(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
