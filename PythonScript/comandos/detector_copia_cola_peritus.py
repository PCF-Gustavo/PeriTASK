"""
Comando baseado no filtro de detecção de cópia/cola por PCA em blocos
POPESCU, A. C.; FARID, H. Exposing Digital Forgeries by Detecting Duplicated Image Regions, 2004
Implementação de referência: https://github.com/SEPAEL/Peritus
imagem em escala de cinza -> blocos sobrepostos -> PCA -> quantização/ordenação -> vetores de deslocamento repetidos -> morfologia -> regiões coloridas transparentes
"""

from __future__ import annotations

import math
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from utilitario.outros import (
    filtrar_arquivos,
    replace_com_incremento,
    selecionar_arquivos,
)

# ============================================================
# Metadados e saída
# ============================================================

PREFIXO_SAIDA = "copy_paste_"
EXTENSAO_SAIDA = "png"

# ============================================================
# Parâmetros da UI
# ============================================================

NCOMP_PADRAO = 0.75
QUANTIZACAO_PADRAO = 256

# ============================================================
# Constantes internas
# ============================================================

BLOCO_REFERENCIA = 7
NN_REFERENCIA = 2
NF_REFERENCIA = 128
ND_REFERENCIA = 16
ALPHA_CLUSTER = 0.42
CORES_CLUSTERS_BGR = [
    (0, 0, 255),
    (255, 0, 0),
    (0, 255, 0),
    (0, 255, 255),
    (255, 0, 255),
    (255, 255, 0),
    (0, 128, 255),
    (128, 0, 255),
]


# ============================================================
# Comunicação e controles PeriTASK
# ============================================================

def _status(msg: str) -> None:
    print(f"STATUS:{msg}", flush=True)


def _status_etapa(etapa: int, total: int, mensagem: str) -> None:
    _status(f"Etapa {etapa}/{total} - {mensagem}")


def _progress(valor: int) -> None:
    valor = max(0, min(100, int(valor)))
    print(f"PROGRESS:{valor}", flush=True)


def _get_float(
    controls: Dict[str, Any],
    chave: str,
    padrao: float,
    minimo: float,
    maximo: float,
) -> float:
    try:
        valor = float(str(controls.get(chave, padrao)).replace(",", ".").strip())
    except Exception:
        valor = padrao

    return max(minimo, min(maximo, valor))


def _get_int(
    controls: Dict[str, Any],
    chave: str,
    padrao: int,
    minimo: int,
    maximo: int,
) -> int:
    try:
        valor = int(float(str(controls.get(chave, padrao)).replace(",", ".").strip()))
    except Exception:
        valor = padrao

    return max(minimo, min(maximo, valor))


# ============================================================
# Estimadores automáticos
# ============================================================

def estima_bloco_pca(largura: int, altura: int) -> int:
    """
    Estima o tamanho do bloco b.

    Critério sensível:
        - blocos menores detectam cópias menores;
        - blocos menores aumentam custo e falsos positivos;
        - como a preferência é evitar falsos negativos, mantém b baixo.
    """
    maior_lado = max(largura, altura)

    if maior_lado <= 2600:
        return 7

    if maior_lado <= 4200:
        return 9

    return 11


def estima_nn_pca(largura: int, altura: int, b: int) -> int:
    """
    Estima a profundidade de pesquisa Nn.

    Critério sensível:
        - Nn maior compara mais vizinhos após ordenação;
        - aumenta chance de encontrar clones;
        - aumenta custo e falsos positivos.
    """
    linhas_blocos = altura - b + 1
    colunas_blocos = largura - b + 1

    if linhas_blocos <= 0 or colunas_blocos <= 0:
        return NN_REFERENCIA

    nb = linhas_blocos * colunas_blocos

    if nb <= 300_000:
        return 5

    if nb <= 900_000:
        return 4

    if nb <= 1_800_000:
        return 3

    return 2


