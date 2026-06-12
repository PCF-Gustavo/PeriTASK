"""
Comando baseado na lógica do projeto https://github.com/cantugba/Copy_Move_Forgery_Detection
SIFT / AKAZE -> matching de descritores -> RANSAC -> regiões coloridas transparentes
"""

from __future__ import annotations

import math
import os
import traceback
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

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

LOWE_RATIO_PADRAO = 0.85
RANSAC_REPROJ_THRESHOLD_PADRAO = 5.0
KNN_K_PADRAO = 10

# ============================================================
# Constantes internas
# ============================================================

NORMAS = {
    "SIFT": cv2.NORM_L2 if cv2 is not None else None,
    "AKAZE": cv2.NORM_HAMMING if cv2 is not None else None,
}

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


def _get_float(controls: Dict[str, Any], chave: str, padrao: float, minimo: float, maximo: float) -> float:
    try:
        valor = float(str(controls.get(chave, padrao)).replace(",", ".").strip())
    except Exception:
        valor = padrao
    return max(minimo, min(maximo, valor))


def _get_int(controls: Dict[str, Any], chave: str, padrao: int, minimo: int, maximo: int) -> int:
    try:
        valor = int(float(str(controls.get(chave, padrao)).replace(",", ".").strip()))
    except Exception:
        valor = padrao
    return max(minimo, min(maximo, valor))


# ============================================================
# Estimadores automáticos
# ============================================================

def estima_distancia_minima_px(largura: int, altura: int) -> float:
    """
    Estima a distância mínima entre pontos casados.
    """
    diagonal = math.hypot(largura, altura)
    return max(12.0, min(60.0, diagonal * 0.015))


def estima_agrupamento_regiao_px(largura: int, altura: int, quantidade_keypoints: int) -> float:
    """
    Estima a distância para unir pontos próximos em uma mesma região local.
    """
    diagonal = math.hypot(largura, altura)
    base = diagonal * 0.014

    if quantidade_keypoints > 3000:
        base *= 0.85
    elif quantidade_keypoints < 800:
        base *= 1.15

    return max(16.0, min(45.0, base))


def estima_raio_ponto_cluster(largura: int, altura: int) -> int:
    """
    Estima o raio visual dos pontos coloridos.
    """
    diagonal = math.hypot(largura, altura)
    return int(round(max(6.0, min(18.0, diagonal * 0.0075))))


def estima_min_pontos_por_regiao(quantidade_keypoints: int, total_inliers: int) -> int:
    """
    Estima o mínimo de pontos para uma região local existir.
    """
    if quantidade_keypoints > 3500 and total_inliers > 120:
        return 3
    return 2


def estima_min_pontos_por_familia(total_inliers: int) -> int:
    """
    Estima o mínimo de pontos para uma família ser desenhada.
    """
    if total_inliers < 20:
        return 3
    if total_inliers < 80:
        return 4
    return 6


def estima_max_candidatos_por_keypoint(quantidade_keypoints: int) -> int:
    """
    Estima quantos candidatos do KNN serão avaliados por keypoint.
    """
    if quantidade_keypoints < 800:
        return 6
    if quantidade_keypoints < 1800:
        return 5
    return 4


# ============================================================
# Estruturas auxiliares
# ============================================================

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)

        if ra == rb:
            return

        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


# ============================================================
# Detectores e descritores
# ============================================================

def _criar_detector(nome: str):
    nome = nome.upper().strip()

    if nome == "SIFT":
        if not hasattr(cv2, "SIFT_create"):
            raise RuntimeError(
                "SIFT indisponível. Instale uma versão atual de opencv-python."
            )
        return cv2.SIFT_create()

    if nome == "AKAZE":
        if not hasattr(cv2, "AKAZE_create"):
            raise RuntimeError(
                "AKAZE indisponível. Instale uma versão atual de opencv-python."
            )
        return cv2.AKAZE_create()

    raise ValueError(f"Detector não suportado: {nome}")


def _obter_detectores(controls: Dict[str, Any]) -> List[str]:
    """
    Lê o detector escolhido pela UI.
    Opções aceitas:
        AKAZE
        SIFT
        AKAZE e SIFT
    """
    valor = str(controls.get("detectores", "AKAZE")).upper().strip()

    if valor == "AKAZE E SIFT":
        return ["AKAZE", "SIFT"]

    detectores = [
        item.strip()
        for item in valor.replace(";", ",").split(",")
        if item.strip()
    ]

    detectores = [
        item for item in detectores
        if item in {"SIFT", "AKAZE"}
    ]

    if not detectores:
        detectores = ["AKAZE"]

    return detectores


# ============================================================
# Matching e filtragem geométrica
# ============================================================

