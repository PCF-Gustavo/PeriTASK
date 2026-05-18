"""
===========================================================
BENCHMARK: EXECUÇÃO INTERNA (PYTHON PURO)
===========================================================

Este benchmark mede a performance do pipeline executado
diretamente dentro do interpretador Python, chamando a função
main().

✔ O que este teste mede:
- Tempo de execução da lógica do código Python

📌 Interpretação:
Este teste representa o desempenho "ideal" do sistema, isolando
apenas a lógica interna. É útil para análise, otimização de
algoritmos e comparação entre implementações.
"""

import sys
import time
import json
import statistics
from pathlib import Path
from utilitario_pytest import BASE_DIR, ROOT, machine_name, criar_argumento_ui, obter_combo_box_options_ids
sys.path.append(str(ROOT))
from main import main

# ===========================
# CONFIG RUNS
# ===========================
WARMUP_RUNS = 1
USED_RUNS = 9

# ===========================
# INPUTS FIXOS
# ===========================

arquivos = [str(p) for p in (BASE_DIR / "videos").iterdir() if p.is_file()]
arquivos_argumentos = "|".join(arquivos)

assert arquivos, f"Nenhum arquivo encontrado em: {BASE_DIR / 'videos'}"


# ===========================
# ARGUMENTOS GENÉRICOS
# ===========================

def criar_argv_funcao(func_id):
    return [
        "PythonScript.exe",
        arquivos_argumentos,
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
# TEST PIPELINE
# ===========================

def test_pipeline():
    funcs = obter_funcoes_benchmark()

    assert funcs, "Nenhuma função encontrada em combo_box_options.json"

    resultados_time = []

    for name, fn in funcs.items():
        nome, dados = medir_time(
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
            "used_runs": USED_RUNS
        },
        "results": merged
    }

    output_path = BASE_DIR / f"test_benchmark_engine_python_{machine_name}.json"

    with open(
        output_path,
        "w",
        encoding="utf-8-sig"
    ) as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), f"Falha ao gerar arquivo: {output_path}"


if __name__ == "__main__":
    if "--run-once" in sys.argv:
        test_pipeline()