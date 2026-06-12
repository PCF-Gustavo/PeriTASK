import os
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

from utilitario.outros import replace_com_incremento, selecionar_arquivos

# ============================================================
# Configuração geral
# ============================================================

PNG_JSON_KEY = "peritask_mp4_atoms_tree_json"
PNG_SCHEMA = "peritask_mp4_atoms_tree_v1"


# Boxes/atoms que normalmente podem conter outros boxes diretamente.
CONTAINER_BOXES = {
    "moov", "trak", "mdia", "minf", "dinf", "stbl", "edts",
    "udta", "ilst", "moof", "traf", "mfra", "skip",
    "tref", "ipro", "sinf", "schi", "mvex", "clip",
    "matt", "rmra", "gmhd", "wave", "strk", "strd",
}


# Sample entries dentro de stsd podem conter boxes filhos após campos próprios.
SAMPLE_ENTRY_BOXES = {
    # Vídeo
    "avc1", "avc2", "avc3", "avc4", "hvc1", "hev1", "encv",
    "mp4v", "jpeg", "png ", "apcn", "apch", "apcs", "apco",

    # Áudio
    "mp4a", "enca", "alac", "ac-3", "ec-3", "Opus",

    # Legendas/texto
    "tx3g", "text", "wvtt", "stpp",
}


# Boxes do tipo FullBox: possuem version + flags antes dos filhos.
FULLBOX_CONTAINERS_COM_FILHOS = {
    "stsd": 8,  # version/flags + entry_count
    "dref": 8,  # version/flags + entry_count
}


# Algumas caixas UUID podem conter dados arbitrários; por padrão não descendemos nelas.
DESCER_EM_UUID = False


# ============================================================
# Estruturas
# ============================================================

def criar_no(tipo, offset, tamanho, header_size, uuid=None):
    return {
        "type": tipo,
        "offset": offset,
        "size": tamanho,
        "header_size": header_size,
        "end": offset + tamanho if tamanho is not None else None,
        "uuid": uuid,
        "children": [],
    }


# ============================================================
# Leitura dos boxes/atoms
# ============================================================

def ler_header_box(f, limite_fim):
    """
    Lê cabeçalho ISO BMFF/MP4:
    - size 32-bit + type 4 bytes;
    - se size == 1, usa largesize 64-bit;
    - se type == uuid, lê 16 bytes de UUID.
    """
    offset = f.tell()

    if limite_fim is not None and offset + 8 > limite_fim:
        return None

    header = f.read(8)
    if len(header) < 8:
        return None

    size32, tipo_bytes = struct.unpack(">I4s", header)

    try:
        tipo = tipo_bytes.decode("ascii", errors="replace")
    except Exception:
        tipo = repr(tipo_bytes)

    header_size = 8
    uuid = None

    if size32 == 1:
        largesize_bytes = f.read(8)
        if len(largesize_bytes) < 8:
            return None

        tamanho = struct.unpack(">Q", largesize_bytes)[0]
        header_size += 8

    elif size32 == 0:
        # Box vai até o fim do arquivo ou até o limite informado.
        if limite_fim is None:
            atual = f.tell()
            f.seek(0, os.SEEK_END)
            fim_arquivo = f.tell()
            f.seek(atual)
            tamanho = fim_arquivo - offset
        else:
            tamanho = limite_fim - offset

    else:
        tamanho = size32

    if tipo == "uuid":
        uuid_bytes = f.read(16)
        if len(uuid_bytes) < 16:
            return None

        uuid = uuid_bytes.hex()
        header_size += 16

    if tamanho < header_size:
        return None

    if limite_fim is not None and offset + tamanho > limite_fim:
        # Arquivo truncado/corrompido ou box declarando tamanho além do pai.
        tamanho = max(header_size, limite_fim - offset)

    return criar_no(tipo, offset, tamanho, header_size, uuid=uuid)


def offset_inicio_filhos(no, contexto_pai=None):
    """
    Define onde começam os filhos de um box.

    A maioria dos containers começa logo após o cabeçalho.
    Alguns FullBoxes possuem version/flags e campos adicionais.
    Sample entries dentro de stsd possuem cabeçalho próprio antes dos boxes filhos.
    """
    tipo = no["type"]
    inicio = no["offset"] + no["header_size"]

    if tipo in FULLBOX_CONTAINERS_COM_FILHOS:
        return inicio + FULLBOX_CONTAINERS_COM_FILHOS[tipo]

    if tipo in SAMPLE_ENTRY_BOXES and contexto_pai == "stsd":

        # VisualSampleEntry:
        # 6 reserved + 2 data_reference_index + vários campos até compressorname/depth.
        # Total após cabeçalho do box: 78 bytes para sample entry de vídeo.
        if tipo in {
            "avc1", "avc2", "avc3", "avc4",
            "hvc1", "hev1", "encv", "mp4v",
        }:
            return inicio + 78

        # AudioSampleEntry clássico:
        # 6 reserved + 2 data_reference_index + 8 reserved + 2 channelcount
        # + 2 samplesize + 4 pre_defined/reserved + 4 samplerate = 28 bytes.
        if tipo in {
            "mp4a", "enca", "alac", "ac-3", "ec-3", "Opus",
        }:
            return inicio + 28

        # Text/legenda variam. Tenta descer após 8 bytes básicos.
        return inicio + 8

    return inicio