def _matching_interno(
    keypoints,
    descriptors,
    norma: int,
    lowe_ratio: float,
    distancia_minima_px: float,
    knn_k: int,
    max_candidatos_por_keypoint: int,
) -> List[Any]:
    """
    Matching dos descritores da imagem contra ela mesma.
    """
    if descriptors is None or len(descriptors) < 4:
        return []

    matcher = cv2.BFMatcher(norma, crossCheck=False)

    try:
        knn = matcher.knnMatch(descriptors, descriptors, k=knn_k)
    except Exception:
        return []

    bons_matches = []
    pares_vistos = set()

    for candidatos in knn:
        candidatos_validos = [
            m for m in candidatos
            if m.queryIdx != m.trainIdx
        ]

        if len(candidatos_validos) < 2:
            continue

        limite = min(max_candidatos_por_keypoint, len(candidatos_validos) - 1)

        for idx in range(limite):
            m = candidatos_validos[idx]
            n = candidatos_validos[idx + 1]

            if m.distance >= lowe_ratio * n.distance:
                continue

            p1 = keypoints[m.queryIdx].pt
            p2 = keypoints[m.trainIdx].pt

            distancia = math.hypot(
                p1[0] - p2[0],
                p1[1] - p2[1],
            )

            if distancia < distancia_minima_px:
                continue

            par = tuple(sorted((m.queryIdx, m.trainIdx)))

            if par in pares_vistos:
                continue

            pares_vistos.add(par)
            bons_matches.append(m)

    return bons_matches


def _filtrar_por_ransac(
    keypoints,
    matches: Sequence[Any],
    ransac_reproj_threshold: float,
) -> List[Any]:
    """
    Remove matches errados usando RANSAC.
    """
    if len(matches) < 4:
        return []

    pts1 = np.float32(
        [keypoints[m.queryIdx].pt for m in matches]
    ).reshape(-1, 1, 2)

    pts2 = np.float32(
        [keypoints[m.trainIdx].pt for m in matches]
    ).reshape(-1, 1, 2)

    try:
        _H, mask = cv2.findHomography(
            pts1,
            pts2,
            cv2.RANSAC,
            ransac_reproj_threshold,
        )
    except Exception:
        return []

    if mask is None:
        return []

    mask = mask.ravel().astype(bool)

    return [
        m for m, ok in zip(matches, mask)
        if ok
    ]


# ============================================================
# Agrupamento de regiões
# ============================================================

def _ponto_int(pt) -> tuple[int, int]:
    return int(round(pt[0])), int(round(pt[1]))


