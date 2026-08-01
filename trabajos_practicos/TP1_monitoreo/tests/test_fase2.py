"""
Tests Fase 2 — parseo de /proc y cálculo de CPU% por delta de jiffies.

Qué se prueba:
  1. El parseo de /proc/<pid>/stat con el comm difícil (espacios y paréntesis).
  2. Los lectores del sistema (meminfo, loadavg, /proc/stat, uptime).
  3. El CÁLCULO de CPU% con delta de jiffies entre dos lecturas (el corazón).
"""
import os
import sys
import tempfile
import unittest

# IMPORTANTE: agregar src/ y tests/ al path ANTES de importar los módulos del
# proyecto. Si un formateador (isort) sube los imports arriba de estas líneas,
# rompe. Por eso corremos los tests con PYTHONPATH=src (ver README), que hace
# esto innecesario y es a prueba de reordenamientos.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import procfs                 # noqa: E402
import procfs_sistema         # noqa: E402
from recolector import Recolector  # noqa: E402
import _fixtures as fx        # noqa: E402


class TestParseoStat(unittest.TestCase):
    def test_comm_con_espacios_y_parentesis(self):
        """El comm 'a b)c' tiene espacio y ')': se parsea desde el ÚLTIMO ')'."""
        linea = fx.construir_stat(pid=1234, comm="a b)c", state="R", ppid=1000,
                                  utime=40, stime=12, nice=0, threads=5, policy=2)
        d = procfs._parsear_stat(linea)
        self.assertEqual(d["pid"], 1234)
        self.assertEqual(d["comm"], "a b)c")   # nombre real, con espacio y )
        self.assertEqual(d["state"], "R")
        self.assertEqual(d["ppid"], 1000)
        self.assertEqual(d["utime"], 40)
        self.assertEqual(d["stime"], 12)
        self.assertEqual(d["num_threads"], 5)
        self.assertEqual(d["nice"], 0)
        self.assertEqual(d["policy"], 2)       # campo 41 (RR)


class TestLectoresSistema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fx.montar(self.tmp)
        fx.sistema(self.tmp)

    def test_meminfo(self):
        mem = procfs_sistema.leer_meminfo()
        self.assertEqual(mem["MemTotal"], 2048)
        self.assertEqual(mem["MemAvailable"], 1500)

    def test_loadavg(self):
        load = procfs_sistema.leer_loadavg()
        self.assertEqual(load["load_1"], 0.50)
        self.assertEqual(load["procs_total"], 100)

    def test_stat_sistema_cpu_total(self):
        st = procfs_sistema.leer_stat_sistema()
        # cpu 500 0 200 300 0 0 0 -> total = 1000, idle_all = idle+iowait = 300
        self.assertEqual(st["cpu"]["total"], 1000)
        self.assertEqual(st["cpu"]["idle_all"], 300)
        self.assertEqual(st["btime"], 1000)

    def test_uptime(self):
        self.assertEqual(procfs_sistema.leer_uptime(), 100.0)


class TestCpuDelta(unittest.TestCase):
    """El CPU% NO sale de una lectura: es el delta entre dos."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fx.montar(self.tmp)

    def _snapshot(self, utime, cpu_total_line):
        fx.sistema(self.tmp, cpu=cpu_total_line)
        fx.proceso(self.tmp, 1234,
                   stat=fx.construir_stat(pid=1234, utime=utime, stime=0),
                   status=fx.construir_status())
        return self.rec.snapshot_procesos()

    def test_primera_lectura_cpu_cero(self):
        self.rec = Recolector()
        procs = self._snapshot(utime=10, cpu_total_line="cpu 500 0 200 300 0 0 0\n")
        # Primera pasada: sin lectura previa -> CPU% = 0 (esperado, no es bug).
        self.assertEqual(procs[0]["cpu"], 0.0)

    def test_segunda_lectura_calcula_delta(self):
        self.rec = Recolector()
        # 1ra: proc usó 10 jiffies, cpu total = 1000.
        self._snapshot(utime=10, cpu_total_line="cpu 500 0 200 300 0 0 0\n")
        # 2da: proc usó 30 (delta 20), cpu total = 1100 (delta 100).
        procs = self._snapshot(utime=30, cpu_total_line="cpu 500 0 200 400 0 0 0\n")
        # cpu% = 100 * 20 / 100 = 20.0
        self.assertEqual(procs[0]["cpu"], 20.0)
        self.assertEqual(procs[0]["ppid"], 1000)
        self.assertEqual(procs[0]["rss_kb"], 2048)


if __name__ == "__main__":
    unittest.main(verbosity=2)
