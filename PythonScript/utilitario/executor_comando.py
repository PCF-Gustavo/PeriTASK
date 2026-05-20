import json
from utilitario.caminhos import obter_pasta_raiz
from utilitario.benchmark import emitir_evento_pytest
import base64
import binascii
from comandos import executar_comando

catalogo_de_comandos_path = obter_pasta_raiz() / "Compartilhado" / "catalogo_de_comandos.json"

def carregar_catalogo_de_comandos():
    with open(catalogo_de_comandos_path, encoding="utf-8-sig") as f:
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

    catalogo_de_comandos = carregar_catalogo_de_comandos()

    # -------------------------
    # extrai dados
    # -------------------------
    selecao_id = ui_payload.get("comando_id")
    ui_state = ui_payload.get("controls", {})

    # -------------------------
    # validação de Ids
    # -------------------------
    ids_validos = {comando["id"] for comando in catalogo_de_comandos["comandos"]}

    if selecao_id not in ids_validos:
        raise ValueError(f"Opção inválida: {selecao_id}")

    # -------------------------
    # routing dinâmico
    # -------------------------
    emitir_evento_pytest(f"ROTA:{selecao_id}")

    executar_comando(selecao_id, arquivos, ui_state, pasta_saida)