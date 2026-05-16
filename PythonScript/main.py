print("STATUS:Executando Python...", flush=True)

import sys
import os
from pathlib import Path
from benchmark import modo_benchmark_pytest, emitir_evento_pytest

# utilitario
from utilitario.outros import coletar_arquivos_e_pasta_saida, obter_videos

def main():
    # =========================
    # MODO BENCHMARK INICIALIZAÇÃO
    # =========================
    emitir_evento_pytest("PERITASK_READY")
    
    # =========================
    # MODO DEBUG (usando depurador da UI do Visual Studio)
    # =========================
    if len(sys.argv) < 3:
        pasta_saida = r"C:\Users\gustavo.gvs\Desktop\teste_PeriTASK"
        arquivos = obter_videos(list(Path(r"C:\Users\gustavo.gvs\Desktop\teste_PeriTASK").iterdir()))
        selecao_ComboBox = f"Vídeos -> tabela completa de informações em .csv"
        # selecao_ComboBox = f"Vídeos -> tabela simplificada de informações em .csv"
        
    # =========================
    # MODO NORMAL
    # =========================
    else:
        itens_selecionados = sys.argv[1].split("|")
        selecao_ComboBox = sys.argv[2]
        arquivos, pasta_saida = coletar_arquivos_e_pasta_saida(itens_selecionados)

    # =========================
    # MODO BENCHMARK APLICACAO COMPLETA
    # =========================
    if modo_benchmark_pytest():
        pasta_saida = Path(os.getenv("USERPROFILE")) / "Desktop" / "PeriTASK_pytest"
        pasta_saida.mkdir(parents=True, exist_ok=True)

    # =========================
    # ROTEAMENTO
    # =========================
    if selecao_ComboBox == f"Arquivos -> lista de caminhos em .txt":
        from saida.imprimir_lista_caminhos_txt import imprimir_lista_caminhos_txt
        imprimir_lista_caminhos_txt(arquivos, pasta_saida)
    elif selecao_ComboBox == f"Vídeos -> tabela simplificada de informações em .csv":
        from saida.imprimir_tabela_simplificada_infos_csv import imprimir_tabela_simplificada_infos_csv
        arquivos_videos = obter_videos(arquivos)
        imprimir_tabela_simplificada_infos_csv(arquivos_videos, pasta_saida)
    elif selecao_ComboBox == f"Vídeos -> tabela completa de informações em .csv":
        from saida.imprimir_tabela_completa_infos_csv import imprimir_tabela_completa_infos_csv
        arquivos_videos = obter_videos(arquivos)
        imprimir_tabela_completa_infos_csv(arquivos_videos, pasta_saida)


if __name__ == "__main__":
    main()
    
