"""
===========================================================
BENCHMARK: CONTRATO PURO PYTHON
===========================================================
Mede apenas o overhead interno do contrato UI -> PythonScript,
sem executar UserInterface.exe, sem abrir janela e sem processar mídia.
"""

import base64
import json
import statistics
import sys
import time
import pytest

from utilitario_pytest import (
    WARMUP_RUNS,
    USED_RUNS,
    BASE_DIR,
    ROOT,
    obter_catalogo_de_comandos_ids,
    benchmark_overhead_contrato_path
)

sys.path.append(str(ROOT))

from utilitario.executor_comando import processar_payload
import comandos

# ===========================
# HELPERS
# ===========================
def criar_argumento_ui_base64(comando_id, controls=None):
    payload = {
        "comando_id": comando_id,
        "controls": controls or {},
    }

    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return base64.b64encode(
        payload_json.encode("utf-8")
    ).decode("ascii")


def comando_noop(arquivos, ui_state, pasta_saida):
    return None


def medir_overhead_medio(func, rodadas, ignorar):
    tempos = []

    for _ in range(rodadas):
        inicio = time.perf_counter()
        func()
        fim = time.perf_counter()

        tempos.append(fim - inicio)

    tempos_validos = tempos[ignorar:]

    return statistics.mean(tempos_validos)


def teste_benchmark_overhead_contrato(monkeypatch):
    comandos_ids = obter_catalogo_de_comandos_ids()

    assert comandos_ids, "Nenhum comando encontrado no catalogo_de_comandos.json"

    pasta_saida = BASE_DIR
    arquivos = []

    # Substitui a resolução dinâmica real por uma função noop.
    # Assim o benchmark mede apenas:
    # Base64 -> JSON -> validação do ID -> chamada do executor.
    monkeypatch.setattr(
        comandos,
        "obter_funcao_comando",
        lambda comando_id: comando_noop,
    )

    overheads_por_comando = []

    for comando_id in comandos_ids:
        argumento_ui = criar_argumento_ui_base64(comando_id)

        overhead_comando = medir_overhead_medio(
            lambda arg=argumento_ui: processar_payload(
                arquivos,
                arg,
                pasta_saida,
            ),
            WARMUP_RUNS + USED_RUNS,
            WARMUP_RUNS,
        )

        overheads_por_comando.append(overhead_comando)

    overhead_contrato_s = round(
        statistics.mean(overheads_por_comando),
        6,
    )

    output = {
        "overhead_contrato_s": overhead_contrato_s
    }

    output_path = benchmark_overhead_contrato_path()

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), f"Falha ao gerar benchmark: {output_path}"


if __name__ == "__main__":
    pytest.main([__file__])
