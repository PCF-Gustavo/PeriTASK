"""
===========================================================
BENCHMARK: OVERHEAD DO CONTRATO UI -> PYTHONSCRIPT
===========================================================
Mede somente o overhead médio da comunicação UI -> PythonScript,
sem salvar detalhes por rota, runs individuais ou estatísticas extras.
"""

import json
import statistics
import time

from utilitario_pytest import (
    BASE_DIR,
    machine_name,
    criar_args_ui_benchmark,
    criar_arquivo_txt_temporario_para_ui,
    executar_subprocess,
    obter_catalogo_de_comandos_ids,
)


# ===========================
# CONFIG RUNS
# ===========================
WARMUP_RUNS = 1
USED_RUNS = 9


# ===========================
# HELPERS
# ===========================
def medir_rota_comunicacao(rota, arquivo_teste):
    inicio = time.perf_counter()

    result = executar_subprocess(
        criar_args_ui_benchmark(rota, arquivo_teste),
        timeout=60,
    )

    fim = time.perf_counter()
    tempo_s = fim - inicio

    saida = (result.stdout or "") + "\n" + (result.stderr or "")

    marcador_ready = "BENCHMARK:PERITASK_READY"
    marcador_rota = f"BENCHMARK:ROTA:{rota}"

    assert result.returncode == 0, (
        f"Rota '{rota}' retornou código {result.returncode}\n\n{saida}"
    )

    assert marcador_ready in saida, (
        f"Rota '{rota}' não emitiu marcador de inicialização: "
        f"{marcador_ready}\n\n{saida}"
    )

    assert marcador_rota in saida, (
        f"Rota '{rota}' não emitiu marcador esperado: "
        f"{marcador_rota}\n\n{saida}"
    )

    return tempo_s


def medir_overhead_medio_rota(rota, arquivo_teste):
    tempos = []

    for _ in range(WARMUP_RUNS + USED_RUNS):
        tempos.append(medir_rota_comunicacao(rota, arquivo_teste))

    tempos_validos = tempos[WARMUP_RUNS:]
    return statistics.mean(tempos_validos)


# ===========================
# BENCHMARK
# ===========================
def test_benchmark_comunicacao_UI_PythonScript():
    rotas = obter_catalogo_de_comandos_ids()
    assert rotas, "Nenhuma rota encontrada no catalogo_de_comandos.json"

    arquivo_teste = criar_arquivo_txt_temporario_para_ui()

    overheads_por_rota = []

    for rota in rotas:
        overhead_rota = medir_overhead_medio_rota(rota, arquivo_teste)
        overheads_por_rota.append(overhead_rota)

    overhead_comunicacao_s = round(statistics.mean(overheads_por_rota), 4)

    output = {
        "overhead_comunicacao_ui_pythonscript_s": overhead_comunicacao_s
    }

    output_path = BASE_DIR / f"test_benchmark_comunicacao_UI_PythonScript_{machine_name}.json"

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), f"Falha ao gerar benchmark: {output_path}"


if __name__ == "__main__":
    test_benchmark_comunicacao_UI_PythonScript()