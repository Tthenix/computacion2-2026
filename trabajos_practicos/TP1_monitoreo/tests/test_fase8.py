"""
Tests Fase 8 — decodificar máscaras de señales (SigBlk, etc.) a nombres.

Regla: la máscara es hex de 64 bits; el bit i (desde 0) representa la señal (i+1).

Uso SIGINT (señal 2) y SIGTERM (señal 15), que existen en Windows y Linux, para
que el test corra en cualquier lado. Los nombres solo-Linux (SIGHUP=1, SIGCHLD=17)
se verifican en Docker / a mano en la vista Señales.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analizadores.senales import decodificar_mascara  # noqa: E402


class TestDecodificarMascara(unittest.TestCase):
    def test_mascara_vacia(self):
        self.assertEqual(decodificar_mascara("0"), [])
        self.assertEqual(decodificar_mascara("0000000000000000"), [])

    def test_hex_invalido_no_rompe(self):
        self.assertEqual(decodificar_mascara("xyz"), [])
        self.assertEqual(decodificar_mascara(None), [])

    def test_sigint_bit1(self):
        # 0x2 = bit 1 -> señal 2 = SIGINT
        self.assertEqual(decodificar_mascara("2"), ["SIGINT"])

    def test_sigterm_bit14(self):
        # 0x4000 = bit 14 -> señal 15 = SIGTERM
        self.assertEqual(decodificar_mascara("0000000000004000"), ["SIGTERM"])

    def test_varias_en_orden(self):
        # 0x4002 = bits 1 y 14 -> señales 2 y 15, en orden ascendente
        self.assertEqual(decodificar_mascara("0000000000004002"),
                         ["SIGINT", "SIGTERM"])

    def test_cantidad_de_bits(self):
        # 0x4002 tiene 2 bits en 1 -> 2 nombres
        self.assertEqual(len(decodificar_mascara("4002")), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