def estima_nf_pca(largura: int, altura: int, b: int) -> int:
    """
    Estima Nf, tamanho mínimo do clone.

    Critério sensível:
        - Nf menor aceita regiões menores;
        - evita falsos negativos;
        - pode aumentar falsos positivos.
    """
    linhas_blocos = altura - b + 1
    colunas_blocos = largura - b + 1

    if linhas_blocos <= 0 or colunas_blocos <= 0:
        return NF_REFERENCIA

    nb = linhas_blocos * colunas_blocos

    estimado = int(round(nb * 0.00008))

    return max(32, min(128, estimado))


def estima_nd_pca(largura: int, altura: int) -> int:
    """
    Estima Nd, distância mínima de Manhattan entre blocos.

    Critério sensível:
        - Nd menor permite detectar deslocamentos mais próximos;
        - evita falsos negativos em cópias pequenas/próximas;
        - pode aumentar falsos positivos.
    """
    diagonal = math.hypot(largura, altura)

    estimado = int(round(diagonal * 0.008))

    return max(8, min(24, estimado))


def estima_parametros_pca(
    largura: int,
    altura: int,
) -> Dict[str, int]:
    """
    Estima os parâmetros automáticos do PCA por blocos.
    """
    b = estima_bloco_pca(
        largura=largura,
        altura=altura,
    )

    nn = estima_nn_pca(
        largura=largura,
        altura=altura,
        b=b,
    )

    nf = estima_nf_pca(
        largura=largura,
        altura=altura,
        b=b,
    )

    nd = estima_nd_pca(
        largura=largura,
        altura=altura,
    )

    return {
        "b": b,
        "Nn": nn,
        "Nf": nf,
        "Nd": nd,
    }


# ============================================================
# Indexação e blocos
# ============================================================

def _linha_coluna_para_indice(
    linha: int,
    coluna: int,
    linhas_blocos: int,
) -> int:
    """
    Índice linear usado pelo C++:
        indice = coluna * linhas_blocos + linha
    """
    return int(coluna * linhas_blocos + linha)


def _distancia_cpp(
    maior: float,
    menor: float,
    linhas_blocos: int,
) -> int:
    """
    Reproduz a fórmula de distância usada no C++.
    """
    lb = float(linhas_blocos)

    distancia = int(
        abs(
            maior
            - menor
            + math.floor(menor / lb) * lb
            - math.floor(maior / lb) * lb
        )
    )

    distancia += int(
        math.floor(maior / lb)
        - math.floor(menor / lb)
    )

    return int(distancia)


def _linha_interna_cpp(
    valor: float,
    linhas_blocos: int,
) -> float:
    """
    Equivale a:
        valor - floor(valor/(linhas-b+1))*(linhas-b+1)
    """
    lb = float(linhas_blocos)
    return valor - math.floor(valor / lb) * lb


# ============================================================
# Extração de blocos
# ============================================================

def _extrair_blocos_vetorizados_cpp(
    gray: np.ndarray,
    b: int,
) -> Tuple[np.ndarray, int, int]:
    """
    Extrai blocos no mesmo layout do C++.

    C++:
        pDados[(j*(linhas-b+1)+i)*b2 + h*b + k]
            = pImagem[(i+k)*colunas + j+h]

    Portanto:
        índice do bloco = coluna * linhas_blocos + linha
        índice interno  = coluna_interna * b + linha_interna
    """
    linhas, colunas = gray.shape[:2]

    linhas_blocos = linhas - b + 1
    colunas_blocos = colunas - b + 1

    if linhas_blocos <= 0 or colunas_blocos <= 0:
        raise RuntimeError("Imagem menor que o tamanho do bloco informado.")

    nb = linhas_blocos * colunas_blocos
    b2 = b * b

    try:
        blocos = np.lib.stride_tricks.sliding_window_view(
            gray,
            (b, b),
        )

        # sliding_window_view:
        #   [linha_bloco, coluna_bloco, linha_interna, coluna_interna]
        #
        # C++:
        #   [coluna_bloco, linha_bloco, coluna_interna, linha_interna]
        blocos = blocos.transpose(1, 0, 3, 2)

        dados = blocos.reshape(
            nb,
            b2,
        )

        dados = np.ascontiguousarray(
            dados,
            dtype=np.float32,
        )

        return dados, linhas_blocos, colunas_blocos

    except Exception:
        dados = np.zeros(
            (nb, b2),
            dtype=np.float32,
        )

        for i in range(linhas_blocos):
            for j in range(colunas_blocos):
                indice_bloco = _linha_coluna_para_indice(
                    linha=i,
                    coluna=j,
                    linhas_blocos=linhas_blocos,
                )

                for k in range(b):
                    for h in range(b):
                        indice_interno = h * b + k
                        dados[indice_bloco, indice_interno] = gray[i + k, j + h]

        return dados, linhas_blocos, colunas_blocos