def _distancia_pontos(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _criar_familias_de_regioes(
    keypoints,
    inliers: Sequence[Any],
    agrupamento_regiao_px: float,
    min_pontos_por_regiao: int,
    min_pontos_por_familia: int,
):
    """
    Cria famílias de regiões relacionadas.
    """
    if not inliers:
        return []

    pontos = []
    pares_indices = []

    for m in inliers:
        p1 = keypoints[m.queryIdx].pt
        p2 = keypoints[m.trainIdx].pt

        idx1 = len(pontos)
        pontos.append((float(p1[0]), float(p1[1])))

        idx2 = len(pontos)
        pontos.append((float(p2[0]), float(p2[1])))

        pares_indices.append((idx1, idx2))

    if not pontos:
        return []

    # --------------------------------------------------------
    # 1. Agrupa pontos próximos em regiões locais
    # --------------------------------------------------------
    uf_pontos = UnionFind(len(pontos))
    limite = float(agrupamento_regiao_px)

    for i in range(len(pontos)):
        for j in range(i + 1, len(pontos)):
            if _distancia_pontos(pontos[i], pontos[j]) <= limite:
                uf_pontos.union(i, j)

    regioes_temp: Dict[int, List[int]] = {}

    for idx in range(len(pontos)):
        raiz = uf_pontos.find(idx)
        regioes_temp.setdefault(raiz, []).append(idx)

    regioes = []
    ponto_para_regiao = {}

    for indices in regioes_temp.values():
        if len(indices) < min_pontos_por_regiao:
            continue

        id_regiao = len(regioes)
        regioes.append(indices)

        for idx in indices:
            ponto_para_regiao[idx] = id_regiao

    if not regioes:
        return []

    # --------------------------------------------------------
    # 2. Conecta regiões por matches
    # --------------------------------------------------------
    uf_regioes = UnionFind(len(regioes))

    for idx1, idx2 in pares_indices:
        r1 = ponto_para_regiao.get(idx1)
        r2 = ponto_para_regiao.get(idx2)

        if r1 is None or r2 is None:
            continue

        if r1 == r2:
            continue

        uf_regioes.union(r1, r2)

    familias_temp: Dict[int, List[int]] = {}

    for id_regiao in range(len(regioes)):
        raiz = uf_regioes.find(id_regiao)
        familias_temp.setdefault(raiz, []).append(id_regiao)

    familias = []

    for ids_regioes in familias_temp.values():
        pontos_familia = []

        for id_regiao in ids_regioes:
            for idx_ponto in regioes[id_regiao]:
                pontos_familia.append(pontos[idx_ponto])

        if len(pontos_familia) < min_pontos_por_familia:
            continue

        familias.append(pontos_familia)

    familias.sort(key=len, reverse=True)

    return familias


# ============================================================
# Visualização
# ============================================================

def _desenhar_clusters_resultado(
    imagem_bgr,
    keypoints,
    inliers: Sequence[Any],
    agrupamento_regiao_px: float,
    min_pontos_por_regiao: int,
    min_pontos_por_familia: int,
    raio_ponto_cluster: int,
):
    """
    Desenha regiões conectadas por matches usando cores transparentes.
    """
    saida = imagem_bgr.copy()
    overlay = imagem_bgr.copy()

    familias = _criar_familias_de_regioes(
        keypoints=keypoints,
        inliers=inliers,
        agrupamento_regiao_px=agrupamento_regiao_px,
        min_pontos_por_regiao=min_pontos_por_regiao,
        min_pontos_por_familia=min_pontos_por_familia,
    )

    if not familias:
        return saida

    for idx_familia, pontos_familia in enumerate(familias):
        cor = CORES_CLUSTERS_BGR[idx_familia % len(CORES_CLUSTERS_BGR)]

        for ponto in pontos_familia:
            p = _ponto_int(ponto)

            cv2.circle(
                overlay,
                p,
                raio_ponto_cluster,
                cor,
                -1,
                cv2.LINE_AA,
            )

    return cv2.addWeighted(
        overlay,
        ALPHA_CLUSTER,
        saida,
        1.0 - ALPHA_CLUSTER,
        0,
    )


# ============================================================
# Pipeline
# ============================================================

def _processar_detector(
    imagem_bgr,
    gray,
    detector_nome: str,
    controls: Dict[str, Any],
):
    detector = _criar_detector(detector_nome)
    _status_etapa(4, 11, f"{detector_nome}: extraindo keypoints e descritores.")
    keypoints, descriptors = detector.detectAndCompute(gray, None)

    if keypoints is None:
        keypoints = []

    altura, largura = imagem_bgr.shape[:2]
    quantidade_keypoints = len(keypoints)

    _status_etapa(5, 11, f"{detector_nome}: estimando parâmetros automáticos e lendo controles da UI.")
    distancia_minima_px = estima_distancia_minima_px(largura, altura)
    agrupamento_regiao_px = estima_agrupamento_regiao_px(
        largura,
        altura,
        quantidade_keypoints,
    )
    raio_ponto_cluster = estima_raio_ponto_cluster(largura, altura)

    lowe_ratio = _get_float(
        controls,
        "lowe_ratio",
        LOWE_RATIO_PADRAO,
        0.60,
        0.98,
    )

    ransac_reproj_threshold = _get_float(
        controls,
        "ransac_reproj_threshold",
        RANSAC_REPROJ_THRESHOLD_PADRAO,
        1.0,
        20.0,
    )

    knn_k = _get_int(
        controls,
        "knn_k",
        KNN_K_PADRAO,
        3,
        20,
    )

    matches = []
    inliers = []

    _status_etapa(6, 11, f"{detector_nome}: executando matching interno de descritores.")
    if descriptors is not None and quantidade_keypoints >= 4:
        matches = _matching_interno(
            keypoints=keypoints,
            descriptors=descriptors,
            norma=NORMAS[detector_nome],
            lowe_ratio=lowe_ratio,
            distancia_minima_px=distancia_minima_px,
            knn_k=knn_k,
            max_candidatos_por_keypoint=estima_max_candidatos_por_keypoint(quantidade_keypoints),
        )

        _status_etapa(7, 11, f"{detector_nome}: filtrando correspondências com RANSAC.")
        inliers = _filtrar_por_ransac(
            keypoints=keypoints,
            matches=matches,
            ransac_reproj_threshold=ransac_reproj_threshold,
        )

    min_pontos_por_regiao = estima_min_pontos_por_regiao(
        quantidade_keypoints,
        len(inliers),
    )

    min_pontos_por_familia = estima_min_pontos_por_familia(len(inliers))

    _status_etapa(8, 11, f"{detector_nome}: agrupando pontos em regiões relacionadas.")
    _status_etapa(9, 11, f"{detector_nome}: desenhando regiões coloridas transparentes.")
    resultado = _desenhar_clusters_resultado(
        imagem_bgr=imagem_bgr,
        keypoints=keypoints,
        inliers=inliers,
        agrupamento_regiao_px=agrupamento_regiao_px,
        min_pontos_por_regiao=min_pontos_por_regiao,
        min_pontos_por_familia=min_pontos_por_familia,
        raio_ponto_cluster=raio_ponto_cluster,
    )

    return resultado, {
        "keypoints": quantidade_keypoints,
        "matches": len(matches),
        "inliers": len(inliers),
    }


def _processar_imagem(
    caminho_imagem: str,
    pasta_saida: str,
    controls: Dict[str, Any],
):
    nome_base = Path(caminho_imagem).stem

    _status_etapa(1, 11, f"{Path(caminho_imagem).name}: lendo imagem de entrada.")
    imagem_bgr = cv2.imread(caminho_imagem, cv2.IMREAD_COLOR)

    if imagem_bgr is None:
        raise RuntimeError("Imagem não pôde ser lida pelo OpenCV.")

    _status_etapa(2, 11, f"{Path(caminho_imagem).name}: convertendo imagem para escala de cinza.")
    gray = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY)
    _status_etapa(3, 11, f"{Path(caminho_imagem).name}: selecionando detectores configurados.")
    detectores = _obter_detectores(controls)

    for detector_nome in detectores:
        imagem_resultado, info = _processar_detector(
            imagem_bgr=imagem_bgr,
            gray=gray,
            detector_nome=detector_nome,
            controls=controls,
        )

        tmp = os.path.join(
            os.getenv("TEMP") or pasta_saida,
            f"{PREFIXO_SAIDA}{detector_nome}_{nome_base}.tmp.{EXTENSAO_SAIDA}",
        )

        final = os.path.join(
            pasta_saida,
            f"{PREFIXO_SAIDA}{detector_nome}_{nome_base}.{EXTENSAO_SAIDA}",
        )

        _status_etapa(10, 11, f"{Path(caminho_imagem).name} - {detector_nome}: salvando imagem de resultado.")
        cv2.imwrite(tmp, imagem_resultado)
        saida = replace_com_incremento(tmp, final)

        _status_etapa(11, 11, 
            f"{Path(caminho_imagem).name} - {detector_nome}: "
            f"kp={info['keypoints']}, matches={info['matches']}, inliers={info['inliers']} -> {saida}"
        )


