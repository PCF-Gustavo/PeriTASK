import os
import csv
from pymediainfo import MediaInfo
from utilitario.mediainfo import obter_duracao_ms_mediainfo, obter_fps_mediainfo, obter_conteiner_mediainfo, obter_codec_video_mediainfo, obter_codec_audio_mediainfo
from utilitario.pyav import obter_duracao_ms_pyav, obter_fps_pyav, obter_cfr_vfr_pyav, obter_bitrate_pyav, obter_unidade_de_tempo_pyav, obter_fps_nominal_pyav
from utilitario.formatacao import formatar_duracao_hh_mm_ssss, formata_tamanho, formata_bitrate, formatar_duracao_hh_mm_ss
from utilitario.outros import replace_com_incremento, obter_videos, calcular_sha256


def gerar_tabela_simplificada(arquivos_videos, pasta_saida):
    arquivo_saida = "tabela_simplificada_de_informacoes.csv"
    caminho_saida = os.path.join(pasta_saida, arquivo_saida)
    caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_saida + ".tmp")

    total = len(arquivos_videos)
    duracao_total_ms = 0

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

            fps = obter_fps_mediainfo(arquivo_mediainfo) or obter_fps_pyav(arquivo, duracao_ms)

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


def gerar_tabela_completa(arquivos_videos, pasta_saida):
    arquivo_saida = "tabela_completa_de_informacoes.csv"
    caminho_saida = os.path.join(pasta_saida, arquivo_saida)
    caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_saida + ".tmp")

    total = len(arquivos_videos)

    if total == 0:
        print("PROGRESS:100", flush=True)
        return

    ultimo_progresso = -1

    with open(caminho_tmp, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")

        for i, arquivo in enumerate(arquivos_videos, start=1):
            arquivo_mediainfo = MediaInfo.parse(arquivo)

            # Nome
            writer.writerow(["Nome do Arquivo", os.path.basename(arquivo)])

            # Tamanho
            tamanho_bytes = os.path.getsize(arquivo)
            tamanho_str = formata_tamanho(tamanho_bytes)
            writer.writerow(["Tamanho", tamanho_str])

            # Duração
            duracao_ms = obter_duracao_ms_mediainfo(arquivo_mediainfo) or obter_duracao_ms_pyav(arquivo)
            writer.writerow(["Duracao", formatar_duracao_hh_mm_ssss(duracao_ms)])

            contador_fluxo_video = 0
            contador_fluxo_audio = 0

            # FLUXOS
            for track_mediainfo in arquivo_mediainfo.tracks:
                # Fluxo geral
                if track_mediainfo.track_type == "General":

                    # Formato do conteiner
                    container = obter_conteiner_mediainfo(track_mediainfo)
                    writer.writerow(["Formato do contêiner", container])

                    # Taxa de bits total
                    overall_bitrate = getattr(track_mediainfo, "overall_bit_rate", "") or ((tamanho_bytes * 8) / (duracao_ms / 1000.0))
                    overall_bitrate_str = formata_bitrate(overall_bitrate)
                    writer.writerow(["Taxa de bits total", overall_bitrate_str])

                # Fluxos de Video
                if track_mediainfo.track_type == "Video":
                    contador_fluxo_video += 1
                    writer.writerow([f"Fluxo de Vídeo ({contador_fluxo_video})"])

                    # Codificação
                    codec_video = obter_codec_video_mediainfo(track_mediainfo)
                    writer.writerow(["Codificação", codec_video])

                    # Resolução
                    writer.writerow(["Resolução (LxA)", f"{track_mediainfo.width}x{track_mediainfo.height}"])

                    # FPS constante
                    framerate_mode = getattr(track_mediainfo, "frame_rate_mode", "") or obter_cfr_vfr_pyav(arquivo, tolerancia=0.03)
                    if framerate_mode == "CFR":
                        fps_constante = "Sim"
                    elif framerate_mode == "VFR":
                        fps_constante = "Não"
                    else:
                        fps_constante = ""
                    writer.writerow(["FPS constante", fps_constante])

                    # FPS médio
                    fps = obter_fps_mediainfo(arquivo_mediainfo) or obter_fps_pyav(arquivo, duracao_ms)
                    writer.writerow(["FPS médio", f'="{fps:.2f}"'.replace('.', ',')])

                    # FPS nominal
                    fps_nominal = getattr(track_mediainfo, "frame_rate_nominal", "") or obter_fps_nominal_pyav(arquivo)
                    writer.writerow(["FPS nominal", f'="{str(fps_nominal).replace(".", ",")}"'])

                    # Unidade de tempo interna
                    unidade_de_tempo = obter_unidade_de_tempo_pyav(arquivo)
                    writer.writerow(["Unidade de tempo interna", unidade_de_tempo])

                    # Espaço de cor
                    writer.writerow(["Espaço de cor", getattr(track_mediainfo, "color_space", "")])

                    # Subamostragem de cor
                    writer.writerow(["Subamostragem de cor", f'="{getattr(track_mediainfo, "chroma_subsampling", "")}"'])

                    # Profundidade de bits por canal
                    writer.writerow(["Profundidade de bits por canal", f'="{getattr(track_mediainfo, "bit_depth", "")} bits"'])

                    # Cores primárias
                    cores_primarias = (
                        getattr(track_mediainfo, "color_primaries", "")
                        or getattr(track_mediainfo, "transfer_characteristics", "")
                        or getattr(track_mediainfo, "matrix_coefficients", "")
                        or "(não informado)"
                    )
                    writer.writerow(["Cores primárias", cores_primarias])

                    # Tipo de varredura
                    scan_type = getattr(track_mediainfo, "scan_type", "")
                    if scan_type == "Progressive":
                        tipo_varredura = "Progressiva"
                    else:
                        tipo_varredura = "Entrelaçada"
                    writer.writerow(["Tipo de varredura", tipo_varredura])

                    # Taxa de bits
                    bitrate_video = getattr(track_mediainfo, "bit_rate", "") or obter_bitrate_pyav(arquivo, "video", duracao_ms)
                    bitrate_video_str = formata_bitrate(bitrate_video)
                    writer.writerow(["Taxa de bits", bitrate_video_str])

                # Fluxos de Audio
                elif track_mediainfo.track_type == "Audio":
                    contador_fluxo_audio += 1
                    writer.writerow([f"Fluxo de Áudio ({contador_fluxo_audio})"])

                    # Codificação
                    codec_audio = obter_codec_audio_mediainfo(track_mediainfo)
                    writer.writerow(["Codificação", codec_audio])

                    # Taxa de amostragem
                    writer.writerow(["Taxa de amostragem", f'{getattr(track_mediainfo, "sampling_rate", "")} Hz'])

                    # Canais
                    canais = getattr(track_mediainfo, "channel_s", "")
                    if canais == 1:
                        canais_str = "Mono"
                    elif canais == 2:
                        canais_str = "Estéreo"
                    else:
                        canais_str = ""
                    writer.writerow(["Canais", canais_str])

                    # Taxa de bits
                    bitrate_audio = getattr(track_mediainfo, "bit_rate", "") or obter_bitrate_pyav(arquivo, "audio", duracao_ms)
                    bitrate_audio_str = formata_bitrate(bitrate_audio)
                    writer.writerow(["Taxa de bits", bitrate_audio_str])

                # Outros fluxos
                else:
                    pass

            writer.writerow([])

            progresso = int((i / total) * 100)
            if progresso != ultimo_progresso:
                print(f"PROGRESS:{progresso}", flush=True)
                ultimo_progresso = progresso

    replace_com_incremento(caminho_tmp, caminho_saida)


def executar(arquivos, controls, pasta_saida):
    arquivos_videos = obter_videos(arquivos)

    tipo_tabela = str(controls.get("tipo_tabela"))

    if tipo_tabela == "simplificada":
        gerar_tabela_simplificada(arquivos_videos, pasta_saida)

    if tipo_tabela == "completa":
        gerar_tabela_completa(arquivos_videos, pasta_saida)