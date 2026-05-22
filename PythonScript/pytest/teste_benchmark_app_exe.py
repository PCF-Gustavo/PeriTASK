"""
===========================================================
BENCHMARK: EXECUÇÃO REAL DO EXE (END-TO-END)
===========================================================
Mede a execução completa a partir do PythonScript.exe, incluindo
startup, criação de processo, carregamento de bibliotecas e uso
de CPU/RAM/IO.
"""

import sys
import json
from pathlib import Path

from utilitario_pytest import (
    WARMUP_RUNS,
    USED_RUNS,
    benchmark_app_exe_path,
    collect_static_system_info,
    criar_args_pythonscript_exe,
    exigir_pythonscript_exe,
    medir_cpu_ram_io,
    medir_time_subprocess,
    obter_arquivos_recursos_teste,
    obter_catalogo_de_comandos_ids,
)

# ===========================
# ARGUMENTOS GENÉRICOS
# ===========================

def criar_args_funcao(func_id):
    return criar_args_pythonscript_exe(func_id)


def obter_funcoes_benchmark():
    return {
        func_id: (lambda fid=func_id: criar_args_funcao(fid))
        for func_id in obter_catalogo_de_comandos_ids()
    }


def teste_benchmark_app_exe():
    exigir_pythonscript_exe()

    system = collect_static_system_info()
    funcs = obter_funcoes_benchmark()

    assert funcs, "Nenhuma função encontrada em catalogo_de_comandos.json"

    resultados_time = []
    resultados_cpu = []

    # FASE 1: TIME
    for name, fn in funcs.items():
        nome, dados = medir_time_subprocess(
            name,
            fn,
            WARMUP_RUNS + USED_RUNS,
            WARMUP_RUNS,
            timeout=300,
        )
        resultados_time.append({nome: dados})

    # FASE 2: CPU / RAM / IO
    for name, fn in funcs.items():
        nome, dados = medir_cpu_ram_io(
            name,
            fn,
            WARMUP_RUNS + USED_RUNS,
            WARMUP_RUNS,
        )
        resultados_cpu.append({nome: dados})

    merged = {}

    for item in resultados_time:
        for k, v in item.items():
            merged[k] = {
                "statistics": {
                    "time_s": v["time_s"],
                }
            }

    for item in resultados_cpu:
        for k, v in item.items():
            merged[k]["statistics"]["cpu_peak"] = v["cpu_peak"]
            merged[k]["statistics"]["ram_peak_mb"] = v["ram_peak_mb"]
            merged[k]["statistics"]["io"] = v["io"]

    arquivos = obter_arquivos_recursos_teste()

    output = {
        "run_info": {
            "warmup_runs": WARMUP_RUNS,
            "used_runs": USED_RUNS,
        },
        "results": merged,
        "input_files": [Path(v).name for v in arquivos],
        "system": system,
    }
    output_path = benchmark_app_exe_path()

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), f"Falha ao gerar arquivo: {output_path}"


if __name__ == "__main__":
    if "--run-once" in sys.argv:
        teste_benchmark_app_exe()
