import sys
import os
import time
import tempfile
import csv
import hashlib
from pymediainfo import MediaInfo

def tem_permissao_escrita(pasta):
    try:
        with tempfile.NamedTemporaryFile(
            dir=pasta,
            mode="w",
            encoding="utf-8",
            delete=True
        ) as f:
            f.write("teste")
        return True
    except Exception:
        return False


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

def imprimir_caminhos_txt(arquivos, pasta_saida):
    arquivo_saida = "caminho_dos_arquivos.txt"
    caminho_saida = os.path.join(pasta_saida, arquivo_saida)
    caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_saida + ".tmp")
    
    total = len(arquivos)
    with open(caminho_tmp, "w", encoding="utf-8") as f:
        for i, arquivo in enumerate(arquivos, start=1):
            f.write(arquivo + "\n")
            progresso = int((i / total) * 100)
            print(f"STATUS:{'Imprimindo caminhos dos arquivos em .txt'}", flush=True)
            print(f"PROGRESS:{progresso}", flush=True)
    
    os.replace(caminho_tmp, caminho_saida)
    
def calcular_sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(8192), b""):
            h.update(bloco)
    return h.hexdigest()

def formatar_duracao(ms):
    if not ms:
        return "0:0:0"
    total = int(ms // 1000)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h}:{m}:{s}"

def imprimir_infos_csv(arquivos, pasta_saida):
    arquivo_saida = "tabela_de_informacoes.csv"
    caminho_saida = os.path.join(pasta_saida, arquivo_saida)
    caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_saida + ".tmp")

    extensoes_video = {
        ".avi", ".mp4", ".mkv", ".mov", ".wmv", ".flv",
        ".mpeg", ".mpg", ".webm", ".dav", ".m4v",
        ".3gp", ".ts", ".vob"
    }

    arquivos_video = [
        a for a in arquivos
        if os.path.splitext(a)[1].lower() in extensoes_video
    ]

    total = len(arquivos_video)

    with open(caminho_tmp, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")

        writer.writerow([
            "#", "Pasta", "Nome do Arquivo", "Hash SHA-256",
            "Duracao", "Fluxos de Video", "Fluxos de Audio",
            "FPS", "Resolucao"
        ])

        for i, arquivo in enumerate(arquivos_video, start=1):
            try:
                media = MediaInfo.parse(arquivo)

                video_streams = [t for t in media.tracks if t.track_type == "Video"]
                audio_streams = [t for t in media.tracks if t.track_type == "Audio"]
                general = next(
                    (t for t in media.tracks if t.track_type == "General"), None
                )

                duracao = formatar_duracao(
                    general.duration if general and general.duration else 0
                )

                fps = "0/0"
                resolucao = "Unknown"

                if video_streams:
                    v = video_streams[0]

                    if v.frame_rate:
                        fps = str(v.frame_rate)

                    if v.width and v.height:
                        resolucao = f"{v.width}x{v.height}"

                hash_sha256 = calcular_sha256(arquivo)

                writer.writerow([
                    i,
                    os.path.dirname(arquivo),
                    os.path.basename(arquivo),
                    hash_sha256,
                    duracao,
                    len(video_streams),
                    len(audio_streams),
                    fps,
                    resolucao
                ])

                progresso = int((i / total) * 100)
                print(
                    "STATUS:Imprimindo tabelas de informações dos arquivos em .csv",
                    flush=True
                )
                print(f"PROGRESS:{progresso}", flush=True)

            except Exception:
                print(
                    f"STATUS:Erro ao processar {os.path.basename(arquivo)}",
                    flush=True
                )

    os.replace(caminho_tmp, caminho_saida)


# def imprimir_infos_csv(arquivos, pasta_saida):
#     arquivo_saida = "tabela_de_informacoes.csv"
#     caminho_saida = os.path.join(pasta_saida, arquivo_saida)
#     caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_saida + ".tmp")
    
#     total = len(arquivos)
#     with open(caminho_tmp, "w", encoding="utf-8") as f:
#         for i, arquivo in enumerate(arquivos, start=1):
#             f.write(arquivo + "\n")
#             time.sleep(0.001)
#             progresso = int((i / total) * 100)
#             print(f"STATUS:{'Imprimindo tabelas de informações dos arquivos em .csv'}", flush=True)
#             print(f"PROGRESS:{progresso}", flush=True)
    
#     os.replace(caminho_tmp, caminho_saida)

def main():
    try:
        if len(sys.argv) < 2:
            print("Argumentos dos itens seleciondos ausentes.")
            sys.exit(1)
        
        elif len(sys.argv) < 3:
            print("Argumento da selecao da ComboBox ausente.")
            sys.exit(1)


        itens_selecionados  = sys.argv[1].split("|")
        selecao_ComboBox  = sys.argv[2]
    
        arquivos, pasta_saida = coletar_arquivos_e_pasta_saida(itens_selecionados)

        if not arquivos:
            print("Nenhum arquivo válido encontrado.")
            sys.exit(1)

        if not pasta_saida:
            print("Os itens selecionados não compartilham uma pasta raiz.")
            sys.exit(1)

        if not tem_permissao_escrita(pasta_saida):
            print(f"Sem permissão de escrita na pasta:\n{pasta_saida}")
            sys.exit(1)

        if (selecao_ComboBox == "Imprimir caminhos em .txt"):
            try:
                imprimir_caminhos_txt(arquivos, pasta_saida)
            except Exception as e:
                print(f"Erro ao criar arquivo:\n{e}")
                sys.exit(1)
        elif (selecao_ComboBox == "Imprimir tabela de informações em .csv"):
            try:
                imprimir_infos_csv(arquivos, pasta_saida)
            except Exception as e:
                print(f"Erro ao criar arquivo:\n{e}")
                sys.exit(1)
        
    except Exception as e:
        print(f"Erro inesperado:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