# ============================================================
# PCA, quantização e ordenação
# ============================================================

def _calcular_pca_cpp(
    dados: np.ndarray,
    n_comp: float,
) -> Tuple[np.ndarray, int]:
    """
    Equivalente a:
        cv::PCA data_pca(dados, cv::Mat(), DATA_AS_ROW, Nt)
        data_pca.project(...)
    """
    _nb, dimensoes = dados.shape

    nt = int(round(dimensoes * n_comp))
    nt = max(1, min(dimensoes, nt))

    media, autovetores, _autovalores = cv2.PCACompute2(
        dados,
        mean=None,
        maxComponents=nt,
    )

    g = cv2.PCAProject(
        dados,
        media,
        autovetores,
    )

    g = np.ascontiguousarray(
        g,
        dtype=np.float32,
    )

    return g, nt


def _calcular_chave_b_cpp(
    g: np.ndarray,
    q: int,
) -> np.ndarray:
    """
    Reproduz a criação do vetor B no C++.

    C++:
        cv::minMaxLoc(G, &minimoG, &maximoG);
        maximoG = floor(maximoG / Q);

        pB[i] += pow(maximoG + 1, j) * floor(pG[i*Nt+j] / Q);
    """
    q = max(1, int(q))

    nb, nt = g.shape

    maximo_g = float(np.max(g))
    maximo_g = math.floor(maximo_g / float(q))

    base = float(maximo_g + 1.0)

    b_chave = np.zeros(
        nb,
        dtype=np.float64,
    )

    fator = 1.0

    for j in range(nt):
        b_chave += fator * np.floor(
            g[:, j].astype(np.float64) / float(q)
        )

        fator *= base

        if not np.isfinite(fator):
            break

    return b_chave


def _ordenar_indices_por_b_cpp(
    b_chave: np.ndarray,
) -> np.ndarray:
    """
    Equivalente aproximado ao:
        std::sort(pIND, pIND+Nb, ... return pB[i1] < pB[i2])
    """
    indices = np.argsort(
        b_chave,
        kind="quicksort",
    )

    return indices.astype(np.int64)


# ============================================================
# Deslocamentos e seleção de clones
# ============================================================

def _calcular_md_dir_deslocamentos_cpp(
    indices_ordenados: np.ndarray,
    linhas: int,
    colunas: int,
    linhas_blocos: int,
    nb: int,
    nn: int,
    nf: int,
    nd: int,
) -> Tuple[np.ndarray, np.ndarray, List[int]]:
    """
    Reproduz a etapa C++ que calcula:
        MD
        Dir
        contador
        p_desloc

    p_desloc mantém deslocamentos repetidos, como no C++.
    """
    limite = nb - nn + 1

    md = np.zeros(
        (nn, limite),
        dtype=np.int64,
    )

    dir_mat = np.zeros(
        (max(1, nn - 1), limite),
        dtype=np.int8,
    )

    md[0, :] = indices_ordenados[:limite]

    tamanho_contador = 2 * (linhas * colunas - 1)

    contador = np.zeros(
        tamanho_contador,
        dtype=np.int32,
    )

    p_desloc: List[int] = []

    for i in range(1, nn):
        for j in range(limite):
            indice_base = int(md[0, j])
            indice_vizinho = int(indices_ordenados[j + i])

            if indice_vizinho > indice_base:
                maior = float(indice_vizinho)
                menor = float(indice_base)
                dir_mat[i - 1, j] = 0
            else:
                menor = float(indice_vizinho)
                maior = float(indice_base)
                dir_mat[i - 1, j] = 1

            distancia = _distancia_cpp(
                maior=maior,
                menor=menor,
                linhas_blocos=linhas_blocos,
            )

            linha_maior = _linha_interna_cpp(
                maior,
                linhas_blocos,
            )

            linha_menor = _linha_interna_cpp(
                menor,
                linhas_blocos,
            )

            if linha_maior < linha_menor:
                deslocamento = int(menor - maior)
                md[i, j] = deslocamento

                if distancia > nd:
                    aux = int(linhas * colunas - 1 + maior - menor)

                    if 0 <= aux < tamanho_contador:
                        contador[aux] += 1

                        if contador[aux] > nf:
                            if len(p_desloc) < 10000:
                                p_desloc.append(deslocamento)
            else:
                deslocamento = int(maior - menor)
                md[i, j] = deslocamento

                if distancia > nd:
                    aux = int(maior - menor)

                    if 0 <= aux < tamanho_contador:
                        contador[aux] += 1

                        if contador[aux] > nf:
                            if len(p_desloc) < 10000:
                                p_desloc.append(deslocamento)

    return md, dir_mat, p_desloc


