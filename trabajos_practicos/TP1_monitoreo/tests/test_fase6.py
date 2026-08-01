"""
Tests Fase 6/7 — TUI: filtro/orden, parseo de teclado y clamp de intervalos.

Corre en Docker (importa vistas/display, que usan rich).

Qué se prueba:
  1. filtrar_ordenar: filtra por comando y por usuario, y ordena por cpu/rss/pid.
     (misma función que usan la vista Y la navegación, para que coincidan).
  2. El parser de teclado: bytes crudos -> tokens (flechas ESC[ y ESC O, chars).
  3. +/- ajusta el intervalo respetando el mínimo y el máximo por vista (Fase 7).
"""
import os
import queue
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import vistas       # noqa: E402
import display      # noqa: E402

PROCS = [
    {"pid": 3, "comando": "python app", "usuario": "root", "cpu": 5.0, "rss_kb": 100},
    {"pid": 1, "comando": "bash", "usuario": "nahuel", "cpu": 10.0, "rss_kb": 50},
    {"pid": 2, "comando": "python worker", "usuario": "root", "cpu": 1.0, "rss_kb": 200},
]


class TestFiltrarOrdenar(unittest.TestCase):
    def test_filtro_por_comando(self):
        r = vistas.filtrar_ordenar(PROCS, "python", "", "cpu")
        self.assertEqual([p["pid"] for p in r], [3, 2])  # ambos python, orden cpu desc

    def test_filtro_por_usuario(self):
        r = vistas.filtrar_ordenar(PROCS, "", "nahuel", "cpu")
        self.assertEqual([p["pid"] for p in r], [1])

    def test_orden_por_pid(self):
        r = vistas.filtrar_ordenar(PROCS, "", "", "pid")
        self.assertEqual([p["pid"] for p in r], [1, 2, 3])

    def test_orden_por_rss(self):
        r = vistas.filtrar_ordenar(PROCS, "", "", "rss")
        self.assertEqual([p["pid"] for p in r], [2, 3, 1])  # rss desc


class TestTeclado(unittest.TestCase):
    def setUp(self):
        self.cola = queue.Queue()
        self.h = display.HiloTeclado(self.cola)  # no .start(): solo parseamos

    def _drenar(self):
        out = []
        while not self.cola.empty():
            out.append(self.cola.get_nowait())
        return out

    def test_flecha_arriba_abajo(self):
        self.h._parsear(b"\x1b[A")
        self.h._parsear(b"\x1b[B")
        self.assertEqual(self._drenar(), ["UP", "DOWN"])

    def test_flecha_modo_application(self):
        self.h._parsear(b"\x1bOA")   # ESC O A (application cursor)
        self.assertEqual(self._drenar(), ["UP"])

    def test_chars_normales(self):
        self.h._parsear(b"q")
        self.h._parsear(b"5")
        self.assertEqual(self._drenar(), ["q", "5"])


class _ValueFalso:
    def __init__(self, v):
        self.value = v


class TestIntervalos(unittest.TestCase):
    def setUp(self):
        self.iv = _ValueFalso(2.0)
        self.tui = display.MonitorTUI({"resumen": self.iv})
        self.tui.vista_activa = "resumen"

    def test_mas_baja_el_intervalo(self):
        self.tui._ajustar_intervalo(-0.5)
        self.assertEqual(self.iv.value, 1.5)

    def test_respeta_el_minimo(self):
        for _ in range(20):
            self.tui._ajustar_intervalo(-0.5)
        self.assertEqual(self.iv.value, 0.5)   # mínimo de resumen

    def test_respeta_el_maximo(self):
        for _ in range(200):
            self.tui._ajustar_intervalo(+0.5)
        self.assertEqual(self.iv.value, 30.0)  # INTERVALO_MAX


if __name__ == "__main__":
    unittest.main(verbosity=2)
