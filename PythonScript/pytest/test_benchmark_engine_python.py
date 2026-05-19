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
    ROOT,
    benchmark_engine_python_path,
    criar_argumento_ui,
    medir_time_funcao,
    obter_arquivos_argumentos_teste,
    obter_combo_box_options_ids,
)

sys.path.append(str(ROOT))
from main import main


# ===========================
# CONFIG RUNS
# ===========================

WARMUP_RUNS = 1
USED_RUNS = 9


# ===========================
# ARGUMENTOS GENÉRICOS
# ===========================

def criar_argv_funcao(func_id):
    return [
        "PythonScript.exe",
        obter_arquivos_argumentos_teste(),
        criar_argumento_ui(func_id),
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
    return {
        func_id: (lambda fid=func_id: executar_main_com_argv(criar_argv_funcao(fid)))
        for func_id in obter_combo_box_options_ids()
    }


# ===========================
# TEST PIPELINE
# ===========================

def test_pipeline():
    funcs = obter_funcoes_benchmark()
    assert funcs, "Nenhuma função encontrada em combo_box_options.json"

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
        test_pipeline()
