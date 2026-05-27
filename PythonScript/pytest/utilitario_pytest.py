import os
import sys
import csv
import json
import time
import base64
import shutil
import platform
import statistics
import subprocess
from pathlib import Path
from itertools import product
import psutil

# ===========================
# CONFIG RUNS
# ===========================
WARMUP_RUNS = 1
USED_RUNS = 9

# =========================
# PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parent          # PeriTASK\PythonScript\pytest
ROOT = BASE_DIR.parent                             # PeriTASK\PythonScript
PROJECT_ROOT = BASE_DIR.parents[1]                 # PeriTASK

EXE_PATH = PROJECT_ROOT / "Instalador" / "build" / "main.dist" / "PythonScript.exe"

PASTA_SAIDA_PYTEST = Path(os.getenv("USERPROFILE")) / "Desktop" / "PeriTASK_pytest"
PASTA_TEMP_UI_CLI = Path(os.getenv("TEMP")) / "PeriTASK_UI_CLI_Test"

sys.path.append(str(ROOT))

from utilitario.executor_comando import carregar_catalogo_de_comandos


# =========================
# MACHINE NAME
# =========================

ALIASES = {
    "MA2023127403": "notebook",
    "MASETEC31224": "workstation",
}


def get_machine_name():
    name = platform.node().strip().upper()
    return ALIASES.get(name, name.lower())


machine_name = get_machine_name()


# =========================
# CATÁLOGO DE COMANDOS
# =========================

def obter_catalogo_de_comandos_ids():
    catalogo_de_comandos = carregar_catalogo_de_comandos()
    return [comando["id"] for comando in catalogo_de_comandos["comandos"]]


def criar_argumento_ui(comando_id, controls=None):
    if controls is None:
        controls = {}

    payload = {
        "comando_id": comando_id,
        "controls": controls,
    }

    json_payload = json.dumps(payload, ensure_ascii=False)
    return base64.b64encode(json_payload.encode("utf-8")).decode("utf-8")


# =========================
# INPUTS DE TESTE
# =========================
def obter_arquivos_recursos_teste():
    pasta_recursos = BASE_DIR / "recursos"
    arquivos = [str(p) for p in pasta_recursos.rglob("*") if p.is_file()]
    assert arquivos, f"Nenhum arquivo encontrado em: {pasta_recursos}"
    return arquivos


def obter_arquivos_argumentos_teste():
    return "|".join(obter_arquivos_recursos_teste())


def criar_arquivo_txt_temporario_para_ui():
    PASTA_TEMP_UI_CLI.mkdir(parents=True, exist_ok=True)

    arquivo = PASTA_TEMP_UI_CLI / "arquivo_teste.txt"
    arquivo.write_text(
        "arquivo usado no teste de integração UI -> Python",
        encoding="utf-8",
    )

    return arquivo


# =========================
# USERINTERFACE.EXE
# =========================

def encontrar_userinterface_exe():
    candidatos = [
        PROJECT_ROOT / "UserInterface" / "bin" / "x64" / "Debug" / "net8.0-windows" / "UserInterface.exe",
        PROJECT_ROOT / "UserInterface" / "bin" / "Debug" / "net8.0-windows" / "UserInterface.exe",
        PROJECT_ROOT / "UserInterface" / "bin" / "x64" / "Release" / "net8.0-windows" / "UserInterface.exe",
        PROJECT_ROOT / "UserInterface" / "bin" / "Release" / "net8.0-windows" / "UserInterface.exe",
    ]

    for candidato in candidatos:
        if candidato.exists():
            return candidato

    bin_dir = PROJECT_ROOT / "UserInterface" / "bin"
    if bin_dir.exists():
        encontrados = list(bin_dir.rglob("UserInterface.exe"))
        if encontrados:
            return encontrados[0]

    raise FileNotFoundError(
        "UserInterface.exe não encontrado. Compile o projeto UserInterface em Debug antes de rodar o teste."
    )


def criar_args_ui_benchmark(rota, arquivo_teste):
    return [
        str(encontrar_userinterface_exe()),
        "--benchmark",
        "--route",
        rota,
        str(arquivo_teste),
    ]


# =========================
# PYTHONSCRIPT.EXE
# =========================

def exigir_pythonscript_exe():
    assert EXE_PATH.exists(), f"Exe não encontrado: {EXE_PATH}"
    return EXE_PATH


def criar_args_pythonscript_exe(func_id):
    return [
        str(exigir_pythonscript_exe()),
        obter_arquivos_argumentos_teste(),
        criar_argumento_ui(func_id),
        "--benchmark",
    ]


# =========================
# SUBPROCESS
# =========================

def executar_subprocess(args, timeout=300, imprimir_saida=False):
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )

    if imprimir_saida:
        print("\n===== STDOUT =====\n")
        print(result.stdout)
        print("\n===== STDERR =====\n")
        print(result.stderr)

    return result


# =========================
# PASTA DE SAÍDA / VALIDAÇÕES
# =========================

