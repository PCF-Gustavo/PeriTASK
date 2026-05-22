def pausar_para_usuario(mensagem):
    print(f"PAUSE:{mensagem}", flush=True)
    input()


def executar(arquivos, controls, pasta_saida):
    if controls.get("checkbox_teste_alerta1"):
        pausar_para_usuario(
            f"Checkbox marcado1. editbox: {controls.get('editbox_quantidade')} dropdown: {controls.get('dropdown_id')}"
        )
