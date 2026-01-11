import sys
import os
import tempfile
import csv
import hashlib

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


def imprimir_caminhos_txt(arquivos, pasta_saida):
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


def formatar_duracao(ms):
    if not ms:
        return "0:0:0"
    total = int(ms // 1000)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h}:{m}:{s}"


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


def obter_duracao_ms_mediainfo(media):
    tracks = getattr(media, "tracks", [])

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


def obter_duracao_ms_pyav(caminho):
    try:
        container = av.open(caminho)

        stream = next((s for s in container.streams if s.type == "video"), None)
        if not stream:
            stream = next((s for s in container.streams if s.type == "audio"), None)

        if not stream:
            return 0

        first_pts = None
        last_pts = None

        for packet in container.demux(stream):
            if packet.pts is None:
                continue
            if first_pts is None:
                first_pts = packet.pts
            last_pts = packet.pts

        if first_pts is None or last_pts is None:
            return 0

        duracao = (last_pts - first_pts) * float(stream.time_base)
        return int(duracao * 1000) if duracao > 0 else 0

    except Exception:
        return 0


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
    duracao_total_ms = 0

    print("STATUS:Imprimindo tabelas de informações dos arquivos em .csv", flush=True)

    if total == 0:
        print("PROGRESS:100", flush=True)
        return

    ultimo_progresso = -1

    with open(caminho_tmp, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")

        writer.writerow([
            "#", "Pasta", "Nome do Arquivo", "Hash SHA-256",
            "Duracao", "Fluxos de Video", "Fluxos de Audio",
            "FPS", "Resolucao"
        ])

        for i, arquivo in enumerate(arquivos_video, start=1):
            media = MediaInfo.parse(arquivo)

            video_streams = [t for t in media.tracks if t.track_type == "Video"]
            audio_streams = [t for t in media.tracks if t.track_type == "Audio"]

            duracao_ms = obter_duracao_ms_mediainfo(media)
            if duracao_ms == 0:
                duracao_ms = obter_duracao_ms_pyav(arquivo)

            duracao_total_ms += duracao_ms

            fps_valor = obter_fps(media, arquivo)

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
                formatar_duracao(duracao_ms),
                len(video_streams),
                len(audio_streams),
                f"{fps_valor:.3f}" if fps_valor > 0 else "0",
                resolucao
            ])

            progresso = int((i / total) * 100)
            if progresso != ultimo_progresso:
                print(f"PROGRESS:{progresso}", flush=True)
                ultimo_progresso = progresso

        writer.writerow([
            "", "", "", "Duracao Total",
            formatar_duracao(duracao_total_ms),
            "", "", "", ""
        ])

    os.replace(caminho_tmp, caminho_saida)


def main():
    if len(sys.argv) < 3:
        sys.exit(1)

    itens_selecionados = sys.argv[1].split("|")
    selecao_ComboBox = sys.argv[2]

    arquivos, pasta_saida = coletar_arquivos_e_pasta_saida(itens_selecionados)

    if selecao_ComboBox == "Imprimir caminhos em .txt":
        imprimir_caminhos_txt(arquivos, pasta_saida)
    elif selecao_ComboBox == "Imprimir tabela de informações em .csv":
        imprimir_infos_csv(arquivos, pasta_saida)


if __name__ == "__main__":
    main()