def limpar_pasta_saida_pytest():
    if PASTA_SAIDA_PYTEST.exists():
        shutil.rmtree(PASTA_SAIDA_PYTEST)

    PASTA_SAIDA_PYTEST.mkdir(parents=True, exist_ok=True)


def validar_arquivo(path: Path):
    assert path.exists(), f"Arquivo não foi criado: {path}"
    assert path.stat().st_size > 0, f"Arquivo vazio: {path}"


def validar_csv(path: Path):
    validar_arquivo(path)

    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    assert len(rows) >= 2, "CSV sem header ou sem linhas"
    assert len(rows[0]) > 0, "CSV sem colunas"


def validar_txt(path: Path):
    validar_arquivo(path)

    content = path.read_text(encoding="utf-8-sig").strip()

    assert content, "TXT vazio"
    assert len(content.splitlines()) > 0, "TXT sem linhas válidas"


def validar_saidas_genericas(pasta_saida: Path = PASTA_SAIDA_PYTEST):
    arquivos = list(pasta_saida.glob("*"))

    for f in arquivos:
        validar_arquivo(f)

        if f.suffix == ".csv":
            validar_csv(f)
        elif f.suffix == ".txt":
            validar_txt(f)


# =========================
# BENCHMARK OUTPUT PATHS
# =========================

def benchmark_overhead_contrato_path():
    return BASE_DIR / f"teste_benchmark_overhead_contrato_{machine_name}.json"

def benchmark_comunicacao_UI_PythonScript_path():
    return BASE_DIR / f"teste_benchmark_comunicacao_UI_PythonScript_{machine_name}.json"

def benchmark_build_path():
    return BASE_DIR / f"teste_benchmark_build_{machine_name}.json"

def benchmark_inicializacao_path():
    return BASE_DIR / f"teste_benchmark_inicializacao_{machine_name}.json"

def benchmark_app_exe_path():
    return BASE_DIR / f"teste_benchmark_app_exe_{machine_name}.json"

def benchmark_engine_python_path():
    return BASE_DIR / f"teste_benchmark_engine_python_{machine_name}.json"

def benchmark_report_path():
    return BASE_DIR / f"BenchmarkReport_{machine_name}.json"

def benchmark_report_referencia_path():
    return BASE_DIR / f"BenchmarkReport_{machine_name}_referencia.json"

def benchmark_report_comparacao_path():
    return BASE_DIR / f"BenchmarkReport_{machine_name}_comparacao.json"


# =========================
# SISTEMA
# =========================

def get_gpu_name():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode(errors="replace").strip()
    except Exception:
        pass

    try:
        import wmi

        c = wmi.WMI()
        gpus = []
        for gpu in c.Win32_VideoController():
            if gpu.Name:
                gpus.append(gpu.Name)
        return " | ".join(gpus) if gpus else "unknown"
    except Exception:
        return "unknown"


def get_gpu_vram_gb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
        )
        vram_mb = float(out.decode(errors="replace").strip().split("\n")[0])
        return round(vram_mb / 1024, 2)
    except Exception:
        pass

    try:
        import wmi

        c = wmi.WMI()
        total = 0
        for gpu in c.Win32_VideoController():
            if gpu.AdapterRAM:
                total += int(gpu.AdapterRAM)
        if total > 0:
            return round(total / (1024 ** 3), 2)
    except Exception:
        pass

    return None


def get_disk_type():
    try:
        import wmi

        c = wmi.WMI()
        for disk in c.Win32_DiskDrive():
            model = (disk.Model or "").lower()
            if "nvme" in model:
                return "NVME SSD"
            elif "ssd" in model:
                return "SSD SATA"
            else:
                return "HDD"
    except Exception:
        return "unknown"

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
            "vram_gb": get_gpu_vram_gb(),
        },
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.node(),
        "machine_alias": machine_name,
    }


# =========================
# BENCHMARK HELPERS
# =========================

def estatisticas_tempo(valores):
    return {
        "mean": round(statistics.mean(valores), 4),
        "min": round(min(valores), 4),
        "max": round(max(valores), 4),
    }


def estatisticas_float(valores, casas=2):
    return {
        "mean": round(statistics.mean(valores), casas),
        "min": round(min(valores), casas),
        "max": round(max(valores), casas),
    }


