"""
===========================================================
BENCHMARK: EXECUÇÃO DO APP EXE
===========================================================
Mede a performance do pipeline executado pelo executável
PythonScript.exe.
"""

import json
import subprocess
import time
import psutil

from utilitario_pytest import (
    WARMUP_RUNS,
    USED_RUNS,
    EXE_PATH,
    benchmark_app_exe_path,
    criar_argumento_ui,
    obter_arquivos_argumentos_teste,
    obter_cenarios_benchmark,
    exigir_pythonscript_exe,
    collect_static_system_info,
)


# ===========================
# ARGUMENTOS GENÉRICOS
# ===========================

def criar_argv_funcao(func_id, controls):
    return [
        str(EXE_PATH),
        obter_arquivos_argumentos_teste(),
        criar_argumento_ui(func_id, controls),
        "--benchmark",
    ]


def executar_app_exe_com_argv(argv):
    return subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

def medir_app_exe_funcao(nome, func, total_runs, warmup_runs):
    tempos = []
    cpu_peaks = []
    ram_peaks_mb = []
    read_iops = []
    write_iops = []
    read_throughput_bps = []
    write_throughput_bps = []

    for i in range(total_runs):
        inicio = time.perf_counter()

        processo = func()
        ps_proc = psutil.Process(processo.pid)

        cpu_peak = 0.0
        ram_peak_mb = 0.0

        read_count_inicio = 0
        write_count_inicio = 0
        read_bytes_inicio = 0
        write_bytes_inicio = 0

        read_count_fim = 0
        write_count_fim = 0
        read_bytes_fim = 0
        write_bytes_fim = 0

        try:
            io_inicio = ps_proc.io_counters()

            read_count_inicio = io_inicio.read_count
            write_count_inicio = io_inicio.write_count
            read_bytes_inicio = io_inicio.read_bytes
            write_bytes_inicio = io_inicio.write_bytes

            read_count_fim = read_count_inicio
            write_count_fim = write_count_inicio
            read_bytes_fim = read_bytes_inicio
            write_bytes_fim = write_bytes_inicio

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        t_io_inicio = time.perf_counter()
        t_io_fim = t_io_inicio

        while processo.poll() is None:
            try:
                cpu = ps_proc.cpu_percent(interval=0.05)
                ram_mb = ps_proc.memory_info().rss / (1024 * 1024)

                cpu_peak = max(cpu_peak, cpu)
                ram_peak_mb = max(ram_peak_mb, ram_mb)

                io_atual = ps_proc.io_counters()
                read_count_fim = io_atual.read_count
                write_count_fim = io_atual.write_count
                read_bytes_fim = io_atual.read_bytes
                write_bytes_fim = io_atual.write_bytes
                t_io_fim = time.perf_counter()

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

        stdout, stderr = processo.communicate()

        fim = time.perf_counter()

        assert processo.returncode == 0, (
            f"Execução do app exe falhou com código {processo.returncode}.\n\n"
            f"STDOUT:\n{stdout}\n\n"
            f"STDERR:\n{stderr}"
        )

        intervalo_io = max(t_io_fim - t_io_inicio, 0.000001)

        read_count_delta = read_count_fim - read_count_inicio
        write_count_delta = write_count_fim - write_count_inicio
        read_bytes_delta = read_bytes_fim - read_bytes_inicio
        write_bytes_delta = write_bytes_fim - write_bytes_inicio

        read_iops_run = read_count_delta / intervalo_io
        write_iops_run = write_count_delta / intervalo_io
        read_throughput_run = read_bytes_delta / intervalo_io
        write_throughput_run = write_bytes_delta / intervalo_io

        if i >= warmup_runs:
            tempos.append(round(fim - inicio, 4))
            cpu_peaks.append(round(cpu_peak, 2))
            ram_peaks_mb.append(round(ram_peak_mb, 2))
            read_iops.append(round(read_iops_run, 2))
            write_iops.append(round(write_iops_run, 2))
            read_throughput_bps.append(round(read_throughput_run, 2))
            write_throughput_bps.append(round(write_throughput_run, 2))

    def stats(valores):
        return {
            "mean": round(sum(valores) / len(valores), 4),
            "min": round(min(valores), 4),
            "max": round(max(valores), 4),
        }

    return nome, {
        "time_s": stats(tempos),
        "cpu_peak": stats(cpu_peaks),
        "ram_peak_mb": stats(ram_peaks_mb),
        "io": {
            "read_iops": stats(read_iops),
            "write_iops": stats(write_iops),
            "read_throughput_bps": stats(read_throughput_bps),
            "write_throughput_bps": stats(write_throughput_bps),
        },
    }


def obter_funcoes_benchmark():
    funcs = {}

    for cenario in obter_cenarios_benchmark():
        benchmark_id = cenario["benchmark_id"]
        comando_id = cenario["comando_id"]
        controls = cenario["controls"]

        funcs[benchmark_id] = (
            lambda cid=comando_id, ctrls=controls:
            executar_app_exe_com_argv(criar_argv_funcao(cid, ctrls))
        )

    return funcs


def teste_benchmark_app_exe():
    exigir_pythonscript_exe()

    system = collect_static_system_info()
    funcs = obter_funcoes_benchmark()
    assert funcs, "Nenhuma função encontrada em catalogo_de_comandos.json"

    resultados_time = []

    for name, fn in funcs.items():
        nome, dados = medir_app_exe_funcao(
            name,
            fn,
            WARMUP_RUNS + USED_RUNS,
            WARMUP_RUNS,
        )
        resultados_time.append({nome: dados})

    merged = {}

    for item in resultados_time:
        for k, v in item.items():
            merged[k] = {
                "statistics": {
                    "time_s": v["time_s"],
                    "cpu_peak": v.get("cpu_peak", {
                        "mean": 0,
                        "min": 0,
                        "max": 0,
                    }),
                    "ram_peak_mb": v.get("ram_peak_mb", {
                        "mean": 0,
                        "min": 0,
                        "max": 0,
                    }),
                    "io": v.get("io", {
                        "read_iops": {
                            "mean": 0,
                            "min": 0,
                            "max": 0,
                        },
                        "write_iops": {
                            "mean": 0,
                            "min": 0,
                            "max": 0,
                        },
                        "read_throughput_bps": {
                            "mean": 0,
                            "min": 0,
                            "max": 0,
                        },
                        "write_throughput_bps": {
                            "mean": 0,
                            "min": 0,
                            "max": 0,
                        },
                    }),
                }
            }

    output = {
        "run_info": {
            "warmup_runs": WARMUP_RUNS,
            "used_runs": USED_RUNS,
        },
        "results": merged,
        "input_files": [
            arquivo.split("\\")[-1].split("/")[-1]
            for arquivo in obter_arquivos_argumentos_teste().split("|")
            if arquivo
        ],
        "system": system,
    }

    output_path = benchmark_app_exe_path()

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), f"Falha ao gerar arquivo: {output_path}"


if __name__ == "__main__":
    teste_benchmark_app_exe()