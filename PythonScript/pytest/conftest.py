"""
Configuração global dos testes pytest do PeriTASK.

Objetivos:
1. Ordenar a execução quando todos os testes forem rodados pelo Test Explorer/pytest.
2. Impedir benchmarks se a etapa básica falhar.

Etapa básica:
- test_app_exe.py
- test_comunicacao_UI_PythonScript.py

Etapa benchmark:
- test_benchmark_inicializacao.py
- test_benchmark_engine_python.py
- test_benchmark_app_exe.py
- gerar_relatorio.py
"""

import pytest


PRE_TEST_FILES = {
    "test_app_exe.py",
    "test_comunicacao_UI_PythonScript.py",
}

BENCHMARK_FILES = {
    "test_benchmark_inicializacao.py",
    "test_benchmark_engine_python.py",
    "test_benchmark_app_exe.py",
    "gerar_relatorio.py",
}

_pre_status = {}


def pytest_sessionstart(session):
    """
    Inicializa o estado dos pré-testes no começo da sessão.
    """
    global _pre_status

    _pre_status = {
        file_name: {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for file_name in PRE_TEST_FILES
    }


def pytest_collection_modifyitems(session, config, items):
    """
    Ordem lógica para execução completa:
    1. Teste do exe final
    2. Teste de comunicação UI -> PythonScript
    3. Benchmarks
    4. Relatório final
    """

    prioridade_por_arquivo = {
        "test_app_exe.py": 10,
        "test_comunicacao_UI_PythonScript.py": 20,

        "test_benchmark_inicializacao.py": 100,
        "test_benchmark_engine_python.py": 110,
        "test_benchmark_app_exe.py": 120,

        "gerar_relatorio.py": 200,
    }

    def prioridade(item):
        return prioridade_por_arquivo.get(item.path.name, 999)

    items.sort(key=prioridade)


def pytest_runtest_logreport(report):
    """
    Registra resultado dos testes básicos.

    Observação:
    TestReport não tem report.config.
    Por isso usamos a variável global _pre_status.
    """
    global _pre_status

    file_name = report.location[0].replace("\\", "/").split("/")[-1]

    if file_name not in PRE_TEST_FILES:
        return

    status = _pre_status[file_name]

    if report.failed:
        status["failed"] += 1
        return

    if report.skipped:
        status["skipped"] += 1
        return

    if report.when == "call" and report.passed:
        status["passed"] += 1


def _pre_tests_ok():
    """
    Retorna True somente se cada arquivo de pré-teste teve ao menos
    um teste aprovado e nenhum teste falhou.
    """
    for file_name in PRE_TEST_FILES:
        file_status = _pre_status.get(file_name)

        if not file_status:
            return False

        if file_status["failed"] > 0:
            return False

        if file_status["passed"] == 0:
            return False

    return True


def pytest_runtest_setup(item):
    """
    Benchmarks só rodam se os dois testes básicos tiverem passado
    na mesma sessão pytest.
    """
    file_name = item.path.name

    if file_name not in BENCHMARK_FILES:
        return

    if not _pre_tests_ok():
        pytest.skip(
            "Benchmark ignorado: test_app_exe.py e "
            "test_comunicacao_UI_PythonScript.py precisam concluir com êxito primeiro."
        )