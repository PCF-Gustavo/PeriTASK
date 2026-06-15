"""
Comando baseado no filtro Wavelets Noise Residue.
MAHDIAN, B.; SAIC, S. Using noise inconsistencies for blind image forensics. Image and Vision Computing, v. 27, n. 10, p. 1497-1503, set. 2009
Implementação de referência: https://github.com/SEPAEL/Peritus
imagem RGB -> escala de cinza -> DWT db8 (Daubechies 8) -> reconstrução suavizada -> resíduo de ruído → variância com janela deslizante -> pós-processamento -> regiões suspeitas coloridas
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np
from PIL import Image
import pywt

from utilitario.outros import replace_com_incremento, selecionar_arquivos


# ============================================================
# Metadados e saída
# ============================================================

PREFIXO_SAIDA = "wavelet_noise_residue_"
EXTENSAO_SAIDA = "png"


# ============================================================
# Parâmetros fixos do algoritmo
# ============================================================

BLOCK_SIZE_PADRAO = 5

DAUBECHIES_ORDEM = 8
WAVELET_NOME = f"db{DAUBECHIES_ORDEM}"
WAVELET_MODE = "symmetric"

NIVEIS_DWT = 1

# ============================================================
# Comunicação PeriTASK
# ============================================================

def _status(msg: str) -> None:
    print(f"STATUS:{msg}", flush=True)


def _status_etapa(etapa: int, total: int, mensagem: str) -> None:
    _status(f"Etapa {etapa}/{total} - {mensagem}")


def _progress(valor: int) -> None:
    valor = max(0, min(100, int(valor)))
    print(f"PROGRESS:{valor}", flush=True)


def _odd(valor: int) -> int:
    valor = int(valor)
    return valor + 1 if valor % 2 == 0 else valor


# ============================================================
# Leitura e escrita
# ============================================================

def _abrir_imagem_rgb(caminho_imagem: str) -> np.ndarray:
    return np.array(Image.open(caminho_imagem).convert("RGB"), dtype=np.uint8)


def _salvar_rgb(caminho_saida: str, imagem_rgb: np.ndarray) -> None:
    Image.fromarray(imagem_rgb.astype(np.uint8), mode="RGB").save(caminho_saida)


# ============================================================
# Núcleo do algoritmo
# ============================================================

def _normalizar_uint8(matriz: np.ndarray) -> np.ndarray:
    """
    Normalização robusta e conservadora para visualização.

    Evita o min/max puro, que deixava o resultado escuro demais quando
    havia poucos valores extremos, mas também evita o realce excessivo
    que ocorreu com percentis agressivos e sqrt.
    """
    matriz = matriz.astype(np.float32)

    valores = matriz[np.isfinite(matriz)]
    if valores.size == 0:
        return np.zeros_like(matriz, dtype=np.uint8)

    minimo = float(np.percentile(valores, 0.5))
    maximo = float(np.percentile(valores, 99.95))

    if maximo <= minimo:
        minimo = float(np.min(valores))
        maximo = float(np.max(valores))

    if maximo <= minimo:
        return np.zeros_like(matriz, dtype=np.uint8)

    normalizada = (matriz - minimo) / (maximo - minimo)
    normalizada = np.clip(normalizada, 0.0, 1.0)

    return np.clip(normalizada * 255.0, 0, 255).astype(np.uint8)

def aplicar_sensibilidade_uint8(img_uint8, sensibilidade):
    """
    Ajuste de sensibilidade controlando contraste via gamma.

    sensibilidade:
        0 → imagem mais escura (menos destaque)
        10 → imagem mais clara (mais hotspots)
    """
    gamma = 2.0 * (0.3 / 2.0) ** (sensibilidade / 10.0)

    tabela = np.array([
        ((i / 255.0) ** gamma) * 255 for i in range(256)
    ], dtype=np.uint8)

    return cv2.LUT(img_uint8, tabela)

def _reconstruir_aproximacao_wavelet(gray: np.ndarray) -> np.ndarray:
    """
    Aplica DWT 2D com Daubechies 8 e reconstrói a imagem mantendo apenas
    a aproximação.
    """
    gray_float = gray.astype(np.float32)

    coeffs = pywt.wavedec2(
        gray_float,
        wavelet=WAVELET_NOME,
        mode=WAVELET_MODE,
        level=NIVEIS_DWT,
    )

    coeffs_filtrados = [coeffs[0]]

    for detalhes in coeffs[1:]:
        cH, cV, cD = detalhes
        coeffs_filtrados.append(
            (
                np.zeros_like(cH),
                np.zeros_like(cV),
                np.zeros_like(cD),
            )
        )

    reconstruida = pywt.waverec2(
        coeffs_filtrados,
        wavelet=WAVELET_NOME,
        mode=WAVELET_MODE,
    )

    reconstruida = reconstruida[: gray.shape[0], : gray.shape[1]]
    return reconstruida.astype(np.float32)


def _calcular_residuo_wavelet(gray: np.ndarray) -> np.ndarray:
    """
    Calcula o resíduo de ruído a partir dos detalhes high-pass da DWT db8.

    A versão anterior baseada em energia quadrática dos detalhes ficou
    forte demais. Esta revisão mantém a abordagem por detalhes wavelet,
    mas reconstrói somente as sub-bandas de detalhe e usa a magnitude
    absoluta do resíduo reconstruído, com suavização muito leve.

    Isso tende a ficar mais próximo do filtro original do que usar apenas:
        imagem - reconstrução_da_aproximação

    e menos agressivo do que somar:
        detalhe_reconstruído²
    """
    gray_float = gray.astype(np.float32)

    coeffs = pywt.wavedec2(
        gray_float,
        wavelet=WAVELET_NOME,
        mode=WAVELET_MODE,
        level=NIVEIS_DWT,
    )

    coeffs_detalhes = [np.zeros_like(coeffs[0])]

    for detalhes in coeffs[1:]:
        cH, cV, cD = detalhes
        coeffs_detalhes.append(
            (
                cH.copy(),
                cV.copy(),
                cD.copy(),
            )
        )

    residuo = pywt.waverec2(
        coeffs_detalhes,
        wavelet=WAVELET_NOME,
        mode=WAVELET_MODE,
    )

    residuo = residuo[: gray.shape[0], : gray.shape[1]]
    residuo = np.abs(residuo.astype(np.float32))

    # Suavização mínima para reduzir pontilhado isolado sem espalhar demais.
    residuo = cv2.GaussianBlur(
        residuo,
        (3, 3),
        0,
        borderType=cv2.BORDER_REFLECT,
    )

    return residuo.astype(np.float32)


def _mapa_variancia_local(residuo: np.ndarray, block_size: int) -> np.ndarray:
    """
    Calcula variância/energia local do resíduo usando janela deslizante.

    A versão por blocos não sobrepostos deixou o resultado forte e blocado.
    Esta versão usa a mesma ideia local controlada por block_size, mas com
    janela deslizante por média local:

        Var(X) = E[X²] - E[X]²

    Como o resíduo já é magnitude de alta frequência, mistura-se uma pequena
    parcela de energia média para aproximar o aspecto mais preenchido do
    original sem saturar.
    """
    residuo = residuo.astype(np.float32)

    k = _odd(max(3, int(block_size)))

    media = cv2.blur(
        residuo,
        (k, k),
        borderType=cv2.BORDER_REFLECT,
    )

    media2 = cv2.blur(
        residuo * residuo,
        (k, k),
        borderType=cv2.BORDER_REFLECT,
    )

    variancia = np.maximum(media2 - media * media, 0.0)

    # Energia local moderada: ajuda a preencher regiões texturizadas,
    # mas com peso baixo para não repetir o excesso da versão anterior.
    energia_media = media2

    mapa = 0.75 * variancia + 0.25 * energia_media

    # Suavização leve proporcional ao block_size, limitada para não borrar.
    k_suave = _odd(max(3, min(9, k + 2)))
    mapa = cv2.GaussianBlur(
        mapa,
        (k_suave, k_suave),
        0,
        borderType=cv2.BORDER_REFLECT,
    )

    return mapa.astype(np.float32)


# ============================================================
# Visualização
# ============================================================

def _criar_visualizacao(
    imagem_rgb: np.ndarray,
    mapa_variancia: np.ndarray,
    sensibilidade: float
) -> np.ndarray:

    variancia_uint8 = _normalizar_uint8(mapa_variancia)

    # ✅ AQUI entra a sensibilidade (ANTES do colormap)
    variancia_uint8 = aplicar_sensibilidade_uint8(
        variancia_uint8,
        sensibilidade
    )

    heat_bgr = cv2.applyColorMap(variancia_uint8, cv2.COLORMAP_JET)
    heat_rgb = cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)

    return heat_rgb


# ============================================================
# Pipeline
# ============================================================

def _processar_imagem(
    caminho_imagem: str,
    pasta_saida: str,
    controls: Dict[str, Any],
) -> str:

    nome_base = Path(caminho_imagem).stem

    block_size = float(controls.get("block_size", 5.0))
    sensibilidade = float(controls.get("sensitivity", 5.0))

    block_size = _odd(block_size)

    _status_etapa(1, 7, f"Lendo imagem: {Path(caminho_imagem).name}")
    imagem_rgb = _abrir_imagem_rgb(caminho_imagem)

    _progress(10)

    _status_etapa(2, 7, "Convertendo imagem inteira para escala de cinza.")
    gray = cv2.cvtColor(imagem_rgb, cv2.COLOR_RGB2GRAY)

    _progress(25)

    _status_etapa(
        3,
        7,
        f"Aplicando DWT {WAVELET_NOME} na imagem inteira.",
    )
    residuo = _calcular_residuo_wavelet(gray)

    _progress(50)

    _status_etapa(
        4,
        7,
        f"Calculando variância local com block_size={block_size}.",
    )
    mapa_variancia = _mapa_variancia_local(residuo, block_size)

    _progress(85)

    _status_etapa(7, 7, "Gerando visualização.")

    resultado = _criar_visualizacao(
        imagem_rgb=imagem_rgb,
        mapa_variancia=mapa_variancia,
        sensibilidade=sensibilidade
    )

    nome_saida = f"{PREFIXO_SAIDA}{nome_base}.{EXTENSAO_SAIDA}"
    caminho_saida = os.path.join(pasta_saida, nome_saida)

    pasta_tmp = os.getenv("TEMP") or pasta_saida
    caminho_tmp = os.path.join(
        pasta_tmp,
        f"{PREFIXO_SAIDA}{nome_base}_{os.getpid()}.tmp.{EXTENSAO_SAIDA}",
    )

    _salvar_rgb(caminho_tmp, resultado)

    caminho_saida = replace_com_incremento(caminho_tmp, caminho_saida)

    _progress(100)
    _status(f"Arquivo gerado: {caminho_saida}")

    return caminho_saida


# ============================================================
# Entrada PeriTASK
# ============================================================

def executar(arquivos, controls, pasta_saida):
    """
    Função obrigatória para comandos PeriTASK:
    executar(arquivos, controls, pasta_saida)
    """
    _progress(0)

    try:
        if controls is None:
            controls = {}

        imagens = selecionar_arquivos(arquivos, "imagem")

        if not imagens:
            _status("Nenhuma imagem compatível foi selecionada.")
            _progress(100)
            return []

        Path(pasta_saida).mkdir(parents=True, exist_ok=True)

        saidas: List[str] = []

        total = len(imagens)

        for idx, caminho_imagem in enumerate(imagens, start=1):
            _status(
                f"Processando imagem {idx}/{total}: "
                f"{Path(caminho_imagem).name}"
            )

            saida = _processar_imagem(
                caminho_imagem=caminho_imagem,
                pasta_saida=pasta_saida,
                controls=controls,
            )

            saidas.append(saida)

        _status(f"Processamento concluído. Arquivos gerados: {len(saidas)}")
        _progress(100)

        return saidas

    except Exception:
        _status("Erro ao executar Wavelet Noise Residue.")
        _status(traceback.format_exc())
        _progress(100)
        raise


# ============================================================
# Execução direta
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wavelet Noise Residue")
    parser.add_argument("imagens", nargs="+")
    parser.add_argument("--saida", default=".")
    parser.add_argument("--block_size", type=int, default=BLOCK_SIZE_PADRAO)
    parser.add_argument("--sensitivity", type=float, default=5.0)

    args = parser.parse_args()

    controls = {
        "block_size": args.block_size,
        "sensitivity": args.sensitivity
    }

    executar(args.imagens, controls, args.saida)
