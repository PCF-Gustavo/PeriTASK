import sys
import os

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    arquivos = sys.argv[1].split("|")

    pasta = os.path.dirname(arquivos[0])
    caminho_txt = os.path.join(pasta, "lista_arquivos.txt")

    with open(caminho_txt, "w", encoding="utf-8") as f:
        for caminho in arquivos:
            f.write(caminho + "\n")

    print(caminho_txt)


if __name__ == "__main__":
    main()
