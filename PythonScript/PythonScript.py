import sys
import os

def coletar_arquivos_e_pasta_saida(itens):
    arquivos = set()
    pastas_selecionadas = []

    for item in itens:
        if not item:
            continue

        if item.startswith(("::", "shell:")):
            continue

        caminho = os.path.abspath(item)

        if not os.path.exists(caminho):
            continue

        if caminho.lower().endswith(".lnk"):
            continue

        if os.path.isdir(caminho):
            pastas_selecionadas.append(caminho)

            for raiz, _, nomes in os.walk(
                caminho,
                followlinks=False,
                onerror=lambda e: None
            ):
                for nome in nomes:
                    arquivo = os.path.join(raiz, nome)
                    if os.path.isfile(arquivo):
                        arquivos.add(arquivo)

        elif os.path.isfile(caminho):
            arquivos.add(caminho)

    arquivos = sorted(arquivos)

    if not arquivos:
        return [], None

    # 🔹 CASO ESPECIAL: exatamente 1 pasta selecionada
    if len(pastas_selecionadas) == 1 and len(itens) == 1:
            return arquivos, os.path.dirname(pastas_selecionadas[0])

    # 🔹 CASO GERAL
    try:
        pasta = os.path.commonpath(arquivos)
    except ValueError:
        return arquivos, None

    if not os.path.isdir(pasta):
        pasta = os.path.dirname(pasta)

    return arquivos, pasta


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    itens_selecionados  = sys.argv[1].split("|")
    
    arquivos, pasta_saida = coletar_arquivos_e_pasta_saida(itens_selecionados)

    if not arquivos:
        print("Nenhum arquivo válido encontrado.")
        sys.exit(1)

    if not pasta_saida:
        print("Os itens selecionados não compartilham uma pasta raiz.")
        sys.exit(1)

    caminho_saida = os.path.join(
        pasta_saida,
        "caminho_dos_arquivos.txt"
    )

    total = len(arquivos)

    try:
        with open(caminho_saida, "w", encoding="utf-8") as f:
            for i, arquivo in enumerate(arquivos, start=1):
                f.write(arquivo + "\n")

                progresso = int((i / total) * 100)
                print(f"PROGRESS:{progresso}", flush=True)

        print("DONE", flush=True)

    except PermissionError:
        print(
            f"Sem permissão para criar o arquivo em:\n{pasta_saida}"
        )
        sys.exit(1)

    except OSError as e:
        print(
            f"Erro ao criar o arquivo:\n{e}"
        )
        sys.exit(1)



if __name__ == "__main__":
    main()