# ============================================================
# Marcação de blocos clonados
# ============================================================

def _preparar_grupos_deslocamentos(
    md: np.ndarray,
    p_desloc_unicos: List[int],
    nn: int,
) -> Dict[int, List[Tuple[int, np.ndarray]]]:
    """
    Pré-agrupa os índices j por deslocamento.

    Em vez de procurar MD[i] == deslocamento para cada deslocamento
    separadamente, varre cada linha MD[i] apenas uma vez usando np.isin.

    Isso preserva a lógica:
        MD[i, j] == deslocamento
    mas reduz muito o custo da marcação.
    """
    grupos: Dict[int, List[Tuple[int, np.ndarray]]] = {
        int(deslocamento): []
        for deslocamento in p_desloc_unicos
    }

    if not p_desloc_unicos:
        return grupos

    deslocamentos_array = np.array(
        p_desloc_unicos,
        dtype=md.dtype,
    )

    for i in range(1, nn):
        linha_md = md[i]

        mascara_linha = np.isin(
            linha_md,
            deslocamentos_array,
        )

        js_todos = np.flatnonzero(mascara_linha)

        if js_todos.size == 0:
            continue

        deslocamentos_encontrados = linha_md[js_todos]
        unicos_linha = np.unique(deslocamentos_encontrados)

        for deslocamento in unicos_linha:
            js = js_todos[deslocamentos_encontrados == deslocamento]

            if js.size > 0:
                grupos[int(deslocamento)].append(
                    (
                        i,
                        js.astype(np.int64, copy=False),
                    )
                )

    return grupos


def _marcar_um_deslocamento_vetorizado(
    deslocamento: int,
    grupos_deslocamento: List[Tuple[int, np.ndarray]],
    shape_gray: Tuple[int, int],
    md: np.ndarray,
    dir_mat: np.ndarray,
    b: int,
    linhas_blocos: int,
) -> Tuple[int, np.ndarray]:
    """
    Marca os pontos correspondentes a um único deslocamento.

    Mantém a lógica original do C++:
        - usa MD[i, j] == deslocamento;
        - calcula duas posições usando Dir;
        - marca apenas canto superior esquerdo e canto inferior direito.
    """
    linhas, colunas = shape_gray[:2]

    mascara = np.zeros(
        (linhas, colunas),
        dtype=np.uint8,
    )

    deslocamento = int(deslocamento)
    deslocamento_abs = abs(deslocamento)

    limite_linha = linhas - b + 1
    limite_coluna = colunas - b + 1

    for i, js in grupos_deslocamento:
        if js.size == 0:
            continue

        bases = md[0, js].astype(np.int64, copy=False)
        direcoes = dir_mat[i - 1, js].astype(np.int64, copy=False)

        # Primeiro sentido:
        # valor_1 = MD[j] - Dir * abs(p_desloc[k])
        valores_1 = bases - direcoes * deslocamento_abs

        jj_1 = valores_1 // linhas_blocos
        ii_1 = valores_1 - jj_1 * linhas_blocos

        validos_1 = (
            (ii_1 >= 0)
            & (jj_1 >= 0)
            & (ii_1 < limite_linha)
            & (jj_1 < limite_coluna)
        )

        if np.any(validos_1):
            ii = ii_1[validos_1].astype(np.int64, copy=False)
            jj = jj_1[validos_1].astype(np.int64, copy=False)

            mascara[ii, jj] = 255
            mascara[ii + b - 1, jj + b - 1] = 255

        # Segundo sentido:
        # valor_2 = MD[j] + (1 - Dir) * abs(p_desloc[k])
        valores_2 = bases + (1 - direcoes) * deslocamento_abs

        jj_2 = valores_2 // linhas_blocos
        ii_2 = valores_2 - jj_2 * linhas_blocos

        validos_2 = (
            (ii_2 >= 0)
            & (jj_2 >= 0)
            & (ii_2 < limite_linha)
            & (jj_2 < limite_coluna)
        )

        if np.any(validos_2):
            ii = ii_2[validos_2].astype(np.int64, copy=False)
            jj = jj_2[validos_2].astype(np.int64, copy=False)

            mascara[ii, jj] = 255
            mascara[ii + b - 1, jj + b - 1] = 255

    return deslocamento, mascara


