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


EXTENSOES_POR_TIPO = {
    "video": {
        ".avi", ".mp4", ".mkv", ".mov", ".wmv", ".flv",
        ".mpeg", ".mpg", ".webm", ".dav", ".m4v",
        ".3gp", ".ts", ".vob"
    },
    "audio": {
        ".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg",
        ".wma", ".opus", ".amr", ".aiff", ".aif", ".mka",
        ".ac3"
    },
    "imagem": {
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif",
        ".tiff", ".webp", ".heic", ".heif"
    }
}
from pathlib import Path


EXTENSOES = {
    "video": {
        ".avi", ".mp4", ".mkv", ".mov", ".wmv", ".flv",
        ".mpeg", ".mpg", ".webm", ".dav", ".m4v",
        ".3gp", ".ts", ".vob"
    },
    "video_mp4": {
        ".mp4",  ".mov", ".m4v", ".3gp"
    },
    "audio": {
        ".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg",
        ".wma", ".opus", ".amr", ".aiff", ".aif", ".ac3"
    },
    "imagem": {
        ".jpg", ".jpeg", ".png", ".bmp", ".gif",
        ".tif", ".tiff", ".webp", ".heic", ".heif"
    },
    "imagem_png": {
        ".png"
    }
}


def selecionar_arquivos(arquivos, tipos):
    if isinstance(tipos, str):
        tipos = [tipos]
    extensoes = set().union(*(EXTENSOES.get(tipo.lower(), set()) for tipo in tipos))
    return [arq for arq in arquivos if Path(arq).suffix.lower() in extensoes]

def filtrar_arquivos(
    arquivos,
    prefixo=None,
    sufixo=None,
    extensao=None
):
    """
    Remove arquivos que satisfaçam TODOS os filtros informados.

    Os parâmetros são opcionais:
    - prefixo: início do nome do arquivo
    - sufixo: final do nome do arquivo (sem extensão)
    - extensao: extensão do arquivo

    Exemplos:
    prefixo="tmp_"
    sufixo="_editada"
    extensao=".jpg"
    """

    if extensao:
        extensao = extensao.lower()
        if not extensao.startswith("."):
            extensao = "." + extensao

    resultado = []

    for arq in arquivos:
        path = Path(arq)

        nome = path.stem.lower()
        ext = path.suffix.lower()

        filtros = []

        if prefixo is not None:
            filtros.append(nome.startswith(prefixo.lower()))

        if sufixo is not None:
            filtros.append(nome.endswith(sufixo.lower()))

        if extensao is not None:
            filtros.append(ext == extensao)

        # Remove somente se TODOS os filtros forem satisfeitos
        if filtros and all(filtros):
            continue

        resultado.append(arq)

    return resultado