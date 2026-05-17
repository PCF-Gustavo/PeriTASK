print("STATUS:Executando Python...", flush=True)

import sys
import os
from pathlib import Path
from benchmark import modo_benchmark_pytest, emitir_evento_pytest

# utilitario
from utilitario.outros import coletar_arquivos_e_pasta_saida, obter_videos
from processador_combo_box_options import executar_combo_box_option

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
        selecao_ComboBox_id = f"videos_csv_completo"
        # selecao_ComboBox_id = f"videos_csv_simplificado"
        
    # =========================
    # MODO NORMAL
    # =========================
    else:
        itens_selecionados = sys.argv[1].split("|")
        selecao_ComboBox_id = sys.argv[2]
        arquivos, pasta_saida = coletar_arquivos_e_pasta_saida(itens_selecionados)

    # =========================
    # MODO BENCHMARK APP_EXE E ENGINE_PYTHON
    # =========================
    if modo_benchmark_pytest():
        pasta_saida = Path(os.getenv("USERPROFILE")) / "Desktop" / "PeriTASK_pytest"
        pasta_saida.mkdir(parents=True, exist_ok=True)

    # =========================
    # ROTEAMENTO
    # =========================
    executar_combo_box_option(selecao_ComboBox_id, arquivos, pasta_saida)    

if __name__ == "__main__":
    main()
    