def medir_time_subprocess(nome, args_factory, rodadas, ignorar, timeout=300):
    runs_all = []

    for _ in range(rodadas):
        inicio = time.perf_counter()
        result = subprocess.run(
            args_factory(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        fim = time.perf_counter()

        assert result.returncode == 0, (
            f"Execução falhou em '{nome}' com código {result.returncode}"
        )

        runs_all.append(fim - inicio)

    used_runs = runs_all[ignorar:]

    return nome, {
        "time_s": estatisticas_tempo(used_runs)
    }


def medir_time_funcao(nome, func, rodadas, ignorar):
    runs_all = []

    for _ in range(rodadas):
        inicio = time.perf_counter()
        func()
        fim = time.perf_counter()
        runs_all.append(fim - inicio)

    used_runs = runs_all[ignorar:]

    return nome, {
        "time_s": estatisticas_tempo(used_runs)
    }


def executar_com_monitor(args):
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        proc_ps = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        proc.wait()
        return {
            "cpu": [],
            "ram": [],
            "read_iops": [],
            "write_iops": [],
            "read_bytes": [],
            "write_bytes": [],
        }

    cpu_samples = []
    ram_samples = []
    read_iops_samples = []
    write_iops_samples = []
    read_bytes_samples = []
    write_bytes_samples = []

    try:
        prev_io = proc_ps.io_counters()
    except psutil.NoSuchProcess:
        proc.wait()
        return {
            "cpu": [],
            "ram": [],
            "read_iops": [],
            "write_iops": [],
            "read_bytes": [],
            "write_bytes": [],
        }

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
        "write_bytes": write_bytes_samples,
    }


def medir_cpu_ram_io(nome, args_factory, rodadas, ignorar):
    runs_cpu = []
    runs_ram = []
    runs_read_iops = []
    runs_write_iops = []
    runs_read_bytes = []
    runs_write_bytes = []

    for _ in range(rodadas):
        stats = executar_com_monitor(args_factory())

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
        "cpu_peak": estatisticas_float(runs_cpu, casas=2),
        "ram_peak_mb": estatisticas_float(runs_ram, casas=2),
        "io": {
            "read_iops": estatisticas_float(runs_read_iops, casas=2),
            "write_iops": estatisticas_float(runs_write_iops, casas=2),
            "read_throughput_bps": estatisticas_float(runs_read_bytes, casas=2),
            "write_throughput_bps": estatisticas_float(runs_write_bytes, casas=2),
        },
    }




def normalizar_valor_para_id(valor):
    valor = str(valor)
    valor = valor.strip().lower()

    substituicoes = {
        " ": "_",
        "-": "_",
        "->": "_",
        "/": "_",
        "\\": "_",
        ".": "_",
        ",": "_",
        ":": "_",
        ";": "_",
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }

    for antigo, novo in substituicoes.items():
        valor = valor.replace(antigo, novo)

    while "__" in valor:
        valor = valor.replace("__", "_")

    return valor.strip("_")


def obter_valores_benchmark_do_control(control):
    tipo = control.get("type")
    control_id = control.get("id")

    if tipo == "dropdown":
        items = control.get("items") or []

        if items:
            return [
                {
                    "id": control_id,
                    "value": str(item),
                    "label": normalizar_valor_para_id(item),
                }
                for item in items
            ]

        valor_default = str(control.get("default", ""))
        return [
            {
                "id": control_id,
                "value": valor_default,
                "label": normalizar_valor_para_id(valor_default),
            }
        ]

    if tipo == "checkbox":
        return [
            {
                "id": control_id,
                "value": False,
                "label": "false",
            },
            {
                "id": control_id,
                "value": True,
                "label": "true",
            },
        ]

    if tipo == "editbox":
        valor_default = str(control.get("default", ""))
        return [
            {
                "id": control_id,
                "value": valor_default,
                "label": normalizar_valor_para_id(valor_default),
            }
        ]

    return [
        {
            "id": control_id,
            "value": control.get("default"),
            "label": normalizar_valor_para_id(control.get("default", "")),
        }
    ]


def montar_benchmark_id(comando_id, combinacao):
    partes = [comando_id]

    for item in combinacao:
        control_id = item["id"]
        label = item["label"]

        if label:
            partes.append(f"{control_id}='{label}'")
        else:
            partes.append(f"{control_id}=''")

    return "|".join(partes)


def expandir_comando_em_cenarios_benchmark(comando):
    comando_id = comando["id"]

    controls_config = (
        comando
        .get("ui", {})
        .get("controls", [])
    )

    if not controls_config:
        return [
            {
                "benchmark_id": comando_id,
                "comando_id": comando_id,
                "controls": {},
            }
        ]

    listas_de_valores = [
        obter_valores_benchmark_do_control(control)
        for control in controls_config
    ]

    cenarios = []

    for combinacao in product(*listas_de_valores):
        controls = {
            item["id"]: item["value"]
            for item in combinacao
        }

        benchmark_id = montar_benchmark_id(
            comando_id,
            combinacao,
        )

        cenarios.append(
            {
                "benchmark_id": benchmark_id,
                "comando_id": comando_id,
                "controls": controls,
            }
        )

    return cenarios


def obter_cenarios_benchmark():
    catalogo_de_comandos = carregar_catalogo_de_comandos()

    cenarios = []

    for comando in catalogo_de_comandos.get("comandos", []):
        comando_id = comando.get("id", "")

        if comando_id.startswith("teste_"):
            continue

        cenarios.extend(
            expandir_comando_em_cenarios_benchmark(comando)
        )

    return cenarios