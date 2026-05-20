import json
from utilitario.caminhos import obter_pasta_raiz
from benchmark import emitir_evento_pytest
import base64
import binascii
from comandos import executar_comando

combo_box_options_path = obter_pasta_raiz() / "Compartilhado" / "combo_box_options.json"

def carregar_combo_box_options():
    with open(combo_box_options_path, encoding="utf-8-sig") as f:
        return json.load(f)


def executar_argumento_ui(argumento_ui, arquivos, pasta_saida):

    # -------------------------
    # parse do JSON
    # -------------------------
    try:
        decoded = base64.b64decode(argumento_ui).decode("utf-8")
        ui_payload = json.loads(decoded)

    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("UI payload inválido (Base64 ou JSON corrompido)")

    combo_box_options = carregar_combo_box_options()

    # -------------------------
    # extrai dados
    # -------------------------
    selecao_id = ui_payload.get("combo_box_options_id")
    ui_state = ui_payload.get("controls", {})

    # -------------------------
    # validação do comboBoxId
    # -------------------------
    ids_validos = {item["id"] for item in combo_box_options["combo_box_options"]}

    if selecao_id not in ids_validos:
        raise ValueError(f"Opção inválida: {selecao_id}")

    # -------------------------
    # routing dinâmico
    # -------------------------
    emitir_evento_pytest(f"ROTA:{selecao_id}")

    executar_comando(selecao_id, arquivos, ui_state, pasta_saida)