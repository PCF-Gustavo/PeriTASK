import json
from utilitario_pytest import BASE_DIR, machine_name


def test_generate_benchmark_report():

    test_benchmark_inicializacao_path = (
        BASE_DIR / f"test_benchmark_inicializacao_{machine_name}.json"
    )

    test_benchmark_aplicacao_completa_path = (
        BASE_DIR / f"test_benchmark_aplicacao_completa_{machine_name}.json"
    )

    output_path = (
        BASE_DIR / f"BenchmarkReport_{machine_name}.json"
    )

    # =========================
    # VALIDAÇÕES
    # =========================

    assert test_benchmark_inicializacao_path.exists(), (
        f"Arquivo não encontrado: {test_benchmark_inicializacao_path}"
    )

    assert test_benchmark_aplicacao_completa_path.exists(), (
        f"Arquivo não encontrado: {test_benchmark_aplicacao_completa_path}"
    )

    # =========================
    # LEITURA JSON
    # =========================

    with open(test_benchmark_inicializacao_path, encoding="utf-8-sig") as f:
        inicializacao_json = json.load(f)

    with open(test_benchmark_aplicacao_completa_path, encoding="utf-8-sig") as f:
        aplicacao_json = json.load(f)

    # =========================
    # MERGE FINAL
    # =========================

    combined = {
        "test_benchmark_inicializacao": inicializacao_json,
        "test_benchmark_aplicacao_completa": aplicacao_json,
    }

    # =========================
    # OUTPUT
    # =========================

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(combined, f, indent=4)

    # =========================
    # CHECK FINAL
    # =========================

    assert output_path.exists(), "Falha ao gerar report combinado."