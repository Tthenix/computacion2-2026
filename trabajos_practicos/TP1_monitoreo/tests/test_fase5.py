"""
Tests Fase 5 — parseo avanzado de /proc y analizadores especializados.

Qué se prueba (corre en cualquier lado, con /proc de muestra):
  1. _tipo_fd: infiere el tipo de un FD según el destino del symlink.
  2. leer_maps: agrupa segmentos de memoria (text/data/heap/stack/lib) por tamaño.
  3. listar_tids / leer_stat_thread: los threads (LWPs) en task/<tid>/.
  4. analizador memoria: arma el dict por PID con VmRSS, faults y segmentos.
  5. analizador scheduling: policy a nombre (RR), nice, affinity, ctx switches.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import procfs                        # noqa: E402
from analizadores import memoria, scheduling  # noqa: E402
import _fixtures as fx               # noqa: E402

MAPS = (
    "00400000-00401000 r-xp 00000000 08:01 100 /usr/bin/prog\n"   # text  (x, archivo)
    "00500000-00501000 rw-p 00000000 08:01 100 /usr/bin/prog\n"   # data  (rw archivo)
    "00600000-00602000 rw-p 00000000 00:00 0 [heap]\n"            # heap  (8 kB)
    "00700000-00701000 rw-p 00000000 00:00 0 [stack]\n"           # stack
    "00800000-00803000 r-xp 00000000 08:01 5 /lib/libc.so.6\n"    # lib   (12 kB)
)


class TestTipoFd(unittest.TestCase):
    def test_infiere_tipos(self):
        self.assertEqual(procfs._tipo_fd("socket:[123]"), "socket")
        self.assertEqual(procfs._tipo_fd("pipe:[9]"), "pipe")
        self.assertEqual(procfs._tipo_fd("anon_inode:[eventfd]"), "anon")
        self.assertEqual(procfs._tipo_fd("/dev/pts/0"), "tty")
        self.assertEqual(procfs._tipo_fd("/dev/null"), "dev")
        self.assertEqual(procfs._tipo_fd("/home/user/archivo.txt"), "file")


class TestLeerMaps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fx.montar(self.tmp)
        fx.proceso(self.tmp, 1234, maps=MAPS)

    def test_agrupa_segmentos(self):
        seg = procfs.leer_maps(1234)
        self.assertEqual(seg["n_segmentos"], 5)
        self.assertEqual(seg["heap_kb"], 8)     # 0x2000 = 8 kB
        self.assertEqual(seg["lib_kb"], 12)     # 0x3000 = 12 kB
        self.assertEqual(seg["text_kb"], 4)     # 0x1000 = 4 kB
        self.assertEqual(seg["stack_kb"], 4)
        self.assertEqual(seg["total_kb"], 32)   # 4+4+8+4+12


class TestThreadsProcfs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fx.montar(self.tmp)
        tasks = [
            (1234, fx.construir_stat(pid=1234, comm="main", utime=10), None),
            (1240, fx.construir_stat(pid=1240, comm="worker", utime=5), None),
        ]
        fx.proceso(self.tmp, 1234, tasks=tasks)

    def test_listar_tids(self):
        self.assertEqual(sorted(procfs.listar_tids(1234)), [1234, 1240])

    def test_leer_stat_thread(self):
        st = procfs.leer_stat_thread(1234, 1240)
        self.assertEqual(st["comm"], "worker")


class TestAnalizadorMemoria(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fx.montar(self.tmp)
        fx.proceso(self.tmp, 1234,
                   stat=fx.construir_stat(pid=1234, utime=1, stime=1),
                   status=fx.construir_status(rss=4096), maps=MAPS)

    def test_extrae_memoria_por_pid(self):
        datos = memoria.extraer()
        self.assertIn(1234, datos)
        self.assertEqual(datos[1234]["vmrss"], 4096)
        self.assertEqual(datos[1234]["minflt"], 200)   # del stat de muestra
        self.assertEqual(datos[1234]["majflt"], 3)
        self.assertEqual(datos[1234]["segmentos"]["heap_kb"], 8)


class TestAnalizadorScheduling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fx.montar(self.tmp)
        extra = ("Cpus_allowed_list:\t0-15\n"
                 "voluntary_ctxt_switches:\t100\n"
                 "nonvoluntary_ctxt_switches:\t5\n")
        fx.proceso(self.tmp, 1234,
                   stat=fx.construir_stat(pid=1234, nice=0, policy=2),  # 2 = RR
                   status=fx.construir_status(extra=extra))

    def test_extrae_scheduling(self):
        datos = scheduling.extraer()
        self.assertEqual(datos[1234]["policy"], "RR")   # policy 2 decodificada
        self.assertEqual(datos[1234]["affinity"], "0-15")
        self.assertEqual(datos[1234]["vol_ctxt"], 100)
        self.assertEqual(datos[1234]["nonvol_ctxt"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
