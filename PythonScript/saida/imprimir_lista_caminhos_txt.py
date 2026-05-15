import os

def imprimir_lista_caminhos_txt(arquivos, pasta_saida):
    arquivo_saida = "caminho_dos_arquivos.txt"
    caminho_saida = os.path.join(pasta_saida, arquivo_saida)
    caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_saida + ".tmp")

    print("STATUS:Imprimindo caminhos dos arquivos em .txt", flush=True)

    total = len(arquivos)
    ultimo_progresso = -1

    if total == 0:
        print("PROGRESS:100", flush=True)
        return

    with open(caminho_tmp, "w", encoding="utf-8") as f:
        for i, arquivo in enumerate(arquivos, start=1):
            f.write(arquivo + "\n")

            progresso = int((i / total) * 100)
            if progresso != ultimo_progresso:
                print(f"PROGRESS:{progresso}", flush=True)
                ultimo_progresso = progresso

    os.replace(caminho_tmp, caminho_saida)