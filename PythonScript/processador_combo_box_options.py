import json
from utilitario.caminhos import obter_pasta_raiz

combo_box_options_path = obter_pasta_raiz() / "Compartilhado" / "combo_box_options.json"

def carregar_combo_box_options():
    with open(combo_box_options_path, encoding="utf-8-sig") as f:
        return json.load(f)


def executar_combo_box_option(selecao_id,arquivos,pasta_saida,):

    combo_box_options  = carregar_combo_box_options()

    ids_validos = {item["id"] for item in combo_box_options ["combo_box_options"]}

    if selecao_id not in ids_validos:

        raise ValueError(f"Opção inválida: {selecao_id}")

    try:
        import roteamento
        funcao = getattr(roteamento, selecao_id,)

    except Exception as e:
        raise ImportError(f"Erro ao carregar rota " f"'{selecao_id}': {e}")

    funcao(arquivos, pasta_saida)