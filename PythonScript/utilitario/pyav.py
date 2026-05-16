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

