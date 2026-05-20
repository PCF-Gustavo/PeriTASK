"""
===========================================================
TESTE DE COMUNICAÇÃO UI -> PYTHONSCRIPT
===========================================================
Executa UserInterface.exe em modo CLI/benchmark, sem abrir janela,
e valida que a UI consegue chamar o PythonScript e entrar na rota correta.
"""

from utilitario_pytest import (
    criar_args_ui_benchmark,
    criar_arquivo_txt_temporario_para_ui,
    executar_subprocess,
    obter_catalogo_de_comandos_ids,
)


def test_comunicacao_UI_PythonScript():
    rotas = obter_catalogo_de_comandos_ids()
    assert rotas, "Nenhuma rota encontrada no catalogo_de_comandos.json"

    arquivo_teste = criar_arquivo_txt_temporario_para_ui()

    falhas = []

    for rota in rotas:
        result = executar_subprocess(
            criar_args_ui_benchmark(rota, arquivo_teste),
            timeout=60,
        )

        saida = (result.stdout or "") + "\n" + (result.stderr or "")

        marcador_ready = "BENCHMARK:PERITASK_READY"
        marcador_rota = f"BENCHMARK:ROTA:{rota}"

        if result.returncode != 0:
            falhas.append(
                f"Rota '{rota}' retornou código {result.returncode}\n\n{saida}"
            )
            continue

        if marcador_ready not in saida:
            falhas.append(
                f"Rota '{rota}' não emitiu marcador de inicialização: "
                f"{marcador_ready}\n\n{saida}"
            )

        if marcador_rota not in saida:
            falhas.append(
                f"Rota '{rota}' não emitiu marcador esperado: "
                f"{marcador_rota}\n\n{saida}"
            )

    assert not falhas, "\n\n" + "\n\n".join(falhas)
