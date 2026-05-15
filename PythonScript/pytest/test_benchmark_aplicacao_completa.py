import sys
import time
import json
import statistics
import platform
import subprocess
from pathlib import Path
import psutil
import wmi
import threading

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent))
from main import main


# ===========================
# CONFIG RUNS
# ===========================
WARMUP_RUNS = 1
USED_RUNS = 9

process = psutil.Process()

aliases = {
    "MA2023127403": "notebook"
}

machine_name = platform.node().strip().upper()
machine_name = aliases.get(machine_name, machine_name.lower())


# def get_cpu_percent():
#     return psutil.cpu_percent(interval=None)


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
        func()
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

        cpu_samples = []
        ram_samples = []

        read_iops_samples = []
        write_iops_samples = []
        read_bytes_samples = []
        write_bytes_samples = []

        executando = True

        def monitor():
            nonlocal executando

            process.cpu_percent(interval=None)

            prev_io = process.io_counters()
            last_time = time.perf_counter()

            while executando:
                time.sleep(0.1)

                cpu_samples.append(process.cpu_percent(interval=None))

                ram_samples.append(
                    process.memory_info().rss / (1024 * 1024)
                )

                current_io = process.io_counters()
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

        thread = threading.Thread(target=monitor)
        thread.start()

        func()

        executando = False
        thread.join()

        runs_cpu.append(max(cpu_samples) if cpu_samples else 0)
        runs_ram.append(max(ram_samples) if ram_samples else 0)

        runs_read_iops.append(max(read_iops_samples) if read_iops_samples else 0)
        runs_write_iops.append(max(write_iops_samples) if write_iops_samples else 0)

        runs_read_bytes.append(max(read_bytes_samples) if read_bytes_samples else 0)
        runs_write_bytes.append(max(write_bytes_samples) if write_bytes_samples else 0)

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
        # p.name
        str(p)
        for p in (BASE_DIR / "videos").iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".mov", ".avi", ".dav"}
    ]

    def run_txt():
        sys.argv = [
            "PythonScript.exe",
            "|".join(videos),
            "Arquivos -> lista de caminhos em .txt",
            "--benchmark_pytest"
        ]
        main()

    def run_simplificado():
        sys.argv = [
            "PythonScript.exe",
            "|".join(videos),
            "Vídeos -> tabela simplificada de informações em .csv",
            "--benchmark_pytest"
        ]
        main()

    def run_completo():
        sys.argv = [
            "PythonScript.exe",
            "|".join(videos),
            "Vídeos -> tabela completa de informações em .csv",
            "--benchmark_pytest"
        ]
        main()

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
        # nome, dados = medir_cpu_ram(name, fn, WARMUP_RUNS+USED_RUNS, WARMUP_RUNS)
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
            # merged[k]["statistics"]["cpu"] = v["cpu"]
            # merged[k]["statistics"]["ram"] = v["ram"]            
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
        BASE_DIR / f"test_benchmark_aplicacao_completa_{machine_name}.json",
        "w",
        encoding="utf-8-sig"
    ) as f:
        json.dump(output, f, indent=4)


if __name__ == "__main__":
    if "--run-once" in sys.argv:
        test_pipeline()