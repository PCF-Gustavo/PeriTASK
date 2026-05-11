import sys
import time
import json
import statistics
import platform
import subprocess
from pathlib import Path
import psutil
import wmi

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent))
from PythonScript import main


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


def get_cpu_percent():
    return psutil.cpu_percent(interval=None)


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

    runs_used = runs_all[ignorar:]

    return nome, {
        "time": {
            "mean": round(statistics.mean(runs_used), 4),
            "min": round(min(runs_used), 4),
            "max": round(max(runs_used), 4),
        }
    }


# ===========================
# BENCHMARK (CPU ONLY)
# ===========================

def medir_cpu_ram(nome, func, rodadas, ignorar):
    runs_cpu = []
    runs_ram = []

    for _ in range(rodadas):
        psutil.cpu_percent(interval=None)
        func()
        runs_cpu.append(psutil.cpu_percent(interval=None))
        runs_ram.append(psutil.virtual_memory().percent)
        runs_ram.append((process.memory_info().rss / psutil.virtual_memory().total) * 100)

    runs_cpu = runs_cpu[ignorar:]
    runs_ram = runs_ram[ignorar:]

    return nome, {
        "cpu": {
            "mean": round(statistics.mean(runs_cpu), 2),
            "min": round(min(runs_cpu), 2),
            "max": round(max(runs_cpu), 2),
        },
        "ram": {
            "mean": round(statistics.mean(runs_ram), 2),
            "min": round(min(runs_ram), 2),
            "max": round(max(runs_ram), 2),
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
        nome, dados = medir_cpu_ram(name, fn, WARMUP_RUNS+USED_RUNS, WARMUP_RUNS)
        resultados_cpu.append({nome: dados})

    merged = {}

    for item in resultados_time:
        for k, v in item.items():
            merged[k] = {
                "statistics": {
                    "time": v["time"]
                }
            }

    for item in resultados_cpu:
        for k, v in item.items():
            merged[k]["statistics"]["cpu"] = v["cpu"]
            merged[k]["statistics"]["ram"] = v["ram"]

    output = {
        "run_info": {
            "warmup_runs": WARMUP_RUNS,
            "runs_used": USED_RUNS
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