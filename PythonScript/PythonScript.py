import sys
import os

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    arquivos_selecionados = sys.argv[1].split("|")

    pasta = os.path.dirname(arquivos_selecionados[0])
    caminho_txt = os.path.join(pasta, "arquivos_selecionados.txt")

    with open(caminho_txt, "w", encoding="utf-8") as f:
        for caminho in arquivos_selecionados:
            f.write(caminho + "\n")


if __name__ == "__main__":
    main()
