"""
Recolector central (FASE 2).

Responsabilidad: recorrer /proc, armar la lista de procesos con sus datos, y
calcular CPU% (por proceso y global). En fases posteriores se parte a
multiproceso; por ahora es una clase que se llama en un loop.

=== POR QUÉ ES UNA CLASE CON ESTADO ===
El CPU% NO se puede sacar de una sola lectura. /proc/<pid>/stat da utime+stime
como ACUMULADO de jiffies desde que el proceso arrancó, no un porcentaje. Para
saber cuánta CPU usa AHORA hay que comparar dos lecturas separadas en el tiempo:

    cpu% = 100 * (jiffies_proc_ahora - jiffies_proc_antes)
                 -----------------------------------------
                 (jiffies_cpu_total_ahora - antes)

Por eso el recolector guarda la lectura anterior (self._prev_*) entre llamadas.
La 1ra llamada no tiene con qué comparar => CPU% = 0 para todos (esperado).

Un JIFFY es un tick del reloj del kernel. CLK_TCK jiffies = 1 segundo
(normalmente 100, o sea 1 jiffy = 10 ms). Concepto de clase 3/4.
"""
import os
import procfs


class Recolector:
    def __init__(self):
        # Estado para el cálculo de deltas entre snapshots consecutivos.
        self._prev_proc = {}      # {pid: utime+stime en jiffies (lectura previa)}
        self._prev_cpu_total = 0  # jiffies totales de CPU (todas las modes) previos
        self._prev_cpu = {}       # dict cpu de /proc/stat previo (para % global)

    # -----------------------------------------------------------------------
    # Snapshot por proceso (vista Resumen)
    # -----------------------------------------------------------------------
    def snapshot_procesos(self):
        """
        Devuelve lista de dicts, uno por proceso vivo, con:
            pid, ppid, usuario, estado, cpu, rss_kb, threads, comando
        Calcula CPU% comparando con la lectura anterior.
        """
        # 1) CPU total del sistema AHORA (denominador del %).
        stat_sis = procfs.leer_stat_sistema()
        cpu_total_ahora = stat_sis["cpu"].get("total", 0)
        delta_total = cpu_total_ahora - self._prev_cpu_total
        if delta_total <= 0:
            delta_total = 1  # evitar división por cero en la 1ra pasada

        procesos = []
        nuevo_prev_proc = {}

        for pid in procfs.listar_pids():
            stat = procfs.leer_stat(pid)
            if stat is None:
                continue  # murió entre listar y leer

            # jiffies acumulados de CPU de ESTE proceso
            jiffies_proc = stat.get("utime", 0) + stat.get("stime", 0)
            nuevo_prev_proc[pid] = jiffies_proc

            # delta contra la lectura anterior de ESTE mismo pid
            prev = self._prev_proc.get(pid)
            if prev is None:
                cpu_pct = 0.0  # proceso nuevo o 1ra pasada: sin referencia
            else:
                delta_proc = jiffies_proc - prev
                # % de la capacidad total de CPU (sumando todos los cores = 100%)
                cpu_pct = 100.0 * delta_proc / delta_total

            # datos extra de status
            status = procfs.leer_status(pid)
            if status:
                ppid = procfs._a_int(status.get("PPid", 0))
                threads = procfs._a_int(status.get("Threads", 1))
                # Uid: 'real efectivo saved fs' -> tomo el real (primero)
                uid = status.get("Uid", "0").split()[0] if status.get("Uid") else "0"
                usuario = procfs.usuario_de_uid(uid)
                # VmRSS: '1234 kB'
                rss = status.get("VmRSS", "0 kB").split()[0] if status.get("VmRSS") else "0"
                rss_kb = procfs._a_int(rss)
            else:
                ppid, threads, usuario, rss_kb = stat.get("ppid", 0), stat.get("num_threads", 1), "?", 0

            comando = procfs.leer_cmdline(pid)
            if not comando:
                comando = f"[{stat['comm']}]"  # kernel thread

            procesos.append({
                "pid": pid,
                "ppid": ppid,
                "usuario": usuario,
                "estado": stat["state"],
                "cpu": round(cpu_pct, 1),
                "rss_kb": rss_kb,
                "threads": threads,
                "comando": comando,
            })

        # 2) Guardar estado para el próximo delta.
        self._prev_proc = nuevo_prev_proc
        self._prev_cpu_total = cpu_total_ahora

        return procesos

    # -----------------------------------------------------------------------
    # Snapshot del sistema (vista Sistema)
    # -----------------------------------------------------------------------
    def snapshot_sistema(self, procesos=None):
        """
        Devuelve dict con stats globales: CPU% por modo, memoria, load,
        totales de procesos por estado, zombies, uptime.
        Si le paso la lista de 'procesos' (de snapshot_procesos), agrega
        totales por estado y top consumidores sin recorrer /proc de nuevo.
        """
        stat_sis = procfs.leer_stat_sistema()
        cpu = stat_sis["cpu"]

        # --- CPU% global por delta (mismo principio que por proceso) ---
        total_ahora = cpu.get("total", 0)
        idle_ahora = cpu.get("idle_all", 0)
        prev_total = self._prev_cpu.get("total", 0)
        prev_idle = self._prev_cpu.get("idle_all", 0)

        d_total = total_ahora - prev_total
        d_idle = idle_ahora - prev_idle
        if d_total <= 0:
            d_total = 1

        uso_pct = 100.0 * (d_total - d_idle) / d_total
        # desglose por modo (user/system/idle/iowait)
        def pct(modo_ahora, modo_key):
            prev = self._prev_cpu.get(modo_key, 0)
            return 100.0 * (cpu.get(modo_key, 0) - prev) / d_total

        desglose = {
            "user": round(pct(cpu.get("user", 0), "user"), 1),
            "system": round(pct(cpu.get("system", 0), "system"), 1),
            "idle": round(pct(cpu.get("idle", 0), "idle"), 1),
            "iowait": round(pct(cpu.get("iowait", 0), "iowait"), 1),
        }
        self._prev_cpu = cpu  # guardar para el próximo delta

        # --- memoria ---
        mem = procfs.leer_meminfo()

        # --- load ---
        load = procfs.leer_loadavg()

        # --- totales por estado (si me pasaron la lista de procesos) ---
        por_estado = {}
        zombies = 0
        threads_total = 0
        if procesos is not None:
            for p in procesos:
                est = p["estado"]
                por_estado[est] = por_estado.get(est, 0) + 1
                if est == "Z":
                    zombies += 1
                threads_total += p["threads"] if isinstance(p["threads"], int) else 0

        return {
            "cpu_uso": round(uso_pct, 1),
            "cpu_desglose": desglose,
            "mem_total_kb": mem.get("MemTotal", 0),
            "mem_libre_kb": mem.get("MemFree", 0),
            "mem_disp_kb": mem.get("MemAvailable", 0),
            "buffers_kb": mem.get("Buffers", 0),
            "cached_kb": mem.get("Cached", 0),
            "swap_total_kb": mem.get("SwapTotal", 0),
            "swap_libre_kb": mem.get("SwapFree", 0),
            "load": load,
            "uptime_seg": procfs.leer_uptime(),
            "btime": stat_sis["btime"],
            "procs_total": len(procesos) if procesos is not None else load.get("procs_total", 0),
            "por_estado": por_estado,
            "zombies": zombies,
            "threads_total": threads_total,
            "ncpus": os.cpu_count() or 1,
        }
