"""
===========================================================
BENCHMARK: TEMPO DE INICIALIZAÇÃO DO EXE (STARTUP)
===========================================================
Mede exclusivamente o tempo de inicialização do PythonScript.exe,
do início do processo até o evento BENCHMARK:PERITASK_READY.
"""

import json
import time
import statistics
import subprocess

from utilitario_pytest import (
    WARMUP_RUNS,
    USED_RUNS,
    EXE_PATH,
    benchmark_inicializacao_path,
    exigir_pythonscript_exe,
)

# ===========================
# BENCHMARK (INICIALIZAÇÃO)
# ===========================

def medir_startup():
    psi = subprocess.Popen(
        [str(EXE_PATH), "--benchmark"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    start = time.perf_counter()

    for line in psi.stdout:
        if "PERITASK_READY" in line:
            end = time.perf_counter()
            psi.kill()
            psi.wait()
            return end - start

    psi.kill()
    psi.wait()
    raise RuntimeError("PERITASK_READY não encontrado")


def teste_benchmark_inicializacao():
    exigir_pythonscript_exe()

    results = []

    for _ in range(WARMUP_RUNS + USED_RUNS):
        t = medir_startup()
        results.append(t)

    valid = results[WARMUP_RUNS:]
    assert len(valid) > 0, "Nenhuma medição válida"

    mean = round(statistics.mean(valid), 4)
    min_v = round(min(valid), 4)
    max_v = round(max(valid), 4)

    print(f"\nTempo médio: {mean}s")

    output = {
        "run_info": {
            "warmup_runs": WARMUP_RUNS,
            "used_runs": USED_RUNS,
        },
        "results": {
            "statistics": {
                "time_s": {
                    "mean": mean,
                    "min": min_v,
                    "max": max_v,
                }
            }
        }
    }

    output_path = benchmark_inicializacao_path()

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), f"Falha ao gerar arquivo: {output_path}"
