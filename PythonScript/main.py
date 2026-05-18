print("STATUS:Executando Python...", flush=True)

import sys
import os
import json
import base64
from pathlib import Path
from benchmark import modo_benchmark_pytest, emitir_evento_pytest

# utilitario
from utilitario.outros import coletar_arquivos_e_pasta_saida, obter_videos
from processador_argumento_ui import executar_argumento_ui

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
        argumento_ui = base64.b64encode(json.dumps({"combo_box_options_id": "videos_csv_completo"}).encode("utf-8")).decode("utf-8")
        
    # =========================
    # MODO NORMAL
    # =========================
    else:
        itens_selecionados = sys.argv[1].split("|")
        argumento_ui = sys.argv[2]
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
    executar_argumento_ui(argumento_ui, arquivos, pasta_saida)

if __name__ == "__main__":
    main()
    
