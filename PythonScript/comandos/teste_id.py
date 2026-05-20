def pausar_para_usuario(mensagem):
    print(f"PAUSE:{mensagem}", flush=True)
    input()


def executar(arquivos, ui_state, pasta_saida):
    if ui_state.get("checkbox_teste_alerta1"):
        pausar_para_usuario(
            f"Checkbox marcado1. editbox: {ui_state.get('editbox_quantidade')}"
        )

    if ui_state.get("checkbox_teste_alerta2"):
        pausar_para_usuario("Checkbox marcado2")