def _marcar_cantos_blocos_cpp_otimizado(
    shape_gray: Tuple[int, int],
    md: np.ndarray,
    dir_mat: np.ndarray,
    p_desloc: List[int],
    b: int,
    nn: int,
    linhas_blocos: int,
    max_workers: int | None = None,
) -> Tuple[Dict[int, np.ndarray], int]:
    """
    Versão otimizada da marcação dos cantos dos blocos.

    Otimizações:
        - usa deslocamentos únicos na marcação;
        - pré-agrupa índices j por deslocamento usando NumPy;
        - paraleliza por deslocamento usando threads.

    Retorna:
        mascaras_por_deslocamento
        quantidade_de_deslocamentos_unicos_usados
    """
    if not p_desloc:
        return {}, 0

    # Preserva a ordem da primeira aparição.
    p_desloc_unicos = list(dict.fromkeys(int(x) for x in p_desloc))

    grupos = _preparar_grupos_deslocamentos(
        md=md,
        p_desloc_unicos=p_desloc_unicos,
        nn=nn,
    )

    if max_workers is None:
        max_workers = os.cpu_count() or 1

    max_workers = max(1, int(max_workers))

    resultados: Dict[int, np.ndarray] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {
            executor.submit(
                _marcar_um_deslocamento_vetorizado,
                deslocamento,
                grupos.get(deslocamento, []),
                shape_gray,
                md,
                dir_mat,
                b,
                linhas_blocos,
            ): deslocamento
            for deslocamento in p_desloc_unicos
            if grupos.get(deslocamento)
        }

        for futuro in as_completed(futuros):
            deslocamento, mascara = futuro.result()

            if np.count_nonzero(mascara) > 0:
                resultados[int(deslocamento)] = mascara

    # Recria o dicionário na ordem original dos deslocamentos únicos,
    # evitando cor não determinística por causa do as_completed.
    mascaras_por_deslocamento: Dict[int, np.ndarray] = {}

    for deslocamento in p_desloc_unicos:
        if deslocamento in resultados:
            mascaras_por_deslocamento[deslocamento] = resultados[deslocamento]

    return mascaras_por_deslocamento, len(p_desloc_unicos)


# ============================================================
# Morfologia
# ============================================================

def _aplicar_morfologia_mascaras_cpp(
    mascaras_por_deslocamento: Dict[int, np.ndarray],
    b: int,
) -> Dict[int, np.ndarray]:
    """
    Aplica a morfologia original às máscaras por deslocamento:

        morph_size = floor(b/2)
        MORPH_ELLIPSE
        MORPH_CLOSE
        MORPH_OPEN

    Nesta versão, a morfologia é sempre aplicada.
    """
    if not mascaras_por_deslocamento:
        return mascaras_por_deslocamento

    morph_size = int(math.floor(b / 2))

    element = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (
            2 * morph_size + 1,
            2 * morph_size + 1,
        ),
        (
            morph_size,
            morph_size,
        ),
    )

    saida: Dict[int, np.ndarray] = {}

    for deslocamento, mascara in mascaras_por_deslocamento.items():
        resultado = cv2.morphologyEx(
            mascara,
            cv2.MORPH_CLOSE,
            element,
        )

        resultado = cv2.morphologyEx(
            resultado,
            cv2.MORPH_OPEN,
            element,
        )

        if np.count_nonzero(resultado) > 0:
            saida[deslocamento] = resultado

    return saida


