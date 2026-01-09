import sys
import os

def pasta_raiz(caminhos):
    try:
        pasta_comum = os.path.commonpath(caminhos)
    except ValueError:
        print("Os arquivos selecionados não compartilham uma pasta raiz.")
        sys.exit(1)

    if not os.path.isdir(pasta_comum):
        pasta_comum = os.path.dirname(pasta_comum)

    return pasta_comum


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    arquivos_selecionados = sys.argv[1].split("|")

    pasta_saida = pasta_raiz(arquivos_selecionados)

    caminho_saida = os.path.join(
        pasta_saida,
        "caminho_dos_arquivos_selecionados.txt"
    )

    with open(caminho_saida, "w", encoding="utf-8") as f:
        for arquivo in arquivos_selecionados:
            f.write(arquivo + "\n")


if __name__ == "__main__":
    main()
