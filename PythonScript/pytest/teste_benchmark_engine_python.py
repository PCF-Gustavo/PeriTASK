"""
===========================================================
BENCHMARK: EXECUÇÃO INTERNA (PYTHON PURO)
===========================================================
Mede a performance do pipeline executado diretamente dentro
do interpretador Python, chamando a função main().
"""

import sys
import json

from utilitario_pytest import (
    WARMUP_RUNS,
    USED_RUNS,
    ROOT,
    benchmark_engine_python_path,
    criar_argumento_ui,
    medir_time_funcao,
    obter_arquivos_argumentos_teste,
    obter_cenarios_benchmark,
)

sys.path.append(str(ROOT))
from main import main

# ===========================
# ARGUMENTOS GENÉRICOS
# ===========================

def criar_argv_funcao(func_id, controls):
    return [
        "PythonScript.exe",
        obter_arquivos_argumentos_teste(),
        criar_argumento_ui(func_id, controls),
        "--benchmark",
    ]


def executar_main_com_argv(argv):
    argv_original = sys.argv[:]

    try:
        sys.argv = argv
        main()
    finally:
        sys.argv = argv_original


def obter_funcoes_benchmark():
    funcs = {}

    for cenario in obter_cenarios_benchmark():
        benchmark_id = cenario["benchmark_id"]
        comando_id = cenario["comando_id"]
        controls = cenario["controls"]

        funcs[benchmark_id] = (
            lambda cid=comando_id, ctrls=controls:
            executar_main_com_argv(criar_argv_funcao(cid, ctrls))
        )

    return funcs


def teste_benchmark_engine_python():
    funcs = obter_funcoes_benchmark()
    assert funcs, "Nenhuma função encontrada em catalogo_de_comandos.json"

    resultados_time = []

    for name, fn in funcs.items():
        nome, dados = medir_time_funcao(
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
                    "time_s": v["time_s"]
                }
            }

    output = {
        "run_info": {
            "warmup_runs": WARMUP_RUNS,
            "used_runs": USED_RUNS,
        },
        "results": merged,
    }

    output_path = benchmark_engine_python_path()

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), f"Falha ao gerar arquivo: {output_path}"


if __name__ == "__main__":
    if "--run-once" in sys.argv:
        teste_benchmark_engine_python()