# ============================================================
# Entrada PeriTASK
# ============================================================

def executar(arquivos, controls, pasta_saida):
    """
    Função obrigatória para comandos do PeriTASK.

    Controls aceitos:
        detectores: "AKAZE", "SIFT" ou "AKAZE e SIFT"
        lowe_ratio: default 0.85
        ransac_reproj_threshold: default 5.0
        knn_k: default 10
    """
    if controls is None:
        controls = {}

    arquivos_imagens = selecionar_arquivos(arquivos, "imagem")
    arquivos_imagens = filtrar_arquivos(
        arquivos_imagens,
        prefixo=PREFIXO_SAIDA,
        extensao=EXTENSAO_SAIDA,
    )

    if not arquivos_imagens:
        _status("Nenhuma imagem compatível foi selecionada.")
        _progress(100)
        return

    Path(pasta_saida).mkdir(parents=True, exist_ok=True)

    total = len(arquivos_imagens)
    ultimo_progresso = -1

    _status(f"Iniciando detector de cópia/cola em {total} imagem(ns).")

    for i, imagem in enumerate(arquivos_imagens, start=1):
        try:
            _status(f"Processando imagem {i}/{total}: {Path(imagem).name}")

            _processar_imagem(
                caminho_imagem=imagem,
                pasta_saida=pasta_saida,
                controls=controls,
            )

        except Exception as exc:
            _status(f"Erro ao processar {Path(imagem).name}: {exc}")
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
        description="Detector copy-paste para imagens - PeriTASK"
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
        "--detectores",
        default="AKAZE",
        help="AKAZE, SIFT ou 'AKAZE e SIFT'",
    )

    parser.add_argument(
        "--lowe-ratio",
        default=str(LOWE_RATIO_PADRAO),
        help="Ratio de Lowe. Default: 0.85",
    )

    parser.add_argument(
        "--ransac-reproj-threshold",
        default=str(RANSAC_REPROJ_THRESHOLD_PADRAO),
        help="Limiar de reprojeção do RANSAC. Default: 5.0",
    )

    parser.add_argument(
        "--knn-k",
        default=str(KNN_K_PADRAO),
        help="Número de vizinhos do KNN. Default: 10",
    )

    args = parser.parse_args()

    executar(
        arquivos=args.imagens,
        controls={
            "detectores": args.detectores,
            "lowe_ratio": args.lowe_ratio,
            "ransac_reproj_threshold": args.ransac_reproj_threshold,
            "knn_k": args.knn_k,
        },
        pasta_saida=args.saida,
    )
