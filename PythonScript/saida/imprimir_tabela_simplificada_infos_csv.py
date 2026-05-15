from lazy_imports import lazy_imports
MediaInfo = lazy_imports("pymediainfo", "MediaInfo")

import os
import csv
from utilitario.utilitario import (
    calcular_sha256,
    obter_duracao_ms_mediainfo,
    obter_duracao_ms_pyav,
    obter_fps_mediainfo,
    obter_fps_pyav,
    formatar_duracao_hh_mm_ss,
    replace_com_incremento,
)


def imprimir_tabela_simplificada_infos_csv(arquivos_videos, pasta_saida):
    arquivo_saida = "tabela_simplificada_de_informacoes.csv"
    caminho_saida = os.path.join(pasta_saida, arquivo_saida)
    caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_saida + ".tmp")

    total = len(arquivos_videos)
    duracao_total_ms = 0

    print("STATUS:Vídeos -> tabela simplificada de informações em .csv", flush=True)

    if total == 0:
        print("PROGRESS:100", flush=True)
        return

    ultimo_progresso = -1

    with open(caminho_tmp, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")

        writer.writerow([
            "#", "Pasta", "Nome do Arquivo", "Hash SHA-256",
            "Duracao", "Fluxos de Video", "Fluxos de Audio",
            "FPS", "Resolucao"
        ])

        for i, arquivo in enumerate(arquivos_videos, start=1):
            arquivo_mediainfo = MediaInfo.parse(arquivo)

            video_streams = [t for t in arquivo_mediainfo.tracks if t.track_type == "Video"]
            audio_streams = [t for t in arquivo_mediainfo.tracks if t.track_type == "Audio"]

            duracao_ms = obter_duracao_ms_mediainfo(arquivo_mediainfo) or obter_duracao_ms_pyav(arquivo)
            duracao_total_ms += duracao_ms

            fps = obter_fps_mediainfo(arquivo_mediainfo) or obter_fps_pyav(arquivo,duracao_ms)

            resolucao = "Unknown"
            if video_streams:
                v = video_streams[0]
                if v.width and v.height:
                    resolucao = f"{v.width}x{v.height}"

            writer.writerow([
                i,
                os.path.dirname(arquivo),
                os.path.basename(arquivo),
                calcular_sha256(arquivo),
                formatar_duracao_hh_mm_ss(duracao_ms),
                len(video_streams),
                len(audio_streams),
                f"{fps:.0f}",
                resolucao
            ])

            progresso = int((i / total) * 100)
            if progresso != ultimo_progresso:
                print(f"PROGRESS:{progresso}", flush=True)
                ultimo_progresso = progresso

        writer.writerow([
            "", "", "", "Duracao Total",
            formatar_duracao_hh_mm_ss(duracao_total_ms),
            "", "", "", ""
        ])

    replace_com_incremento(caminho_tmp, caminho_saida)