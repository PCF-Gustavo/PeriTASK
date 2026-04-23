print("STATUS:Executando Python...", flush=True)
import sys
import os
import tempfile
import csv
import hashlib
from pathlib import Path
from pymediainfo import MediaInfo
import av  # libav / ffmpeg


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

    if len(pastas_selecionadas) == 1 and len(itens) == 1:
        return arquivos, os.path.dirname(pastas_selecionadas[0])

    try:
        pasta = os.path.commonpath(arquivos)
    except ValueError:
        return arquivos, None

    if not os.path.isdir(pasta):
        pasta = os.path.dirname(pasta)

    return arquivos, pasta


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


def calcular_sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(8192), b""):
            h.update(bloco)
    return h.hexdigest()


def to_int_ms_simples(value):
    if value is None:
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(float(value.strip())))
        except ValueError:
            return 0
    return 0


def obter_duracao_ms_mediainfo(arquivo_mediainfo):
    tracks = getattr(arquivo_mediainfo, "tracks", [])

    general = next((t for t in tracks if t.track_type == "General"), None)
    if general:
        ms = to_int_ms_simples(getattr(general, "duration", None))
        if ms > 0:
            return ms

    video = next((t for t in tracks if t.track_type == "Video"), None)
    if video:
        ms = to_int_ms_simples(getattr(video, "duration", None))
        if ms > 0:
            return ms

        try:
            if video.frame_count and video.frame_rate:
                return int(
                    (float(video.frame_count) /
                     float(str(video.frame_rate).replace(",", "."))) * 1000
                )
        except Exception:
            pass

        try:
            if video.frame_count and video.frame_rate_nominal:
                return int(
                    (float(video.frame_count) /
                     float(str(video.frame_rate_nominal).replace(",", "."))) * 1000
                )
        except Exception:
            pass

    return 0


def obter_duracao_ms_pyav(arquivo_pyav):
    stream = next((s for s in arquivo_pyav.streams if s.type == "video"), None)
    if not stream:
        stream = next((s for s in arquivo_pyav.streams if s.type == "audio"), None)

    if not stream:
        return 0

    first_pts = None
    last_pts = None

    for packet in arquivo_pyav.demux(stream):
        if packet.pts is None:
            continue
        if first_pts is None:
            first_pts = packet.pts
        last_pts = packet.pts

    if first_pts is None or last_pts is None:
        return 0

    duracao = (last_pts - first_pts) * float(stream.time_base)
    return int(duracao * 1000) if duracao > 0 else 0

