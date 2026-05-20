from utilitario.outros import obter_videos

def pausar_para_usuario(mensagem):
    print(f"PAUSE:{mensagem}", flush=True)
    input()

def lista_caminhos_txt(arquivos, _, pasta_saida):
    from saida.imprimir_lista_caminhos_txt import imprimir_lista_caminhos_txt
    imprimir_lista_caminhos_txt(arquivos, pasta_saida)


def videos_csv_simplificado(arquivos, _, pasta_saida):
    from saida.imprimir_tabela_simplificada_infos_csv import imprimir_tabela_simplificada_infos_csv
    arquivos_videos = obter_videos(arquivos)
    imprimir_tabela_simplificada_infos_csv(arquivos_videos, pasta_saida)


def videos_csv_completo(arquivos, _, pasta_saida):
    from saida.imprimir_tabela_completa_infos_csv import imprimir_tabela_completa_infos_csv
    arquivos_videos = obter_videos(arquivos)
    imprimir_tabela_completa_infos_csv(arquivos_videos, pasta_saida)
    
def teste_id(arquivos, ui_state, pasta_saida):
    if ui_state.get("checkbox_teste_alerta1"):
        pausar_para_usuario("Checkbox marcado1")
    if ui_state.get("checkbox_teste_alerta2"):
        pausar_para_usuario("Checkbox marcado2")