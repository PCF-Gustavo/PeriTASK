from utilitario.outros import obter_videos

def lista_caminhos_txt(arquivos, pasta_saida):
    from saida.imprimir_lista_caminhos_txt import imprimir_lista_caminhos_txt
    imprimir_lista_caminhos_txt(arquivos, pasta_saida)


def videos_csv_simplificado(arquivos, pasta_saida):
    from saida.imprimir_tabela_simplificada_infos_csv import imprimir_tabela_simplificada_infos_csv
    arquivos_videos = obter_videos(arquivos)
    imprimir_tabela_simplificada_infos_csv(arquivos_videos, pasta_saida)


def videos_csv_completo(arquivos, pasta_saida):
    from saida.imprimir_tabela_completa_infos_csv import imprimir_tabela_completa_infos_csv
    arquivos_videos = obter_videos(arquivos)
    imprimir_tabela_completa_infos_csv(arquivos_videos, pasta_saida)
    
def teste_id(arquivos, pasta_saida):
    pass