def formatar_duracao_hh_mm_ss(ms):
    if not ms:
        return "00:00:00"

    total_segundos = int(ms // 1000)

    h = total_segundos // 3600
    m = (total_segundos % 3600) // 60
    s = total_segundos % 60

    return f"{h:02}:{m:02}:{s:02}"

def formatar_duracao_hh_mm_ssss(ms):
    if not ms:
        return "00:00:00,00"

    total_segundos = ms / 1000

    h = int(total_segundos // 3600)
    m = int((total_segundos % 3600) // 60)
    s = total_segundos % 60

    return f"{h:02}:{m:02}:{s:05.2f}"


def obter_fps(media, caminho):
    video = next((t for t in media.tracks if t.track_type == "Video"), None)

    if video:
        for attr in ("frame_rate", "frame_rate_nominal"):
            valor = getattr(video, attr, None)
            if valor:
                try:
                    fps = float(str(valor).replace(",", "."))
                    if fps > 0:
                        return fps
                except ValueError:
                    pass

    try:
        container = av.open(caminho)
        stream = next((s for s in container.streams if s.type == "video"), None)

        if stream and stream.average_rate:
            fps = float(stream.average_rate)
            if fps > 0:
                return fps
    except Exception:
        pass

    try:
        container = av.open(caminho)
        stream = next((s for s in container.streams if s.type == "video"), None)

        if not stream:
            return 0.0

        first_pts = None
        last_pts = None
        frames = 0

        for packet in container.demux(stream):
            for frame in packet.decode():
                if frame.pts is None:
                    continue

                if first_pts is None:
                    first_pts = frame.pts

                last_pts = frame.pts
                frames += 1

        if first_pts is None or last_pts is None or frames < 2:
            return 0.0

        duracao = (last_pts - first_pts) * float(stream.time_base)
        return frames / duracao if duracao > 0 else 0.0

    except Exception:
        return 0.0


def obter_fps_mediainfo(arquivo_mediainfo):
    track_video = next(
        (t for t in arquivo_mediainfo.tracks if t.track_type == "Video"),
        None
    )

    if not track_video:
        return 0

    # Campos possíveis onde o FPS pode estar
    campos_fps = (
        "frame_rate",
        "frame_rate_nominal",
        "frame_rate_real",
        "frame_rate_original",
    )

    for campo in campos_fps:
        valor = getattr(track_video, campo, None)

        if not valor:
            continue

        try:
            # Remove qualquer texto tipo " FPS"
            valor_limpo = str(valor).lower().replace("fps", "").strip()
            valor_limpo = valor_limpo.replace(",", ".")
            fps = float(valor_limpo)

            if fps > 0:
                return fps

        except ValueError:
            continue

    return 0

def obter_fps_pyav(arquivo_pyav):
    stream = next((s for s in arquivo_pyav.streams if s.type == "video"), None)
    if not stream: return 0

    first_pts = None
    last_pts = None
    frames = 0

    for packet in arquivo_pyav.demux(stream):
        for frame in packet.decode():
            if frame.pts is None:
                continue

            if first_pts is None:
                first_pts = frame.pts

            last_pts = frame.pts
            frames += 1

    if first_pts is None or last_pts is None or frames < 2:
        return 0.0

    duracao = (last_pts - first_pts) * float(stream.time_base)

    return frames / duracao if duracao > 0 else 0



def replace_com_incremento(caminho_tmp, caminho_saida):
    try:
        os.replace(caminho_tmp, caminho_saida)
        return caminho_saida
    except PermissionError:
        base, ext = os.path.splitext(caminho_saida)
        contador = 1

        while True:
            novo_caminho = f"{base}({contador}){ext}"
            try:
                os.replace(caminho_tmp, novo_caminho)
                return novo_caminho
            except PermissionError:
                contador += 1


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
            arquivo_pyav = av.open(arquivo)

            video_streams = [t for t in arquivo_mediainfo.tracks if t.track_type == "Video"]
            audio_streams = [t for t in arquivo_mediainfo.tracks if t.track_type == "Audio"]

            duracao_ms = (obter_duracao_ms_mediainfo(arquivo_mediainfo) or obter_duracao_ms_pyav(arquivo_pyav))
            duracao_total_ms += duracao_ms

            # fps_valor = obter_fps(arquivo_mediainfo, arquivo)
            fps = (obter_fps_mediainfo(arquivo_mediainfo) or obter_fps_pyav(arquivo_pyav))

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

def formata_tamanho(tamanho_bytes):
    if tamanho_bytes >= 1024 * 1024:
        tamanho_str = f"{tamanho_bytes / (1024 * 1024):.2f} MB"
    else:
        tamanho_str = f"{tamanho_bytes / 1024:.2f} KB"
    return tamanho_str.replace(".", ",")


def obter_conteiner_mediainfo(track_mediainfo):
    formato = getattr(track_mediainfo, "format", "")
    perfil = getattr(track_mediainfo, "format_profile", "")
    codec_id = getattr(track_mediainfo, "codec_id", "")
    codecid_compatible = getattr(track_mediainfo, "codecid_compatible", "")
    commercial_name = getattr(track_mediainfo, "commercial_name", "")
    compatible_brands = getattr(track_mediainfo, "compatible_brands", "")

    # Junta possíveis campos onde pode aparecer mp41/mp42/isom
    identificadores = f"{perfil} {codec_id} {codecid_compatible} {commercial_name} {compatible_brands}".lower()

    if "mp42" in identificadores:
        return "MPEG-4 (ISO Base Media v2)"

    elif "mp41" in identificadores or "isom" in identificadores:
        return "MPEG-4 (ISO Base Media v1)"

    # Caso não seja nenhum dos dois, mantém comportamento padrão
    elif perfil:
        return f"{formato} ({perfil})"

    else:
        return formato

def formata_bitrate(bitrate):
    if not bitrate: return ""

    if bitrate >= 1000:
        return f"{round(bitrate / 1000)} kbps"
    else:
        return f"{round(bitrate)} bps"

def obter_codec_video_mediainfo(track_mediainfo):
    formato = getattr(track_mediainfo, "format", "")
    codec_id = getattr(track_mediainfo, "codec_id", "")
    codec_hint = getattr(track_mediainfo, "codec_id_hint", "")

    perfil = getattr(track_mediainfo, "format_profile", "")
    
    identificadores = f"{formato} {codec_id} {codec_hint}".lower()

    # Determinar nome amigável do codec
    if "avc" in identificadores or "h264" in identificadores:
        codec_video = "H.264"

    elif "hevc" in identificadores or "h265" in identificadores:
        codec_video = "H.265"

    elif "vp9" in identificadores:
        codec_video = "VP9"

    elif "av1" in identificadores:
        codec_video = "AV1"

    elif "mpeg-4 visual" in identificadores or "mp4v" in identificadores:
        codec_video = "MPEG-4 Part 2"

    else:
        codec_video = formato

    if perfil:
        return f"{codec_video} ({perfil})"

    return codec_video

def obter_codec_audio_mediainfo(track_mediainfo):
    formato = getattr(track_mediainfo, "format", "")
    formato_info = getattr(track_mediainfo, "format_info", "")
    codec_id = getattr(track_mediainfo, "codec_id", "")
    codec_hint = getattr(track_mediainfo, "codec_id_hint", "")
    perfil = getattr(track_mediainfo, "format_profile", "")

    identificadores = f"{formato} {formato_info} {codec_id} {codec_hint}".lower()

    codec_audio = ""

    # =========================
    # DETECÇÃO DO CODEC BASE
    # =========================
    if "aac" in identificadores:
        codec_audio = "AAC"
    elif "mp3" in identificadores or "mpeg audio" in identificadores:
        codec_audio = "MP3"
    elif "e-ac-3" in identificadores or "eac3" in identificadores:
        codec_audio = "E-AC-3"
    elif "ac-3" in identificadores or "ac3" in identificadores:
        codec_audio = "AC-3"
    elif "dts" in identificadores:
        codec_audio = "DTS"
    elif "opus" in identificadores:
        codec_audio = "Opus"
    elif "vorbis" in identificadores:
        codec_audio = "Vorbis"
    elif "flac" in identificadores:
        codec_audio = "FLAC"
    elif "alac" in identificadores:
        codec_audio = "ALAC"
    elif "pcm" in identificadores:
        codec_audio = "PCM"
    else:
        codec_audio = formato

    # =========================
    # DETECÇÃO ROBUSTA DO PERFIL
    # =========================

    perfil_detectado = ""

    # 1 Se vier explícito
    if perfil:
        perfil_detectado = perfil

    # 2️ Detectar via identificadores
    elif any(x in identificadores for x in [
        "low complexity with spectral band replication and parametric stereo",
        "mp4a-40-29"
    ]):
        perfil_detectado = "High Efficiency v2"

    elif any(x in identificadores for x in [
        "low complexity with spectral band replication",
        "mp4a-40-5"
    ]):
        perfil_detectado = "High Efficiency v1"

    elif any(x in identificadores for x in [
        "low complexity",
        "mp4a-40-2"
    ]):
        perfil_detectado = "Low Complexity"

    if perfil_detectado:
        return f"{codec_audio} ({perfil_detectado})"

    return codec_audio

def obter_unidade_de_tempo_pyav(arquivo_pyav):
    if not arquivo_pyav: return ""

    video_stream = next((s for s in arquivo_pyav.streams if s.type == "video"), None)

    if not video_stream: return ""

    time_base = getattr(video_stream, "time_base", None)

    if not time_base or not time_base.denominator:
        return ""

    return f"{time_base.denominator} tbn"


def obter_fps_nominal_pyav(arquivo_pyav):
    if not arquivo_pyav: return ""

    video_stream = next((s for s in arquivo_pyav.streams if s.type == "video"), None)

    if not video_stream: return ""

    # average_rate é o equivalente ao tbr
    # rate = getattr(video_stream, "average_rate", None)
    rate = getattr(video_stream, "base_rate", None)

    if not rate: return ""

    return f"{rate:.2f} tbr"

def imprimir_tabela_completa_infos_csv(arquivos_videos, pasta_saida):
    arquivo_saida = "tabela_completa_de_informacoes.csv"
    caminho_saida = os.path.join(pasta_saida, arquivo_saida)
    caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_saida + ".tmp")

    total = len(arquivos_videos)

    print("STATUS:Vídeos -> tabela completa de informações em .csv", flush=True)

    if total == 0:
        print("PROGRESS:100", flush=True)
        return

    ultimo_progresso = -1

    with open(caminho_tmp, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")

        for i, arquivo in enumerate(arquivos_videos, start=1):
            arquivo_mediainfo = MediaInfo.parse(arquivo)
            arquivo_pyav = av.open(arquivo)

            # Nome
            writer.writerow(["Nome do Arquivo" , os.path.basename(arquivo)])

            # Tamanho
            tamanho_bytes = os.path.getsize(arquivo)
            tamanho_str = formata_tamanho(tamanho_bytes)
            writer.writerow(["Tamanho", tamanho_str ])

            # Duração
            duracao_ms = (obter_duracao_ms_mediainfo(arquivo_mediainfo) or obter_duracao_ms_pyav(arquivo_pyav))
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
                    overall_bitrate = getattr(track_mediainfo, "overall_bit_rate", "")
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
                    framerate_mode = getattr(track_mediainfo, "frame_rate_mode", "")
                    if framerate_mode == "CFR":
                        fps_constante = "Sim"
                    elif framerate_mode == "VFR":
                        fps_constante = "Não"
                    else:
                        fps_constante = ""
                    writer.writerow(["FPS constante", fps_constante])
                    
                    # FPS médio
                    fps = (obter_fps_mediainfo(arquivo_mediainfo) or obter_fps_pyav(arquivo_pyav))
                    writer.writerow(["FPS médio", f'="{f'{fps:.2f}'.replace('.', ',')}"'])
                    
                    # FPS nominal
                    fps_nominal = (getattr(track_mediainfo, "frame_rate_nominal", "") or obter_fps_nominal_pyav(arquivo_pyav))
                    writer.writerow(["FPS nominal", f'="{str(fps_nominal).replace('.', ',')}"'])
                    
                    # Unidade de tempo interna
                    unidade_de_tempo = obter_unidade_de_tempo_pyav(arquivo_pyav)
                    writer.writerow(["Unidade de tempo interna", unidade_de_tempo])
                    
                    # Espaço de cor
                    writer.writerow(["Espaço de cor", getattr(track_mediainfo, "color_space", "")])
                    
                    # Subamostragem de cor
                    writer.writerow(["Subamostragem de cor", f'="{getattr(track_mediainfo, "chroma_subsampling", "")}"'])
                    
                    # Profundidade de bits por canal
                    writer.writerow(["Profundidade de bits por canal", f'="{getattr(track_mediainfo, "bit_depth", "")} bits"'])
                    
                    # Cores primárias
                    cores_primarias = ( getattr(track_mediainfo, "color_primaries", "") or getattr(track_mediainfo, "transfer_characteristics", "") or getattr(track_mediainfo, "matrix_coefficients", "") or "(não informado)")
                    writer.writerow(["Cores primárias", cores_primarias ])
                    
                    # Tipo de varredura
                    scan_type = getattr(track_mediainfo, "scan_type", "")
                    if scan_type == "Progressive":
                        tipo_varredura = "Progressiva"
                    else:
                        tipo_varredura = "Entrelaçada"
                    writer.writerow(["Tipo de varredura", tipo_varredura])

                    # Taxa de bits
                    bitrate_video =  getattr(track_mediainfo, "bit_rate", "")
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
                    writer.writerow(["Taxa de amostragem", f"{getattr(track_mediainfo, "sampling_rate", "")} Hz"])

                    # Canais
                    canais = getattr(track_mediainfo, "channel_s", "")
                    if canais == 1:
                        canais_str = "Mono"
                    elif canais == 2:
                        canais_str = "Estéreo"
                    else:
                        canais_str = ""
                    writer.writerow(["Canais", canais_str ])

                    # Taxa de bits
                    bitrate_audio =  getattr(track_mediainfo, "bit_rate", "")
                    bitrate_audio_str = formata_bitrate(bitrate_audio)
                    writer.writerow(["Taxa de bits", bitrate_audio_str])

                # Outros fluxos
                else:
                    pass

            arquivo_pyav.close()
            writer.writerow([])

            progresso = int((i / total) * 100)
            if progresso != ultimo_progresso:
                print(f"PROGRESS:{progresso}", flush=True)
                ultimo_progresso = progresso

    replace_com_incremento(caminho_tmp, caminho_saida)

def obter_videos(arquivos):
    extensoes_video = {
        ".avi", ".mp4", ".mkv", ".mov", ".wmv", ".flv",
        ".mpeg", ".mpg", ".webm", ".dav", ".m4v",
        ".3gp", ".ts", ".vob"
    }
    arquivos_videos = [ arq for arq in arquivos if Path(arq).suffix.lower() in extensoes_video ]
    return arquivos_videos


def main():
    if len(sys.argv) < 3:
        # sys.exit(1)
        itens_selecionados = r"C:\Users\gustavo.gvs\Desktop\teste.mp4"
        selecao_ComboBox = f"Vídeos -> tabela completa de informações em .csv"
        arquivos = [r"C:\Users\gustavo.gvs\Desktop\teste.mp4"]
        pasta_saida = r"C:\Users\gustavo.gvs\Desktop"
    else:
        itens_selecionados = sys.argv[1].split("|")
        selecao_ComboBox = sys.argv[2]
        arquivos, pasta_saida = coletar_arquivos_e_pasta_saida(itens_selecionados)

    if selecao_ComboBox == f"Arquivos -> lista de caminhos em .txt":
        imprimir_lista_caminhos_txt(arquivos, pasta_saida)
    elif selecao_ComboBox == f"Vídeos -> tabela simplificada de informações em .csv":
        arquivos_videos = obter_videos(arquivos)
        imprimir_tabela_simplificada_infos_csv(arquivos_videos, pasta_saida)
    elif selecao_ComboBox == f"Vídeos -> tabela completa de informações em .csv":
        arquivos_videos = obter_videos(arquivos)
        imprimir_tabela_completa_infos_csv(arquivos_videos, pasta_saida)


if __name__ == "__main__":
    main()