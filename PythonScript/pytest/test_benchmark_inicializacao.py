"""
===========================================================
BENCHMARK: TEMPO DE INICIALIZAÇÃO DO EXE (STARTUP)
===========================================================

Este benchmark mede exclusivamente o tempo de inicialização
do executável (PythonScript.exe), desde o início do processo
até o momento em que a aplicação sinaliza que está pronta
para executar tarefas (evento "PERITASK_READY").

✔ O que este teste mede:
- Tempo de criação do processo (subprocess)
- Inicialização do runtime Python/Nuitka
- Importação de módulos (lazy ou não)
- Setup inicial da aplicação
- Overhead de startup do executável

📌 Interpretação:
Este teste isola o custo de inicialização da aplicação,
permitindo identificar gargalos de startup e impactos de:
- Lazy imports
- Bibliotecas pesadas
- Estratégias de empacotamento
"""

import sys
import json
import statistics
import subprocess
import time
from utilitario_pytest import BASE_DIR, ROOT, EXE_PATH, machine_name

sys.path.append(str(ROOT))


# ===========================
# CONFIG RUNS
# ===========================
WARMUP_RUNS = 1
USED_RUNS = 9


# ===========================
# BENCHMARK (INICIALIZACAO)
# ===========================

def medir_startup():
    psi = subprocess.Popen(
        [str(EXE_PATH), "--benchmark"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
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


# ===========================
# TEST
# ===========================

def test_startup_benchmark():
    assert EXE_PATH.exists(), f"Exe não encontrado: {EXE_PATH}"

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
            "used_runs": USED_RUNS
        },
        "results": {
            "statistics": {
                "time_s": {
                    "mean": mean,
                    "min": min_v,
                    "max": max_v
                }
            }
        }
    }


    with open(
        BASE_DIR / f"test_benchmark_inicializacao_{machine_name}.json",
        "w",
        encoding="utf-8-sig"
    ) as f:
        json.dump(output, f, indent=4)

if __name__ == "__main__":
    if "--run-once" in sys.argv:
        test_startup_benchmark()