"""
===========================================================
BENCHMARK: EXECUÇÃO REAL DO EXE (END-TO-END)
===========================================================

Este benchmark mede a execução completa da aplicação a partir
do executável (PythonScript.exe), incluindo todos os custos
reais percebidos pelo usuário.

✔ O que este teste mede:
- Tempo total de execução (startup + processamento)
- Tempo de inicialização do Python/Nuitka
- Carregamento de bibliotecas
- Criação de processo (subprocess)
- Uso real de CPU, RAM e IO do EXE

✖ O que este teste NÃO isola:
- Não separa startup de execução (mede tudo junto)

📌 Interpretação:
Este teste representa o desempenho real da ferramenta em uso
operacional, exatamente como o usuário final experimenta.

👉 Em resumo:
Este é um benchmark da APLICAÇÃO COMPLETA.

⚠️ Observação:
Diferenças entre este teste e o benchmark Python puro indicam
o overhead introduzido pelo empacotamento e inicialização.
"""

import sys
import time
import json
import statistics
import platform
import subprocess
from pathlib import Path
import psutil
import wmi
import pytest
from utilitario_pytest import BASE_DIR, ROOT, EXE_PATH, machine_name
sys.path.append(str(ROOT))
from utilitario.outros import obter_videos

# ===========================
# CONFIG RUNS
# ===========================
WARMUP_RUNS = 1
USED_RUNS = 9


if not EXE_PATH.exists():
        pytest.skip(f"Exe não encontrado: {EXE_PATH}")



def get_gpu_name():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except:
        pass

    try:
        c = wmi.WMI()
        gpus = []
        for gpu in c.Win32_VideoController():
            if gpu.Name:
                gpus.append(gpu.Name)
        return " | ".join(gpus) if gpus else "unknown"
    except:
        return "unknown"


def get_gpu_vram_gb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL
        )
        vram_mb = float(out.decode().strip().split("\n")[0])
        return round(vram_mb / 1024, 2)
    except:
        pass

    try:
        c = wmi.WMI()
        total = 0
        for gpu in c.Win32_VideoController():
            if gpu.AdapterRAM:
                total += int(gpu.AdapterRAM)
        if total > 0:
            return round(total / (1024 ** 3), 2)
    except:
        pass

    return None


def get_disk_type():
    try:
        c = wmi.WMI()
        for disk in c.Win32_DiskDrive():
            model = (disk.Model or "").lower()
            if "nvme" in model:
                return "NVME SSD"
            elif "ssd" in model:
                return "SSD SATA"
            else:
                return "HDD"
    except:
        return "unknown"


