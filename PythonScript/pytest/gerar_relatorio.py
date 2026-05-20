import json

from utilitario_pytest import (
    benchmark_overhead_contrato_path,
    benchmark_comunicacao_UI_PythonScript_path,
    benchmark_app_exe_path,
    benchmark_engine_python_path,
    benchmark_inicializacao_path,
    
    benchmark_report_path,
)


def test_generate_benchmark_report():
    paths = {
        "test_benchmark_overhead_contrato": benchmark_overhead_contrato_path(),
        "test_benchmark_comunicacao_UI_PythonScript": benchmark_comunicacao_UI_PythonScript_path(),
        "test_benchmark_inicializacao": benchmark_inicializacao_path(),
        "test_benchmark_engine_python": benchmark_engine_python_path(),
        "test_benchmark_app_exe": benchmark_app_exe_path(),
        
    }

    for nome, path in paths.items():
        assert path.exists(), f"Arquivo não encontrado para {nome}: {path}"
        
    with open(paths["test_benchmark_overhead_contrato"], encoding="utf-8-sig") as f:
        overhead_contrato_json = json.load(f)
        
    with open(paths["test_benchmark_comunicacao_UI_PythonScript"], encoding="utf-8-sig") as f:
        comunicacao_UI_PythonScript_json = json.load(f)

    with open(paths["test_benchmark_inicializacao"], encoding="utf-8-sig") as f:
        inicializacao_json = json.load(f)

    with open(paths["test_benchmark_engine_python"], encoding="utf-8-sig") as f:
        aplicacao_completa_python = json.load(f)

    with open(paths["test_benchmark_app_exe"], encoding="utf-8-sig") as f:
        aplicacao_completa_exe = json.load(f)
        



    combined = {
        "test_benchmark_overhead_contrato": overhead_contrato_json,
        "test_benchmark_comunicacao_UI_PythonScript": comunicacao_UI_PythonScript_json,
        "test_benchmark_inicializacao": inicializacao_json,
        "test_benchmark_engine_python": aplicacao_completa_python,
        "test_benchmark_app_exe": aplicacao_completa_exe,
    }

    output_path = benchmark_report_path()

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(combined, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), "Falha ao gerar report combinado."

    
    # =========================
    # LIMPEZA DOS JSONS INTERMEDIÁRIOS
    # =========================
    for path in paths.values():
        path.unlink(missing_ok=True)

    # Garante que o report final permaneceu
    assert output_path.exists(), "Report final foi removido indevidamente."
