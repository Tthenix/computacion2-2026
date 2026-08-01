"""
Analizador Threads / LWPs (FASE 5, con CPU% por thread en FASE 7).

Un thread en Linux es un LWP (Light Weight Process): comparte memoria con su
proceso pero tiene su propio TID y su propia entrada /proc/<pid>/task/<tid>/.
Por thread mostramos: TID, nombre, estado, CPU% y context switches.

=== CPU% POR THREAD (FASE 7) ===
Mismo principio que el CPU% por proceso, un nivel más abajo: utime+stime de
/proc/<pid>/task/<tid>/stat son jiffies ACUMULADOS del thread. El % de "ahora"
es el delta entre dos lecturas dividido por el delta de CPU total del sistema.
Por eso el analizador guarda estado (prev por (pid,tid) y prev del total).
"""
import procfs
from analizadores.base import bucle

NOMBRE = "threads"


def correr(snapshot, intervalo, corriendo):
    # Estado para el delta de jiffies por thread (persiste entre iteraciones
    # gracias al closure). prev_total en lista para poder mutarlo desde dentro.
    prev = {}            # (pid, tid) -> jiffies (utime+stime) de la lectura previa
    prev_total = [0]     # jiffies de CPU total del sistema en la lectura previa

    def extraer():
        # Denominador: cuánto avanzó la CPU total entre dos lecturas.
        total_ahora = procfs.leer_stat_sistema()["cpu"].get("total", 0)
        d_total = total_ahora - prev_total[0]
        if d_total <= 0:
            d_total = 1

        res = {}
        nuevo = {}
        for pid in procfs.listar_pids():
            tids = procfs.listar_tids(pid)
            if not tids:
                continue
            lista = []
            for tid in sorted(tids):
                st = procfs.leer_stat_thread(pid, tid)
                if st is None:
                    continue
                jiffies = st.get("utime", 0) + st.get("stime", 0)
                nuevo[(pid, tid)] = jiffies
                anterior = prev.get((pid, tid))
                cpu = 0.0 if anterior is None else 100.0 * (jiffies - anterior) / d_total

                status = procfs.leer_status_thread(pid, tid) or {}
                lista.append({
                    "tid": tid,
                    "nombre": st["comm"],
                    "estado": st["state"],
                    "cpu": round(cpu, 1),
                    "vol_ctxt": procfs._a_int(status.get("voluntary_ctxt_switches", 0)),
                    "nonvol_ctxt": procfs._a_int(status.get("nonvoluntary_ctxt_switches", 0)),
                })
            comm = next((t["nombre"] for t in lista if t["tid"] == pid), "?")
            res[pid] = {"comm": comm, "count": len(lista), "lista": lista}

        prev.clear()
        prev.update(nuevo)
        prev_total[0] = total_ahora
        return res

    bucle(NOMBRE, snapshot, intervalo, corriendo, extraer)
