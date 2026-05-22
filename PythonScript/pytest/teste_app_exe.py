"""
===========================================================
TESTE DE EXECUÇÃO REAL DO EXE
===========================================================
Valida se as principais funcionalidades executam corretamente
a partir do executável final PythonScript.exe.
"""

import pytest

from utilitario_pytest import (
    PASTA_SAIDA_PYTEST,
    criar_args_pythonscript_exe,
    executar_subprocess,
    exigir_pythonscript_exe,
    limpar_pasta_saida_pytest,
    obter_catalogo_de_comandos_ids,
    validar_saidas_genericas,
)


@pytest.mark.parametrize("func_id", obter_catalogo_de_comandos_ids())
def teste_app_exe(func_id):
    exigir_pythonscript_exe()
    limpar_pasta_saida_pytest()

    result = executar_subprocess(
        criar_args_pythonscript_exe(func_id),
        timeout=300,
        imprimir_saida=True,
    )

    assert result.returncode == 0, (
        f"Execução falhou com código {result.returncode}\n\n"
        f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    )

    validar_saidas_genericas(PASTA_SAIDA_PYTEST)