def collect_static_system_info():
    cpu_freq = psutil.cpu_freq()

    return {
        "cpu": {
            "name": platform.processor(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "freq_mhz": round(cpu_freq.max if cpu_freq else 0, 2),
        },
        "ram": {
            "total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        },
        "disk": {
            "type": get_disk_type(),
        },
        "gpu": {
            "name": get_gpu_name(),
            "vram_gb": get_gpu_vram_gb()
        },
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.node(),
        "machine_alias": machine_name
    }


# ===========================
# BENCHMARK (TIME)
# ===========================

def medir_time(nome, func, rodadas, ignorar):
    runs_all = []

    for _ in range(rodadas):
        inicio = time.perf_counter()
        subprocess.run(func(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        fim = time.perf_counter()
        runs_all.append(fim - inicio)

    used_runs = runs_all[ignorar:]

    return nome, {
        "time_s": {
            "mean": round(statistics.mean(used_runs), 4),
            "min": round(min(used_runs), 4),
            "max": round(max(used_runs), 4),
        }
    }


# ===========================
# EXECUTOR COM MONITOR
# ===========================

def executar_com_monitor(args):

    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    proc_ps = psutil.Process(proc.pid)

    cpu_samples = []
    ram_samples = []
    read_iops_samples = []
    write_iops_samples = []
    read_bytes_samples = []
    write_bytes_samples = []

    prev_io = proc_ps.io_counters()
    last_time = time.perf_counter()

    while proc.poll() is None:
        time.sleep(0.1)

        try:
            cpu_samples.append(proc_ps.cpu_percent(interval=None))
            ram_samples.append(proc_ps.memory_info().rss / (1024 * 1024))

            current_io = proc_ps.io_counters()
        
        except psutil.NoSuchProcess:
            break
        
        current_time = time.perf_counter()

        dt = current_time - last_time
        if dt <= 0:
            dt = 0.1

        read_ops = current_io.read_count - prev_io.read_count
        write_ops = current_io.write_count - prev_io.write_count

        read_bytes = current_io.read_bytes - prev_io.read_bytes
        write_bytes = current_io.write_bytes - prev_io.write_bytes

        read_iops_samples.append(read_ops / dt)
        write_iops_samples.append(write_ops / dt)

        read_bytes_samples.append(read_bytes / dt)
        write_bytes_samples.append(write_bytes / dt)

        prev_io = current_io
        last_time = current_time

    return {
        "cpu": cpu_samples,
        "ram": ram_samples,
        "read_iops": read_iops_samples,
        "write_iops": write_iops_samples,
        "read_bytes": read_bytes_samples,
        "write_bytes": write_bytes_samples
    }


# ===========================
# BENCHMARK
# ===========================

def medir_cpu_ram_io(nome, func, rodadas, ignorar):
    runs_cpu = []
    runs_ram = []
    runs_read_iops = []
    runs_write_iops = []
    runs_read_bytes = []
    runs_write_bytes = []

    for _ in range(rodadas):

        stats = executar_com_monitor(func())

        runs_cpu.append(max(stats["cpu"]) if stats["cpu"] else 0)
        runs_ram.append(max(stats["ram"]) if stats["ram"] else 0)

        runs_read_iops.append(max(stats["read_iops"]) if stats["read_iops"] else 0)
        runs_write_iops.append(max(stats["write_iops"]) if stats["write_iops"] else 0)

        runs_read_bytes.append(max(stats["read_bytes"]) if stats["read_bytes"] else 0)
        runs_write_bytes.append(max(stats["write_bytes"]) if stats["write_bytes"] else 0)

    runs_cpu = runs_cpu[ignorar:]
    runs_ram = runs_ram[ignorar:]
    runs_read_iops = runs_read_iops[ignorar:]
    runs_write_iops = runs_write_iops[ignorar:]
    runs_read_bytes = runs_read_bytes[ignorar:]
    runs_write_bytes = runs_write_bytes[ignorar:]

    return nome, {
        "cpu_peak": {
            "mean": round(statistics.mean(runs_cpu), 2),
            "min": round(min(runs_cpu), 2),
            "max": round(max(runs_cpu), 2),
        },
        "ram_peak_mb": {
            "mean": round(statistics.mean(runs_ram), 2),
            "min": round(min(runs_ram), 2),
            "max": round(max(runs_ram), 2),
        },

        "io": {
            "read_iops": {
                "mean": round(statistics.mean(runs_read_iops), 2),
                "min": round(min(runs_read_iops), 2),
                "max": round(max(runs_read_iops), 2),
            },
            "write_iops": {
                "mean": round(statistics.mean(runs_write_iops), 2),
                "min": round(min(runs_write_iops), 2),
                "max": round(max(runs_write_iops), 2),
            },
            "read_throughput_bps": {
                "mean": round(statistics.mean(runs_read_bytes), 2),
                "min": round(min(runs_read_bytes), 2),
                "max": round(max(runs_read_bytes), 2),
            },
            "write_throughput_bps": {
                "mean": round(statistics.mean(runs_write_bytes), 2),
                "min": round(min(runs_write_bytes), 2),
                "max": round(max(runs_write_bytes), 2),
            }
        }
    }


# ===========================
# TEST PIPELINE
# ===========================

def test_pipeline():
    system = collect_static_system_info()

    videos = [
        str(p)
        for p in (BASE_DIR / "videos").iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".mov", ".avi", ".dav"}
    ]
    videos = obter_videos(list((BASE_DIR / "videos").iterdir()))
    videos_argumentos = "|".join(str(v) for v in videos)

    def run_txt():
        return [
            str(EXE_PATH),
            videos_argumentos,
            "lista_caminhos_txt",
            "--benchmark"
        ]

    def run_simplificado():
        return [
            str(EXE_PATH),
            videos_argumentos,
            "videos_csv_simplificado",
            "--benchmark"
        ]

    def run_completo():
        return [
            str(EXE_PATH),
            videos_argumentos,
            "videos_csv_completo",
            "--benchmark"
        ]

    funcs = {
        "txt": run_txt,
        "simplificado": run_simplificado,
        "completo": run_completo
    }

    resultados_time = []
    resultados_cpu = []

    # FASE 1: TIME
    for name, fn in funcs.items():
        nome, dados = medir_time(name, fn, WARMUP_RUNS+USED_RUNS, WARMUP_RUNS)
        resultados_time.append({nome: dados})

    # FASE 2: CPU
    for name, fn in funcs.items():
        nome, dados = medir_cpu_ram_io(name, fn, WARMUP_RUNS+USED_RUNS, WARMUP_RUNS)
        resultados_cpu.append({nome: dados})

    merged = {}

    for item in resultados_time:
        for k, v in item.items():
            merged[k] = {
                "statistics": {
                    "time_s": v["time_s"]
                }
            }

    for item in resultados_cpu:
        for k, v in item.items():
            merged[k]["statistics"]["cpu_peak"] = v["cpu_peak"]
            merged[k]["statistics"]["ram_peak_mb"] = v["ram_peak_mb"]
            merged[k]["statistics"]["io"] = v["io"]

    output = {
        "run_info": {
            "warmup_runs": WARMUP_RUNS,
            "used_runs": USED_RUNS
        },
        "results": merged,
        "videos": [Path(v).name for v in videos],
        "system": system
    }

    with open(
        BASE_DIR / f"test_benchmark_app_exe_{machine_name}.json",
        "w",
        encoding="utf-8-sig"
    ) as f:
        json.dump(output, f, indent=4)


if __name__ == "__main__":
    if "--run-once" in sys.argv:
        test_pipeline()