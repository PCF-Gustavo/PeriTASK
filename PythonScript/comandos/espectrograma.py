import os
import av
import numpy as np
import matplotlib.pyplot as plt

from scipy.signal import spectrogram

from utilitario.outros import replace_com_incremento, selecionar_arquivos


def extrair_audio_pyav(arquivo, sample_rate):
    amostras = []

    with av.open(arquivo) as container:
        audio_streams = [s for s in container.streams if s.type == "audio"]

        if not audio_streams:
            return np.array([], dtype=np.float32)

        stream = audio_streams[0]

        resampler = av.audio.resampler.AudioResampler(
            format="s16",
            layout="mono",
            rate=sample_rate
        )

        for frame in container.decode(stream):
            frames_resampled = resampler.resample(frame)

            if frames_resampled is None:
                continue

            if not isinstance(frames_resampled, list):
                frames_resampled = [frames_resampled]

            for frame_resampled in frames_resampled:
                audio_np = frame_resampled.to_ndarray()

                if audio_np.size > 0:
                    amostras.append(audio_np.reshape(-1))

        # Flush do resampler, se houver amostras pendentes
        try:
            frames_resampled = resampler.resample(None)

            if frames_resampled is not None:
                if not isinstance(frames_resampled, list):
                    frames_resampled = [frames_resampled]

                for frame_resampled in frames_resampled:
                    audio_np = frame_resampled.to_ndarray()

                    if audio_np.size > 0:
                        amostras.append(audio_np.reshape(-1))
        except Exception:
            pass

    if not amostras:
        return np.array([], dtype=np.float32)

    audio = np.concatenate(amostras).astype(np.float32)

    # PCM 16-bit para escala aproximada -1 a 1
    audio /= 32768.0

    return audio


def executar(arquivos, controls, pasta_saida):
    arquivos_audios_e_videos = selecionar_arquivos(arquivos, ["audio", "video"])

    escala_y = controls.get("escala_y") or "linear"

    if escala_y == "logaritmica":
        escala_y = "log"

    if escala_y not in ("linear", "log"):
        escala_y = "linear"

    # ===== Configurações =====
    sample_rate = 44100
    nfft = 2048
    noverlap = 1024
    cmap = "inferno"

    freq_min = 20
    freq_max = sample_rate / 2

    vmin = -120
    vmax = -20
    # =========================

    total = len(arquivos_audios_e_videos)

    if total == 0:
        print("PROGRESS:100", flush=True)
        return

    ultimo_progresso = -1

    for i, arquivo in enumerate(arquivos_audios_e_videos, start=1):
        file_name = os.path.splitext(os.path.basename(arquivo))[0]

        arquivo_saida = f"Espectrograma_{file_name}.png"
        caminho_saida = os.path.join(pasta_saida, arquivo_saida)

        arquivo_tmp = f"Espectrograma_{file_name}_{i}.tmp.png"
        caminho_tmp = os.path.join(os.getenv("TEMP"), arquivo_tmp)

        try:
            audio = extrair_audio_pyav(arquivo, sample_rate)
        except Exception as exc:
            print(
                f"STATUS:Falha ao processar áudio de {os.path.basename(arquivo)}: {exc}",
                flush=True
            )
            audio = np.array([], dtype=np.float32)

        if audio.size == 0:
            print(
                f"STATUS:Arquivo sem áudio ou áudio não decodificável: {os.path.basename(arquivo)}",
                flush=True
            )
        else:
            # Normaliza sem risco de divisão por zero
            max_amp = np.max(np.abs(audio))

            if max_amp > 0:
                audio = audio / max_amp

            # Calcula espectrograma usando SciPy,
            # equivalente ao código que gerou a imagem de referência
            f, t, Sxx = spectrogram(
                audio,
                fs=sample_rate,
                window=("tukey", 0.25),
                nperseg=nfft,
                noverlap=noverlap,
                nfft=nfft,
                detrend="constant",
                return_onesided=True,
                scaling="density",
                mode="psd"
            )

            Sxx_db = 10 * np.log10(Sxx + 1e-10)

            mascara_freq = (f >= freq_min) & (f <= freq_max)

            f_plot = f[mascara_freq]
            Sxx_db_plot = Sxx_db[mascara_freq, :]

            plt.figure(figsize=(10, 5))

            plt.imshow(
                Sxx_db_plot,
                aspect="auto",
                origin="lower",
                extent=[
                    t.min(),
                    t.max(),
                    f_plot.min(),
                    f_plot.max()
                ],
                cmap=cmap,
                vmin=vmin,
                vmax=vmax
            )

            plt.yscale(escala_y)
            plt.ylim(freq_min, freq_max)

            plt.xlabel("Tempo (s)")
            plt.ylabel("Frequência (Hz)")

            plt.xlim(0, t[-1])

            plt.savefig(caminho_tmp, dpi=200, bbox_inches="tight")
            plt.close()

            replace_com_incremento(caminho_tmp, caminho_saida)

        progresso = int((i / total) * 100)

        if progresso != ultimo_progresso:
            print(f"PROGRESS:{progresso}", flush=True)
            ultimo_progresso = progresso