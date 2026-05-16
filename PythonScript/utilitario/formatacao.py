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


def formata_tamanho(tamanho_bytes):
    if tamanho_bytes >= 1024 * 1024:
        tamanho_str = f"{tamanho_bytes / (1024 * 1024):.2f} MB"
    else:
        tamanho_str = f"{tamanho_bytes / 1024:.2f} KB"
    return tamanho_str.replace(".", ",")


def formata_bitrate(bitrate):
    if not bitrate: return ""

    if bitrate >= 1000:
        return f"{round(bitrate / 1000)} kbps"
    else:
        return f"{round(bitrate)} bps"