# ============================================================
# Visualização
# ============================================================

def _desenhar_overlay_por_deslocamento(
    imagem_bgr: np.ndarray,
    mascaras_por_deslocamento: Dict[int, np.ndarray],
) -> np.ndarray:
    """
    Overlay colorido transparente sobre a imagem original.

    Cada deslocamento único recebe uma cor.
    """
    saida = imagem_bgr.copy()

    if not mascaras_por_deslocamento:
        return saida

    overlay = imagem_bgr.copy()

    deslocamentos = list(mascaras_por_deslocamento.keys())

    for idx, deslocamento in enumerate(deslocamentos):
        mascara = mascaras_por_deslocamento[deslocamento]

        if np.count_nonzero(mascara) == 0:
            continue

        cor = CORES_CLUSTERS_BGR[idx % len(CORES_CLUSTERS_BGR)]
        overlay[mascara > 0] = cor

    return cv2.addWeighted(
        overlay,
        ALPHA_CLUSTER,
        saida,
        1.0 - ALPHA_CLUSTER,
        0,
    )


def _criar_mascara_total(
    shape_gray: Tuple[int, int],
    mascaras_por_deslocamento: Dict[int, np.ndarray],
) -> np.ndarray:
    mascara_total = np.zeros(
        shape_gray,
        dtype=np.uint8,
    )

    for mascara in mascaras_por_deslocamento.values():
        mascara_total[mascara > 0] = 255

    return mascara_total


# ============================================================
# Pipeline
# ============================================================

