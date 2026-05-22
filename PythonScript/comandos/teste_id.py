def pausar_para_usuario(mensagem):
    print(f"PAUSE:{mensagem}", flush=True)
    input()


def executar(arquivos, controls, pasta_saida):
    checkbox_teste_alerta1 = controls.get("checkbox_teste_alerta1")
    editbox_quantidade = controls.get("editbox_quantidade")
    dropdown_id = controls.get("dropdown_id")
    

    if checkbox_teste_alerta1:
        pausar_para_usuario(
            f"Checkbox marcado1. editbox: {editbox_quantidade} dropdown: {dropdown_id}"
        )
