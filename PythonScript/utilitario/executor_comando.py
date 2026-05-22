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
    # validação de Ids + obtenção do label
    # -------------------------
    comandos_por_id = {
        comando["id"]: comando
        for comando in catalogo_de_comandos["comandos"]
    }

    if comando_id not in comandos_por_id:
        raise ValueError(f"Opção inválida: {comando_id}")

    comando_config = comandos_por_id[comando_id]
    label = comando_config.get("label", comando_id)

    # -------------------------
    # status automático
    # -------------------------
    print(f"STATUS:{label}", flush=True)
    
    
    controls_config = (
        comando_config
        .get("ui", {})
        .get("controls", [])
    )
    
    status_screentip = montar_status_screentip_controls(
        controls,
        controls_config,
    )

    if status_screentip:
        print(
            f"STATUS_SCREENTIP:{status_screentip}",
            flush=True,
        )

    # -------------------------
    # routing dinâmico
    # -------------------------
    emitir_evento_pytest(f"ROTA:{comando_id}")
    executar_comando(arquivos, comando_id, controls, pasta_saida)
    
def formatar_valor_control_para_screentip(valor):
    if isinstance(valor, bool):
        return "true" if valor else "false"

    if valor is None:
        return ""

    return str(valor)


def formatar_label_control_para_screentip(control):
    label = control.get("text") or control.get("id") or ""

    label = str(label).strip()

    # Remove ":" final para evitar:
    # Escolha:='tabela simplificada'
    if label.endswith(":"):
        label = label[:-1].strip()

    return label


def montar_status_screentip_controls(controls, controls_config):
    if not controls:
        return ""

    controles_por_id = {
        control.get("id"): control
        for control in controls_config
        if control.get("id")
    }

    partes = []

    # Primeiro segue a ordem definida no JSON
    for control in controls_config:
        control_id = control.get("id")

        if not control_id:
            continue

        if control_id not in controls:
            continue

        label = formatar_label_control_para_screentip(control)
        valor = formatar_valor_control_para_screentip(
            controls.get(control_id)
        )

        partes.append(f"{label} = {valor}")

    # Depois inclui controles extras que eventualmente vierem no payload
    for control_id, valor_bruto in controls.items():
        if control_id in controles_por_id:
            continue

        valor = formatar_valor_control_para_screentip(valor_bruto)
        partes.append(f"{control_id} = {valor}")

    return "\\n".join(partes)


def montar_status_curto(comando_id):
    return f"Executando {comando_id}"