def box_pode_ter_filhos(no, contexto_pai=None):
    tipo = no["type"]

    if tipo == "uuid":
        return DESCER_EM_UUID

    if tipo in CONTAINER_BOXES:
        return True

    if tipo in FULLBOX_CONTAINERS_COM_FILHOS:
        return True

    if contexto_pai == "stsd" and tipo in SAMPLE_ENTRY_BOXES:
        return True

    return False


def parse_boxes(f, inicio, fim, profundidade=0, max_profundidade=50, contexto_pai=None):
    """
    Parse recursivo de boxes MP4 sem carregar o arquivo inteiro em memória.
    Não entra em payloads grandes, como mdat.
    """
    filhos = []

    if profundidade > max_profundidade:
        return filhos

    f.seek(inicio)

    while f.tell() + 8 <= fim:
        pos_antes = f.tell()
        no = ler_header_box(f, fim)

        if no is None:
            break

        box_fim = no["offset"] + no["size"]

        if box_fim <= no["offset"]:
            break

        if box_pode_ter_filhos(no, contexto_pai=contexto_pai):
            filhos_inicio = offset_inicio_filhos(no, contexto_pai=contexto_pai)

            if filhos_inicio < box_fim:
                no["children"] = parse_boxes(
                    f,
                    filhos_inicio,
                    box_fim,
                    profundidade=profundidade + 1,
                    max_profundidade=max_profundidade,
                    contexto_pai=no["type"],
                )

        filhos.append(no)

        # Salta para o fim do box atual, sem ler payload.
        f.seek(box_fim)

        if f.tell() <= pos_antes:
            break

    return filhos


def parse_mp4_atoms(caminho_arquivo):
    caminho = Path(caminho_arquivo)
    tamanho = caminho.stat().st_size

    with open(caminho, "rb") as f:
        filhos = parse_boxes(f, 0, tamanho)

    return {
        "type": caminho.name,
        "offset": 0,
        "size": tamanho,
        "header_size": 0,
        "end": tamanho,
        "uuid": None,
        "children": filhos,
    }


# ============================================================
# Normalização para comparação futura
# ============================================================

def normalizar_arvore_para_comparacao(no, caminho_atual="", numero_atual=""):
    """
    Estrutura preparada para comparação futura.

    A imagem usa numeração local para reduzir poluição visual.
    O JSON embutido mantém:
    - número local mostrado na imagem;
    - número completo;
    - caminho por tipo;
    - offset;
    - tamanho;
    - uuid;
    - filhos.
    """
    contagem_tipos = {}
    filhos_normalizados = []

    for indice_local, filho in enumerate(no.get("children", []), start=1):
        tipo = filho["type"]

        contagem_tipos[tipo] = contagem_tipos.get(tipo, 0) + 1
        indice_tipo = contagem_tipos[tipo]

        numero_completo = (
            str(indice_local)
            if not numero_atual
            else f"{numero_atual}.{indice_local}"
        )

        caminho_tipo = (
            f"/{tipo}[{indice_tipo}]"
            if not caminho_atual
            else f"{caminho_atual}/{tipo}[{indice_tipo}]"
        )

        item = {
            "display_number": str(indice_local),
            "full_number": numero_completo,
            "path": caminho_tipo,
            "type": tipo,
            "index_same_type": indice_tipo,
            "offset": filho.get("offset"),
            "size": filho.get("size"),
            "uuid": filho.get("uuid"),
            "children": normalizar_arvore_para_comparacao(
                filho,
                caminho_tipo,
                numero_completo,
            ),
        }

        filhos_normalizados.append(item)

    return filhos_normalizados


def montar_estrutura_embutida(arquivo, raiz):
    """
    Monta o JSON que será armazenado dentro do PNG.
    """
    caminho = Path(arquivo)

    return {
        "schema": PNG_SCHEMA,
        "source_file_name": caminho.name,
        "source_file_size": caminho.stat().st_size,
        "tree": normalizar_arvore_para_comparacao(raiz),
    }


