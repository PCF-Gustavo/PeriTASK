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


def processar_payload(arquivos, payload_base64_from_ui, pasta_saida):

    # -------------------------
    # parse do JSON
    # -------------------------
    try:
        decoded = base64.b64decode(payload_base64_from_ui).decode("utf-8")
        payload_from_ui = json.loads(decoded)

    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("UI payload inválido (Base64 ou JSON corrompido)")

    catalogo_de_comandos = carregar_catalogo_de_comandos()

    # -------------------------
    # extrai dados
    # -------------------------
    comando_id = payload_from_ui.get("comando_id")
    controls = payload_from_ui.get("controls", {})

    # -------------------------
    # validação de Ids
    # -------------------------
    ids_validos = {comando["id"] for comando in catalogo_de_comandos["comandos"]}

    if comando_id not in ids_validos:
        raise ValueError(f"Opção inválida: {comando_id}")

    # -------------------------
    # routing dinâmico
    # -------------------------
    emitir_evento_pytest(f"ROTA:{comando_id}")

    executar_comando(arquivos, comando_id, controls, pasta_saida)