def _copy_move_pca_original_otimizado(
    imagem_bgr: np.ndarray,
    controls: Dict[str, Any],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Implementação Python baseada na lógica original do CopyMovePCA,
    com estimadores automáticos e otimização na etapa de marcação.
    """
    altura, largura = imagem_bgr.shape[:2]

    _status_etapa(2, 15, "Estimando parâmetros automáticos e lendo controles da UI.")
    parametros_estimados = estima_parametros_pca(
        largura=largura,
        altura=altura,
    )

    b = parametros_estimados["b"]
    nn = parametros_estimados["Nn"]
    nf = parametros_estimados["Nf"]
    nd = parametros_estimados["Nd"]

    n_comp = _get_float(
        controls,
        "nComp",
        NCOMP_PADRAO,
        0.01,
        1.0,
    )

    q = _get_int(
        controls,
        "Q",
        QUANTIZACAO_PADRAO,
        1,
        100000,
    )

    if b >= altura or b >= largura:
        raise RuntimeError(
            f"Tamanho do bloco inválido para a imagem: b={b}, "
            f"imagem={largura}x{altura}."
        )

    _status_etapa(3, 15, "Convertendo imagem para escala de cinza.")
    gray = cv2.cvtColor(
        imagem_bgr,
        cv2.COLOR_BGR2GRAY,
    )

    _progress(8)
    _status_etapa(2, 15, 
        "Parâmetros estimados: "
        f"b={b}, Nn={nn}, Nf={nf}, Nd={nd}. "
        f"Parâmetros da UI: nComp={n_comp}, Q={q}."
    )

    _status_etapa(4, 15, "Extraindo blocos bxb na ordem original do C++.")

    dados, linhas_blocos, colunas_blocos = _extrair_blocos_vetorizados_cpp(
        gray=gray,
        b=b,
    )

    nb = int(dados.shape[0])

    _progress(20)
    _status_etapa(5, 15, 
        f"Blocos extraídos: Nb={nb}, "
        f"linhas_blocos={linhas_blocos}, "
        f"colunas_blocos={colunas_blocos}."
    )

    _status_etapa(6, 15, "Executando PCA.")

    g, nt = _calcular_pca_cpp(
        dados=dados,
        n_comp=n_comp,
    )

    del dados

    _progress(36)
    _status_etapa(6, 15, f"PCA concluída: componentes utilizados={nt}.")

    _status_etapa(7, 15, "Calculando chave B conforme lógica original.")

    b_chave = _calcular_chave_b_cpp(
        g=g,
        q=q,
    )

    del g

    _progress(45)
    _status_etapa(8, 15, "Ordenando índices por B.")

    indices_ordenados = _ordenar_indices_por_b_cpp(
        b_chave=b_chave,
    )

    del b_chave

    _progress(55)
    _status_etapa(9, 15, "Calculando MD, Dir, contador e p_desloc.")

    md, dir_mat, p_desloc = _calcular_md_dir_deslocamentos_cpp(
        indices_ordenados=indices_ordenados,
        linhas=altura,
        colunas=largura,
        linhas_blocos=linhas_blocos,
        nb=nb,
        nn=nn,
        nf=nf,
        nd=nd,
    )

    del indices_ordenados

    _progress(72)

    p_desloc_unicos_preview = len(list(dict.fromkeys(int(x) for x in p_desloc)))

    _status_etapa(10, 15, 
        f"p_desloc total={len(p_desloc)}; "
        f"deslocamentos únicos={p_desloc_unicos_preview}."
    )

    _status_etapa(11, 15, "Marcando cantos dos blocos clonados com NumPy/paralelismo.")

    mascaras_por_deslocamento, p_desloc_unicos = _marcar_cantos_blocos_cpp_otimizado(
        shape_gray=gray.shape,
        md=md,
        dir_mat=dir_mat,
        p_desloc=p_desloc,
        b=b,
        nn=nn,
        linhas_blocos=linhas_blocos,
    )

    _progress(82)

    _status_etapa(12, 15, "Aplicando morfologia elíptica original.")
    mascaras_por_deslocamento = _aplicar_morfologia_mascaras_cpp(
        mascaras_por_deslocamento=mascaras_por_deslocamento,
        b=b,
    )

    _progress(88)

    _status_etapa(13, 15, "Criando overlay colorido e máscara total.")
    resultado = _desenhar_overlay_por_deslocamento(
        imagem_bgr=imagem_bgr,
        mascaras_por_deslocamento=mascaras_por_deslocamento,
    )

    mascara_total = _criar_mascara_total(
        shape_gray=gray.shape,
        mascaras_por_deslocamento=mascaras_por_deslocamento,
    )

    pixels_mascara = int(np.count_nonzero(mascara_total))

    info = {
        "b": b,
        "nComp": n_comp,
        "Nn": nn,
        "Q": q,
        "Nf": nf,
        "Nd": nd,
        "morf": True,
        "Nb": nb,
        "linhas_blocos": linhas_blocos,
        "colunas_blocos": colunas_blocos,
        "componentes_pca": nt,
        "p_desloc": len(p_desloc),
        "p_desloc_unicos": p_desloc_unicos,
        "deslocamentos_com_mascara": len(mascaras_por_deslocamento),
        "pixels_mascara": pixels_mascara,
        "workers_marcacao": os.cpu_count() or 1,
    }

    return resultado, info


def _processar_imagem(
    caminho_imagem: str,
    pasta_saida: str,
    controls: Dict[str, Any],
) -> None:
    nome_base = Path(caminho_imagem).stem

    _status_etapa(1, 15, f"{Path(caminho_imagem).name}: lendo imagem de entrada.")
    imagem_bgr = cv2.imread(
        caminho_imagem,
        cv2.IMREAD_COLOR,
    )

    if imagem_bgr is None:
        raise RuntimeError("Imagem não pôde ser lida pelo OpenCV.")

    resultado, info = _copy_move_pca_original_otimizado(
        imagem_bgr=imagem_bgr,
        controls=controls,
    )

    tmp = os.path.join(
        os.getenv("TEMP") or pasta_saida,
        f"{PREFIXO_SAIDA}PCA_{nome_base}.tmp.{EXTENSAO_SAIDA}",
    )

    final = os.path.join(
        pasta_saida,
        f"{PREFIXO_SAIDA}PCA_{nome_base}.{EXTENSAO_SAIDA}",
    )

    _status_etapa(14, 15, f"{Path(caminho_imagem).name}: salvando imagem de resultado.")
    cv2.imwrite(
        tmp,
        resultado,
    )

    saida = replace_com_incremento(
        tmp,
        final,
    )

    _status_etapa(15, 15, 
        f"{Path(caminho_imagem).name}: "
        f"b={info['b']}, "
        f"nComp={info['nComp']}, "
        f"Nn={info['Nn']}, "
        f"Q={info['Q']}, "
        f"Nf={info['Nf']}, "
        f"Nd={info['Nd']}, "
        f"morf={info['morf']}, "
        f"Nb={info['Nb']}, "
        f"componentes_pca={info['componentes_pca']}, "
        f"p_desloc={info['p_desloc']}, "
        f"p_desloc_unicos={info['p_desloc_unicos']}, "
        f"deslocamentos_com_mascara={info['deslocamentos_com_mascara']}, "
        f"pixels_mascara={info['pixels_mascara']}, "
        f"workers_marcacao={info['workers_marcacao']} "
        f"-> {saida}"
    )


# ============================================================
# Entrada PeriTASK
# ============================================================

def executar(arquivos, controls, pasta_saida):
    """
    Função obrigatória para comandos do PeriTASK.

    Controls aceitos:
        nComp:
            percentual de componentes principais utilizadas.
            default: 0.75

        Q:
            fator de quantização dos vetores PCA.
            default: 256

    Parâmetros estimados automaticamente:
        b:
            tamanho do bloco bxb.

        Nn:
            profundidade da pesquisa após ordenação.

        Nf:
            tamanho mínimo do clone.

        Nd:
            distância mínima de Manhattan entre blocos.

    Morfologia:
        sempre aplicada.
    """
    if controls is None:
        controls = {}

    arquivos_imagens = selecionar_arquivos(
        arquivos,
        "imagem",
    )

    arquivos_imagens = filtrar_arquivos(
        arquivos_imagens,
        prefixo=PREFIXO_SAIDA,
        extensao=EXTENSAO_SAIDA,
    )

    if not arquivos_imagens:
        _status("Nenhuma imagem compatível foi selecionada.")
        _progress(100)
        return

    Path(pasta_saida).mkdir(
        parents=True,
        exist_ok=True,
    )

    total = len(arquivos_imagens)
    ultimo_progresso = -1

    _status(
        f"Iniciando detector Copy-Move PCA original otimizado em {total} imagem(ns)."
    )

    for i, imagem in enumerate(arquivos_imagens, start=1):
        try:
            _status(
                f"Processando imagem {i}/{total}: {Path(imagem).name}"
            )

            _processar_imagem(
                caminho_imagem=imagem,
                pasta_saida=pasta_saida,
                controls=controls,
            )

        except Exception as exc:
            _status(
                f"Erro ao processar {Path(imagem).name}: {exc}"
            )
            _status(traceback.format_exc())

        progresso = int((i / total) * 100)

        if progresso != ultimo_progresso:
            _progress(progresso)
            ultimo_progresso = progresso

    _progress(100)


# ============================================================
# Execução direta
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Detector Copy-Move PCA por blocos - lógica original C++ otimizada"
    )

    parser.add_argument(
        "imagens",
        nargs="+",
        help="Imagem(ns) de entrada",
    )

    parser.add_argument(
        "--saida",
        default=".",
        help="Pasta de saída",
    )

    parser.add_argument(
        "--nComp",
        default=str(NCOMP_PADRAO),
        help="Percentual de componentes PCA. Default: 0.75",
    )

    parser.add_argument(
        "--Q",
        default=str(QUANTIZACAO_PADRAO),
        help="Fator de quantização. Default: 256",
    )

    args = parser.parse_args()

    executar(
        arquivos=args.imagens,
        controls={
            "nComp": args.nComp,
            "Q": args.Q,
        },
        pasta_saida=args.saida,
    )
