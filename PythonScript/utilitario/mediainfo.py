from utilitario.formatacao import to_int_ms_simples

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