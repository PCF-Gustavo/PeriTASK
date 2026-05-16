import os
import hashlib
from pathlib import Path

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


def obter_duracao_ms_pyav(arquivo):
    import av
    arquivo_pyav = av.open(arquivo)
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

def obter_cfr_vfr_pyav(arquivo, tolerancia=0.01):
    import av
    arquivo_pyav = av.open(arquivo)
    stream = next((s for s in arquivo_pyav.streams if s.type == "video"), None)
    if not stream:
        return ""

    pts_list = []
    for packet in arquivo_pyav.demux(stream):
        if packet.pts is not None:
            pts_list.append(packet.pts)

    if len(pts_list) < 3:
        return ""

    # calcular deltas (diferença entre timestamps consecutivos)
    deltas = [
        (pts_list[i+1] - pts_list[i]) * float(stream.time_base)
        for i in range(len(pts_list) - 1)
    ]

    # média e variação
    media = sum(deltas) / len(deltas)

    if media <= 0:
        return ""

    max_delta = max(deltas)
    min_delta = min(deltas)

    variacao_relativa = (max_delta - min_delta) / media

    if variacao_relativa <= tolerancia:
        return "CFR"
    else:
        return "VFR"

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

def obter_fps_pyav(arquivo, duracao_ms = None):
    import av
    arquivo_pyav = av.open(arquivo)
    stream = next((s for s in arquivo_pyav.streams if s.type == "video"), None)
    if not stream:
        return 0

    frames = 0
    for packet in arquivo_pyav.demux(stream):
        if packet.pts is None:
            continue
        frames += 1
        
    if frames > 0:
        return  frames / (duracao_ms/1000)
    
    if stream.average_rate:
        return float(stream.average_rate)

    return 0

def obter_bitrate_pyav(arquivo, tipo, duracao_ms):
    import av
    arquivo_pyav = av.open(arquivo)
    stream = next((s for s in arquivo_pyav.streams if s.type == tipo), None)
    if not stream:
        return 0
    
    if stream and stream.bit_rate:
        return stream.bit_rate

    total_bytes = 0
    for packet in arquivo_pyav.demux(stream):
        total_bytes += packet.size

    # bitrate em bits por segundo
    bitrate_bps = (total_bytes * 8) / (duracao_ms/1000)

    return bitrate_bps

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

def obter_unidade_de_tempo_pyav(arquivo):
    import av
    arquivo_pyav = av.open(arquivo)
    if not arquivo_pyav: return ""

    video_stream = next((s for s in arquivo_pyav.streams if s.type == "video"), None)

    if not video_stream: return ""

    time_base = getattr(video_stream, "time_base", None)

    if not time_base or not time_base.denominator:
        return ""

    return f"{time_base.denominator} tbn"


def obter_fps_nominal_pyav(arquivo):
    import av
    arquivo_pyav = av.open(arquivo)
    if not arquivo_pyav: return ""

    video_stream = next((s for s in arquivo_pyav.streams if s.type == "video"), None)

    if not video_stream: return ""

    rate = getattr(video_stream, "base_rate", None)

    if not rate: return ""

    return f"{float(rate):.2f} tbr"

def obter_videos(arquivos):
    extensoes_video = {
        ".avi", ".mp4", ".mkv", ".mov", ".wmv", ".flv",
        ".mpeg", ".mpg", ".webm", ".dav", ".m4v",
        ".3gp", ".ts", ".vob"
    }
    arquivos_videos = [ arq for arq in arquivos if Path(arq).suffix.lower() in extensoes_video ]
    return arquivos_videos
