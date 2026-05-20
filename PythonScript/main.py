print("STATUS:Executando Python...", flush=True)
import sys
from utilitario.benchmark import modo_benchmark_pytest, emitir_evento_pytest

def main():
    # =========================
    # MODO BENCHMARK INICIALIZAÇÃO
    # =========================
    emitir_evento_pytest("PERITASK_READY")
    
    # =========================
    # MODO DEBUG (usando depurador da UI do Visual Studio)
    # =========================
    if len(sys.argv) < 3:
        from pathlib import Path
        import json, base64
        pasta_saida = r"C:\Users\gustavo.gvs\Desktop\teste_PeriTASK"
        arquivos = list(Path(r"C:\Users\gustavo.gvs\Desktop\teste_PeriTASK").iterdir())
        payload_base64_from_ui = base64.b64encode(json.dumps({"comando_id": "videos_csv_completo"}).encode("utf-8")).decode("utf-8")
        
    # =========================
    # MODO NORMAL
    # =========================
    else:
        from utilitario.outros import coletar_arquivos_e_pasta_saida
        itens_selecionados = sys.argv[1].split("|")
        payload_base64_from_ui = sys.argv[2]
        arquivos, pasta_saida = coletar_arquivos_e_pasta_saida(itens_selecionados)

    # =========================
    # MODO BENCHMARK APP_EXE E ENGINE_PYTHON
    # =========================
    if modo_benchmark_pytest():
        from pathlib import Path
        import os
        pasta_saida = Path(os.getenv("USERPROFILE")) / "Desktop" / "PeriTASK_pytest"
        pasta_saida.mkdir(parents=True, exist_ok=True)

    # =========================
    # ROTEAMENTO
    # =========================
    from utilitario.executor_comando import processar_payload    
    processar_payload(arquivos, payload_base64_from_ui,  pasta_saida)

if __name__ == "__main__":
    main()