# ============================================================
# PNG metadata: inserir/extrair JSON
# ============================================================

def inserir_estrutura_json_no_png(caminho_png_entrada, caminho_png_saida, estrutura):
    """
    Insere a estrutura JSON nos metadados textuais do PNG.

    O JSON não aparece visualmente na imagem.
    A comparação futura poderá abrir o PNG e recuperar esse JSON.
    """
    texto_json = json.dumps(
        estrutura,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    pnginfo = PngInfo()
    pnginfo.add_text(PNG_JSON_KEY, texto_json)

    with Image.open(caminho_png_entrada) as img:
        img.save(caminho_png_saida, pnginfo=pnginfo)


def extrair_estrutura_json_do_png(caminho_png):
    """
    Recupera a estrutura JSON embutida no PNG.

    Esta função ainda não é usada pelo comando atual, mas já fica pronta
    para o futuro comando de comparação.
    """
    with Image.open(caminho_png) as img:
        texto_json = img.info.get(PNG_JSON_KEY)

    if not texto_json:
        return None

    return json.loads(texto_json)


# ============================================================
# Renderização em PNG
# ============================================================

def carregar_fonte(tamanho=16, mono=True):
    candidatos = []

    if mono:
        candidatos.extend([
            r"C:\Windows\Fonts\consola.ttf",
            r"C:\Windows\Fonts\cour.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ])

    candidatos.extend([
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ])

    for caminho in candidatos:
        if os.path.exists(caminho):
            return ImageFont.truetype(caminho, tamanho)

    return ImageFont.load_default()


def achatar_arvore_numerada(no, nivel=0, linhas=None, grau_hierarquia=0):
    """
    Transforma a árvore em linhas com numeração local.

    grau_hierarquia:
    - 0: abre tudo;
    - 1: mostra apenas o primeiro nível;
    - 2: mostra primeiro nível e um nível abaixo;
    - 3: mostra até dois níveis abaixo;
    - etc.

    Quando o atom tem filhos, mas eles não são exibidos pelo grau_hierarquia,
    a linha recebe recolhido=True para que a imagem exiba um sinal de +.
    """
    if linhas is None:
        linhas = []

    filhos = no.get("children", [])

    for indice_local, filho in enumerate(filhos, start=1):
        deve_abrir_filhos = (
            grau_hierarquia == 0
            or (nivel + 1) < grau_hierarquia
        )

        tem_filhos = bool(filho.get("children"))
        recolhido = tem_filhos and not deve_abrir_filhos

        linhas.append({
            "nivel": nivel,
            "numero": str(indice_local),
            "no": filho,
            "recolhido": recolhido,
        })

        if deve_abrir_filhos:
            achatar_arvore_numerada(
                filho,
                nivel=nivel + 1,
                linhas=linhas,
                grau_hierarquia=grau_hierarquia,
            )

    return linhas


def texto_atom(no):
    """
    Texto principal do atom.

    Retorna apenas o nome/tipo do atom para a imagem.
    O tamanho continua preservado no JSON embutido no PNG.
    """
    tipo = no["type"]

    if not tipo.strip():
        tipo = "[atom sem tipo textual]"

    if no.get("uuid"):
        tipo += f" uuid={no['uuid']}"

    return tipo


def calcular_dimensoes_texto(linhas, fonte, indent, largura_numero, largura_indicador):
    dummy = Image.new("RGB", (10, 10), "white")
    draw_dummy = ImageDraw.Draw(dummy)

    largura_max = 0

    for linha in linhas:
        nivel = linha["nivel"]
        texto = texto_atom(linha["no"])

        bbox = draw_dummy.textbbox((0, 0), texto, font=fonte)
        largura_texto = bbox[2] - bbox[0]

        largura_total = (
            nivel * indent
            + largura_numero
            + largura_indicador
            + largura_texto
        )

        largura_max = max(largura_max, largura_total)

    return largura_max


def renderizar_arvore_png(raiz, caminho_png, grau_hierarquia=0):
    """
    Renderiza PNG em hierarquia numerada, sem título, sem legenda,
    sem bullets, sem traços, sem caixas, sem conectores e sem tamanhos.

    Quando um atom tem filhos ocultos pelo grau_hierarquia, a imagem mostra
    um sinal de + antes do nome do atom.

    grau_hierarquia:
    - 0: abre tudo;
    - 1: mostra apenas o primeiro nível;
    - 2: mostra primeiro nível e um nível abaixo;
    - 3: mostra até dois níveis abaixo;
    - etc.
    """
    linhas = achatar_arvore_numerada(
        raiz,
        grau_hierarquia=grau_hierarquia,
    )

    fonte = carregar_fonte(tamanho=16, mono=True)

    # Margem única aplicada igualmente à esquerda, direita, topo e base.
    margem = 15
    altura_linha = 24

    # Recuo por nível hierárquico.
    indent = 38

    # Espaço fixo entre número, indicador e nome do atom.
    largura_numero = 34
    largura_indicador = 22

    largura_texto_max = calcular_dimensoes_texto(
        linhas,
        fonte,
        indent,
        largura_numero,
        largura_indicador,
    )

    largura = margem + largura_texto_max + margem
    altura = margem + max(1, len(linhas)) * altura_linha + margem

    img = Image.new("RGB", (largura, altura), "white")
    draw = ImageDraw.Draw(img)

    cor_numero = (110, 110, 110)
    cor_atom = (0, 0, 0)
    cor_indicador = (80, 80, 80)

    for i, linha in enumerate(linhas):
        nivel = linha["nivel"]
        numero = linha["numero"]
        no = linha["no"]
        recolhido = linha.get("recolhido", False)

        x_base = margem + nivel * indent
        y = margem + i * altura_linha

        texto = texto_atom(no)

        # Número local, discreto.
        draw.text(
            (x_base, y),
            numero,
            fill=cor_numero,
            font=fonte,
        )

        x_indicador = x_base + largura_numero
        x_atom = x_indicador + largura_indicador

        # Sinal de expansão/recolhimento apenas quando há filhos ocultos.
        if recolhido:
            draw.text(
                (x_indicador, y),
                "+",
                fill=cor_indicador,
                font=fonte,
            )

        # Nome do atom em preto.
        draw.text(
            (x_atom, y),
            texto,
            fill=cor_atom,
            font=fonte,
        )

    img.save(caminho_png)


# ============================================================
# Saída por arquivo
# ============================================================

def obter_grau_hierarquia(controls):
    valor = controls.get("grau_hierarquia", 0)

    try:
        grau = int(str(valor).strip())
    except Exception:
        grau = 0

    if grau < 0:
        grau = 0

    return grau


def processar_arquivo_mp4(arquivo, pasta_saida, grau_hierarquia=0):
    raiz = parse_mp4_atoms(arquivo)

    base = Path(arquivo).stem + "_" + Path(arquivo).suffix.lstrip(".")

    png_saida = os.path.join(
        pasta_saida,
        f"atoms_{base}.png",
    )

    png_tmp_sem_json = os.path.join(
        os.getenv("TEMP"),
        Path(png_saida).name + ".tmp.sem_json.png",
    )

    png_tmp_com_json = os.path.join(
        os.getenv("TEMP"),
        Path(png_saida).name + ".tmp.com_json.png",
    )

    renderizar_arvore_png(
        raiz,
        png_tmp_sem_json,
        grau_hierarquia=grau_hierarquia,
    )

    estrutura_embutida = montar_estrutura_embutida(
        arquivo,
        raiz,
    )

    inserir_estrutura_json_no_png(
        png_tmp_sem_json,
        png_tmp_com_json,
        estrutura_embutida,
    )

    png_final = replace_com_incremento(
        png_tmp_com_json,
        png_saida,
    )

    try:
        if os.path.exists(png_tmp_sem_json):
            os.remove(png_tmp_sem_json)
    except Exception:
        pass

    return {
        "arquivo": arquivo,
        "png": png_final,
    }


# ============================================================
# Entrada PeriTASK
# ============================================================

def executar(arquivos, controls, pasta_saida):
    """
    Entrada padrão do PeriTASK:
    executar(arquivos, controls, pasta_saida)
    """

    grau_hierarquia = obter_grau_hierarquia(controls)

    arquivos_video_mp4 = selecionar_arquivos(arquivos, "video_mp4")

    if not arquivos_video_mp4:
        print(
            "STATUS:Nenhum arquivo MP4/MOV/M4V compatível encontrado.",
            flush=True,
        )
        return

    total = len(arquivos_video_mp4)
    resultados = []

    for i, arquivo in enumerate(arquivos_video_mp4, start=1):
        nome = Path(arquivo).name

        try:
            resultado = processar_arquivo_mp4(
                arquivo,
                pasta_saida,
                grau_hierarquia=grau_hierarquia,
            )

            resultados.append(resultado)

        except Exception as exc:
            print(
                f"STATUS:Erro ao processar {nome}: {exc}",
                flush=True,
            )

        progresso = int(i / total * 100)
        print(f"PROGRESS:{progresso}", flush=True)
