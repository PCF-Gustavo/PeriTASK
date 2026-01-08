import sys
import os

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    arquivos_selecionados = sys.argv[1].split("|")

    with open(os.path.join(os.path.dirname(arquivos_selecionados[0]), 
                            "caminho_dos_arquivos_selecionados.txt"),
                            "w", encoding="utf-8") as f:
        for arquivo in arquivos_selecionados:
            f.write(arquivo + "\n")


if __name__ == "__main__":
    main()
