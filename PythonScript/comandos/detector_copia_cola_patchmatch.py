
"""
Comando baseado no filtro de detecção de cópia/cola por PatchMatch com momentos de Zernike
COZZOLINO, D.; POGGI, G.; VERDOLIVA, L. Copy-move forgery detection based on PatchMatch, 2014
Implementação de referência: Paulo Max Gil Innocencio Reis - Instituto Nacional de Criminalística
imagem RGB -> patches sobrepostos -> momentos de Zernike -> PatchMatch -> campo de deslocamentos -> pós-processamento DLF-like -> famílias origem/destino coloridas
"""

from __future__ import annotations

import math
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2 as cv
import numpy as np
from PIL import Image

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

P_PADRAO = 5
N_RS_CANDIDATES_PADRAO = 5
N_ITER_PADRAO = 5
MAX_LADO_PATCHMATCH_PADRAO = 1400
ZERNIKE_THREADS_PADRAO = max(1, min(4, os.cpu_count() or 1))

# ============================================================
# Constantes internas
# ============================================================

MAX_ZRD = 6
INIT_METHOD = 2
ZERNIKE = True
ALPHA_REGIAO = 0.42
MAX_N_ITERATIONS = 20

CORES_REGIOES_RGB = [
    (255, 0, 0),
    (0, 0, 255),
    (0, 255, 0),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 128, 0),
    (128, 0, 255),
    (0, 180, 120),
    (255, 80, 160),
]

_ZERNIKE_FILTERS_CACHE: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}

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


def _get_int(controls: Dict[str, Any], chave: str, padrao: int, minimo: int, maximo: int) -> int:
    try:
        valor = int(float(str(controls.get(chave, padrao)).replace(",", ".").strip()))
    except Exception:
        valor = padrao
    return max(minimo, min(maximo, valor))

# ============================================================
# Estimadores automáticos
# ============================================================

def estima_min_dn(largura: int, altura: int) -> int:
    return int(max(24, min(120, round(min(largura, altura) * 0.06))))


def estima_min_region_size(largura: int, altura: int) -> int:
    return int(max(60, min(2000, round(largura * altura * 0.00035))))


def estima_min_votos_relacao(largura: int, altura: int, p: int) -> int:
    return int(max(30, min(90, round(((2 * p + 1) ** 2) * 0.25))))


def estima_min_area_blob_relacao(largura: int, altura: int, p: int) -> int:
    return int(max(30, min(120, round(((2 * p + 1) ** 2) * 0.25))))


def estima_tolerancia_deslocamento_relacao(largura: int, altura: int, p: int, min_dn: int) -> int:
    return int(max(6, min(20, round(p * 1.5))))


def estima_raio_expansao_relacao(largura: int, altura: int, p: int) -> int:
    return int(max(2, min(8, round(p * 0.8))))


def estima_raio_pintura_origem(largura: int, altura: int, p: int) -> int:
    return int(max(1, min(4, round(p * 0.4))))


def estima_raio_pintura_destino(largura: int, altura: int, p: int) -> int:
    return int(max(1, min(5, round(p * 0.6))))


def _odd(k: int) -> int:
    k = int(k)
    return k + 1 if k % 2 == 0 else k


def estima_kernel_fechamento_relacao(largura: int, altura: int, p: int) -> int:
    return _odd(int(max(3, min(9, 2 * round(p * 0.4) + 1))))


def estima_blur_alpha_relacao(largura: int, altura: int, p: int) -> int:
    return _odd(int(max(3, min(9, 2 * round(p * 0.4) + 1))))


def estima_tolerancia_centroide_relacao(largura: int, altura: int, p: int) -> float:
    return float(max(10, min(40, round(p * 4))))


def estima_limiar_homogeneidade_fallback(largura: int, altura: int, p: int) -> float:
    return float(max(8.0, min(22.0, 10.0 + p * 1.5)))


def estima_parametros_visualizacao(largura: int, altura: int, p: int, min_dn: int) -> Dict[str, Any]:
    patch_area = (2 * p + 1) ** 2
    return {
        "min_votos_relacao": estima_min_votos_relacao(largura, altura, p),
        "min_area_blob_relacao": estima_min_area_blob_relacao(largura, altura, p),
        "tolerancia_deslocamento": estima_tolerancia_deslocamento_relacao(largura, altura, p, min_dn),
        "raio_expansao": estima_raio_expansao_relacao(largura, altura, p),
        "raio_pintura_origem": estima_raio_pintura_origem(largura, altura, p),
        "raio_pintura_destino": estima_raio_pintura_destino(largura, altura, p),
        "kernel_fechamento": estima_kernel_fechamento_relacao(largura, altura, p),
        "blur_alpha": estima_blur_alpha_relacao(largura, altura, p),
        "tolerancia_centroide": estima_tolerancia_centroide_relacao(largura, altura, p),
        "limiar_sobreposicao_duplicata": 0.55,
        "limiar_area_semelhante": 0.40,
        "limiar_homogeneidade_fallback": estima_limiar_homogeneidade_fallback(largura, altura, p),
        "limiar_contencao_relacao": 0.78,
        "limiar_sobreposicao_conflito": 0.35,
        "limiar_extra_relativo_uniao": 0.18,
        "tolerancia_deslocamento_conflito": float(max(8, min(28, round(p * 2.0)))),
        "max_iter_resolucao_conflitos": 6,
        "raio_contato_familia": int(max(2, min(8, round(p * 0.8)))),
        "min_area_ponte_familia": int(max(12, min(80, round(patch_area * 0.15)))),
        "max_iter_agrupamento_familias": 6,
        "raio_validacao_visual_familia": int(max(2, min(8, round(p * 0.8)))),
        "min_pixels_validacao_visual": int(max(40, min(180, round(patch_area * 0.45)))),
        "min_cobertura_campo_familia": 0.25,
        "min_cobertura_campo_direcional": 0.20,
        "limiar_mad_rgb_familia": float(max(22.0, min(48.0, 26.0 + p * 2.0))),
        "limiar_mad_luma_familia": float(max(18.0, min(40.0, 20.0 + p * 1.7))),
        "raio_coerencia_campo": int(max(3, min(10, round(p * 0.9)))),
        "tolerancia_residuo_campo": float(max(4.0, min(20.0, p * 2.0))),
        "fator_mad_residuo_campo": 2.5,
        "fator_variacao_campo_compativel": 0.14,
    }

# ============================================================
# PatchMatch/Zernike sem Numba
# ============================================================

np.random.seed(0)

FACTORIALS_LOOKUP_TABLE = np.array([
    1, 1, 2, 6, 24, 120, 720, 5040, 40320,
    362880, 3628800, 39916800, 479001600,
    6227020800, 87178291200, 1307674368000,
    20922789888000, 355687428096000, 6402373705728000,
    121645100408832000, 2432902008176640000,
], dtype=np.int64)


def factorial(n: int) -> int:
    if n > 20:
        raise ValueError
    return int(FACTORIALS_LOOKUP_TABLE[n])


def h(x: float) -> float:
    x = float(x)
    ax = abs(x)
    if ax <= 1:
        return 1.5 * ax ** 3 - 2.5 * x ** 2 + 1
    if ax <= 2:
        return -0.5 * ax ** 3 + 2.5 * x ** 2 - 4 * ax + 2
    return 0.0


def double2single_zernike_index(radial_degree: int, azimuthal_degree: int) -> int:
    assert (radial_degree - azimuthal_degree) % 2 == 0
    assert radial_degree > 0 and azimuthal_degree > 0
    n_smaller_polynomials = (radial_degree // 2) * ((radial_degree + 1) // 2)
    if radial_degree % 2 == 0:
        return n_smaller_polynomials + azimuthal_degree // 2 - 1
    return n_smaller_polynomials + (azimuthal_degree - 1) // 2


MAX_ZERNIKE_ORDER = 10
C = np.zeros((MAX_ZERNIKE_ORDER + 1, MAX_ZERNIKE_ORDER + 1, MAX_ZERNIKE_ORDER // 2 + 1), dtype=np.float64)
for rd in range(1, MAX_ZERNIKE_ORDER + 1):
    for ad in range(1, rd + 1):
        if (rd - ad) % 2 == 0:
            for s in range((rd - ad) // 2 + 1):
                num = (-1) ** s * math.factorial(rd - s)
                den = (rd - 2 * s + 2) * math.factorial((rd + ad) // 2 - s) * math.factorial((rd - ad) // 2 - s)
                C[rd, ad, s] = num / den


def _criar_zernike_filters_numpy(p: int, max_zrd: int) -> np.ndarray:
    n_filters = double2single_zernike_index(max_zrd + 1, max_zrd % 2 + 1)
    filtros = np.zeros((2 * p + 1, 2 * p + 1, n_filters), dtype=np.complex64)
    for rho in range(p):
        dtheta = 2 * np.pi / (4 * (2 * rho + 1))
        for theta in range(4 * (2 * rho + 1)):
            ang0 = theta * dtheta
            ang1 = (theta + 1) * dtheta
            i0 = rho * np.cos(ang0)
            j0 = rho * np.sin(ang0)
            imin = int(np.floor(i0) - 1)
            imax = int(np.floor(i0) + 2)
            jmin = int(np.floor(j0) - 1)
            jmax = int(np.floor(j0) + 2)
            for rd in range(1, max_zrd + 1):
                for ad in range((rd - 1) % 2 + 1, rd + 1, 2):
                    idx = double2single_zernike_index(rd, ad)
                    w = 0.0 + 0.0j
                    for s in range((rd - ad) // 2 + 1):
                        w += C[rd, ad, s] * (((rho + 1) / p) ** (rd - 2 * s + 2) - (rho / p) ** (rd - 2 * s + 2))
                    w *= 1j / ad * (np.exp(-1j * ad * ang1) - np.exp(-1j * ad * ang0))
                    for i in range(imin, min(imax, p) + 1):
                        for j in range(jmin, min(jmax, p) + 1):
                            filtros[i + p, j + p, idx] += h(i0 - i) * h(j0 - j) * w
    return filtros


def _obter_zernike_filters_cache(p: int, max_zrd: int) -> Tuple[Dict[str, np.ndarray], bool]:
    chave = (int(p), int(max_zrd))
    banco = _ZERNIKE_FILTERS_CACHE.get(chave)
    if banco is not None:
        return banco, True
    filtros = _criar_zernike_filters_numpy(chave[0], chave[1])
    banco = {
        "complex": filtros,
        "real": np.ascontiguousarray(filtros.real.astype(np.float32)),
        "imag": np.ascontiguousarray(filtros.imag.astype(np.float32)),
    }
    _ZERNIKE_FILTERS_CACHE[chave] = banco
    return banco, False


def _filtrar_zernike_um_canal(canal: np.ndarray, filtro_real: np.ndarray, filtro_imag: np.ndarray) -> np.ndarray:
    resposta_real = cv.filter2D(canal, cv.CV_32F, filtro_real, borderType=cv.BORDER_CONSTANT)
    resposta_imag = cv.filter2D(canal, cv.CV_32F, filtro_imag, borderType=cv.BORDER_CONSTANT)
    return np.sqrt(resposta_real * resposta_real + resposta_imag * resposta_imag).astype(np.float32)


OFFSETS = np.array([(0, -1), (-1, -1), (-1, 0), (-1, 1)], dtype=np.int64)
N_OFFSETS = len(OFFSETS)


class PatchMatch:
    def __init__(self, im, p, max_zrd, min_dn, n_rs_candidates, zernike_filters, zernike_threads=1):
        self.im = im.astype(np.float32, copy=False)
        self.m, self.n, _ = im.shape
        self.p = int(p)
        assert min(self.m, self.n) >= 2 * self.p + 1
        assert self.p >= 2
        self.max_zrd = int(max_zrd)
        self.min_dn = int(min_dn)
        self.n_rs_candidates = int(n_rs_candidates)
        self.zernike_threads = max(1, int(zernike_threads))
        self.n_performed_iterations = 0
        self.n_propagations = np.zeros(MAX_N_ITERATIONS, dtype=np.int64)
        self.sum_of_distances = np.zeros(MAX_N_ITERATIONS + 1, dtype=np.float64)
        self.zernike_filters = zernike_filters
        self.zernike_moments = np.zeros((self.m, self.n, 1), dtype=np.float32)
        self.vect_field = np.zeros((self.m, self.n, 2), dtype=np.int64)
        self.dist_field = np.zeros((self.m, self.n), dtype=np.float32)
        self._roi_y, self._roi_x = np.mgrid[self.p:self.m - self.p, self.p:self.n - self.p]
        self._roi = (slice(self.p, self.m - self.p), slice(self.p, self.n - self.p))
        self.create_zernike_moments()
        self.create_vect_field2()
        self.create_dist_field()
        self.update_sum_of_distances()

    def create_zernike_moments(self):
        filtros_real = self.zernike_filters["real"]
        filtros_imag = self.zernike_filters["imag"]
        n_filters = filtros_real.shape[-1]
        self.zernike_moments = np.zeros((self.m, self.n, 3 * n_filters), dtype=np.float32)
        tarefas = []
        for rgb in range(3):
            canal = np.ascontiguousarray(self.im[..., rgb].astype(np.float32, copy=False))
            for idx in range(n_filters):
                tarefas.append((rgb, idx, canal, filtros_real[..., idx], filtros_imag[..., idx]))

        def executar_tarefa(tarefa):
            rgb, idx, canal, filtro_real, filtro_imag = tarefa
            magnitude = _filtrar_zernike_um_canal(canal, filtro_real, filtro_imag)
            return rgb, idx, magnitude

        if self.zernike_threads > 1 and len(tarefas) > 1:
            with ThreadPoolExecutor(max_workers=self.zernike_threads) as executor:
                for rgb, idx, magnitude in executor.map(executar_tarefa, tarefas):
                    self.zernike_moments[self._roi[0], self._roi[1], rgb * n_filters + idx] = magnitude[self._roi]
        else:
            for tarefa in tarefas:
                rgb, idx, magnitude = executar_tarefa(tarefa)
                self.zernike_moments[self._roi[0], self._roi[1], rgb * n_filters + idx] = magnitude[self._roi]

    def create_vect_field2(self):
        end_points = np.zeros((self.m, self.n, 2), dtype=np.int64)
        start_points = np.zeros((self.m, self.n, 2), dtype=np.int64)
        start_points[:, :, 0] = np.arange(self.m).reshape((self.m, 1))
        start_points[:, :, 1] = np.arange(self.n).reshape((1, self.n))
        end_points[:, :, 0] = np.random.randint(low=self.p, high=self.m - self.p, size=(self.m, self.n))
        end_points[:, :, 1] = np.random.randint(low=self.p, high=self.n - self.p, size=(self.m, self.n))
        diff = np.abs(end_points - start_points)
        too_small = np.maximum(diff[..., 0], diff[..., 1]) < self.min_dn
        while np.any(too_small):
            count = int(np.sum(too_small))
            end_points[..., 0][too_small] = np.random.randint(low=self.p, high=self.m - self.p, size=count)
            end_points[..., 1][too_small] = np.random.randint(low=self.p, high=self.n - self.p, size=count)
            diff = np.abs(end_points - start_points)
            too_small = np.maximum(diff[..., 0], diff[..., 1]) < self.min_dn
        self.vect_field = end_points - start_points

    def create_dist_field(self):
        self.dist_field = np.zeros((self.m, self.n), dtype=np.float32)
        ys, xs = self._roi_y, self._roi_x
        yd = ys + self.vect_field[self._roi][..., 0]
        xd = xs + self.vect_field[self._roi][..., 1]
        diff = self.zernike_moments[ys, xs] - self.zernike_moments[yd, xd]
        dist = np.sqrt(np.sum(diff * diff, axis=-1)).astype(np.float32)
        self.dist_field[self._roi] = dist

    def update_sum_of_distances(self):
        self.sum_of_distances[self.n_performed_iterations] = float(self.dist_field[self._roi].sum())

    def patch_features(self, i, j):
        return self.zernike_moments[i:i + 1, j:j + 1]

    def dist(self, i, j, k, l):
        diff = self.zernike_moments[i, j] - self.zernike_moments[k, l]
        return float(np.sqrt(np.dot(diff, diff)))

    def dist2candidate(self, i, j, k, l):
        dk, dl = self.vect_field[k, l]
        return self.dist(i, j, i + int(dk), j + int(dl))

    def test_min_separation(self, di, dj):
        return abs(int(di)) >= self.min_dn or abs(int(dj)) >= self.min_dn

    def is_in_inner_image(self, i, j):
        return i >= self.p and i < self.m - self.p and j >= self.p and j < self.n - self.p

    def scan(self):
        for i in range(self.p, self.m - self.p):
            for j in range(self.p, self.n - self.p):
                d0 = float(self.dist_field[i, j])
                zo_distances = np.inf * np.ones(N_OFFSETS, dtype=np.float64)
                zo_vectors = np.zeros((N_OFFSETS, 2), dtype=np.int64)
                for c in range(N_OFFSETS):
                    oi, oj = int(OFFSETS[c, 0]), int(OFFSETS[c, 1])
                    ni, nj = i + oi, j + oj
                    if not self.is_in_inner_image(ni, nj):
                        continue
                    di, dj = int(self.vect_field[ni, nj, 0]), int(self.vect_field[ni, nj, 1])
                    if self.is_in_inner_image(i + di, j + dj):
                        zo_distances[c] = self.dist(i, j, i + di, j + dj)
                        zo_vectors[c, 0] = di
                        zo_vectors[c, 1] = dj
                fo_distances = np.inf * np.ones(N_OFFSETS, dtype=np.float64)
                fo_vectors = np.zeros((N_OFFSETS, 2), dtype=np.int64)
                for c in range(N_OFFSETS):
                    oi, oj = int(OFFSETS[c, 0]), int(OFFSETS[c, 1])
                    n1i, n1j = i + oi, j + oj
                    n2i, n2j = i + 2 * oi, j + 2 * oj
                    if not self.is_in_inner_image(n2i, n2j):
                        continue
                    di = int(2 * self.vect_field[n1i, n1j, 0] - self.vect_field[n2i, n2j, 0])
                    dj = int(2 * self.vect_field[n1i, n1j, 1] - self.vect_field[n2i, n2j, 1])
                    if self.is_in_inner_image(i + di, j + dj) and self.test_min_separation(di, dj):
                        fo_distances[c] = self.dist(i, j, i + di, j + dj)
                        fo_vectors[c, 0] = di
                        fo_vectors[c, 1] = dj
                all_distances = np.concatenate((zo_distances, fo_distances))
                idx = int(np.argmin(all_distances))
                dmin = float(all_distances[idx])
                if dmin < d0:
                    self.dist_field[i, j] = dmin
                    self.n_propagations[self.n_performed_iterations] += 1
                    if idx < N_OFFSETS:
                        self.vect_field[i, j, 0] = zo_vectors[idx, 0]
                        self.vect_field[i, j, 1] = zo_vectors[idx, 1]
                    else:
                        self.vect_field[i, j, 0] = fo_vectors[idx - N_OFFSETS, 0]
                        self.vect_field[i, j, 1] = fo_vectors[idx - N_OFFSETS, 1]

    def random_search_vetorizado(self):
        atualizacoes_total = 0
        ys, xs = self._roi_y, self._roi_x
        dist_roi = self.dist_field[self._roi]
        vf_roi = self.vect_field[self._roi]
        for k in range(self.n_rs_candidates):
            raio = 2 ** k
            di_atual = vf_roi[..., 0]
            dj_atual = vf_roi[..., 1]
            low_i = np.maximum(ys + di_atual - raio, self.p) - ys
            high_i = np.minimum(ys + di_atual + raio + 1, self.m - self.p) - ys
            low_j = np.maximum(xs + dj_atual - raio, self.p) - xs
            high_j = np.minimum(xs + dj_atual + raio + 1, self.n - self.p) - xs
            span_i = high_i - low_i
            span_j = high_j - low_j
            valid_span = (span_i > 0) & (span_j > 0)
            if not np.any(valid_span):
                continue
            di_cand = low_i + (np.random.random(size=span_i.shape) * span_i).astype(np.int64)
            dj_cand = low_j + (np.random.random(size=span_j.shape) * span_j).astype(np.int64)
            min_sep = (np.abs(di_cand) >= self.min_dn) | (np.abs(dj_cand) >= self.min_dn)
            valid = valid_span & min_sep
            if not np.any(valid):
                continue
            yd = ys + di_cand
            xd = xs + dj_cand
            diff = self.zernike_moments[ys, xs] - self.zernike_moments[yd, xd]
            dist_cand = np.sqrt(np.sum(diff * diff, axis=-1)).astype(np.float32)
            melhor = valid & (dist_cand < dist_roi)
            qtd = int(np.count_nonzero(melhor))
            if qtd <= 0:
                continue
            vf_roi[..., 0][melhor] = di_cand[melhor]
            vf_roi[..., 1][melhor] = dj_cand[melhor]
            dist_roi[melhor] = dist_cand[melhor]
            atualizacoes_total += qtd
        self.n_propagations[self.n_performed_iterations] += atualizacoes_total

    def symmetry(self):
        for i in range(self.p, self.m - self.p):
            for j in range(self.p, self.n - self.p):
                di = int(self.vect_field[i, j, 0])
                dj = int(self.vect_field[i, j, 1])
                if self.dist_field[i + di, j + dj] > self.dist_field[i, j]:
                    self.n_propagations[self.n_performed_iterations] += 1
                    self.vect_field[i + di, j + dj, 0] = -di
                    self.vect_field[i + di, j + dj, 1] = -dj
                    self.dist_field[i + di, j + dj] = self.dist_field[i, j]

    def flip(self):
        self.im = self.im[::-1, ::-1]
        self.vect_field = -self.vect_field[::-1, ::-1]
        self.dist_field = self.dist_field[::-1, ::-1]
        self.zernike_moments = self.zernike_moments[::-1, ::-1]
        self._roi_y, self._roi_x = np.mgrid[self.p:self.m - self.p, self.p:self.n - self.p]
        self._roi = (slice(self.p, self.m - self.p), slice(self.p, self.n - self.p))

    def iterate(self):
        for _ in range(2):
            self.scan()
            self.random_search_vetorizado()
            self.symmetry()
            self.flip()
        self.n_performed_iterations += 1
        self.update_sum_of_distances()

# ============================================================
# Máscara inicial e utilitários de visualização
# ============================================================

def gradn(im):
    return np.sqrt(np.diff(im, axis=0)[:, :-1] ** 2 + np.diff(im, axis=1)[:-1, :] ** 2)


def compute_mask_1(vect_field, m, n, p, min_region_size):
    r = p
    th = 0.5
    s = 2 * p
    vx = gradn(vect_field[..., 0])
    vy = gradn(vect_field[..., 1])
    mask_0 = np.zeros((m, n))
    u = (np.mean(vx) + np.mean(vy)) / 100
    mask_0[:-1, :-1] = 1 * (vy < u) * (vx < u)
    kernel = np.ones((r, r))
    kernel = kernel / np.sum(kernel)
    mask_1 = cv.filter2D(mask_0, -1, kernel)
    mask_2 = 1 * (mask_1 > th)
    n_components, component = cv.connectedComponents(np.uint8(mask_2))
    selected = []
    for i in range(1, n_components):
        if np.sum(component == i) > min_region_size:
            selected.append(i)
    mask_4 = np.zeros((m, n))
    for i in selected:
        mask_4 += 1 * (component == i)
    return cv.dilate(mask_4, np.ones((s, s))) > 0


def _abrir_imagem_rgb(caminho_imagem: str) -> np.ndarray:
    return np.array(Image.open(caminho_imagem).convert("RGB"), dtype=np.uint8)


def _salvar_rgb(caminho_saida: str, imagem_rgb: np.ndarray) -> None:
    Image.fromarray(imagem_rgb.astype(np.uint8), mode="RGB").save(caminho_saida)


def _gerar_cores_distintas(n: int):
    if n <= len(CORES_REGIOES_RGB):
        return CORES_REGIOES_RGB[:n]
    import colorsys
    cores = list(CORES_REGIOES_RGB)
    h = 0.0
    while len(cores) < n:
        h = (h + 0.618033988749895) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
        cor = (int(r * 255), int(g * 255), int(b * 255))
        if cor not in cores:
            cores.append(cor)
    return cores


def _remover_blobs_pequenos(mask_binaria: np.ndarray, min_area: int) -> np.ndarray:
    if min_area <= 1:
        return mask_binaria.astype(bool)
    n_labels, labels_cc, stats, _ = cv.connectedComponentsWithStats(mask_binaria.astype(np.uint8), connectivity=8)
    out = np.zeros_like(mask_binaria, dtype=bool)
    for label in range(1, n_labels):
        if int(stats[label, cv.CC_STAT_AREA]) >= min_area:
            out[labels_cc == label] = True
    return out


def _dilatar_bool(mask: np.ndarray, raio: int) -> np.ndarray:
    if raio <= 0:
        return mask.astype(bool)
    k = 2 * int(raio) + 1
    kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (k, k))
    return cv.dilate(mask.astype(np.uint8), kernel, iterations=1).astype(bool)


def _preparar_mascara_visual_relacao(mask_relacao: np.ndarray, raio_pintura: int, kernel_fechamento: int, blur_alpha: int) -> np.ndarray:
    mask_uint8 = mask_relacao.astype(np.uint8)
    if raio_pintura > 0:
        k = 2 * int(raio_pintura) + 1
        mask_uint8 = cv.dilate(mask_uint8, cv.getStructuringElement(cv.MORPH_ELLIPSE, (k, k)), iterations=1)
    if kernel_fechamento > 0:
        k = _odd(int(kernel_fechamento))
        mask_uint8 = cv.morphologyEx(mask_uint8, cv.MORPH_CLOSE, cv.getStructuringElement(cv.MORPH_ELLIPSE, (k, k)))
    if blur_alpha > 0:
        k = _odd(int(blur_alpha))
        mf = cv.GaussianBlur(mask_uint8.astype(np.float32), (k, k), 0)
        mx = float(mf.max())
        if mx > 0:
            mf = mf / mx
        return mf
    return mask_uint8.astype(np.float32)


def _mascara_eh_homogenea(imagem_rgb: np.ndarray, mask: np.ndarray, limiar_std: float, min_pixels: int = 30) -> bool:
    ys, xs = np.where(mask)
    if len(ys) < min_pixels:
        return False
    pixels = imagem_rgb[ys, xs].astype(np.float32)
    lum = 0.299 * pixels[:, 0] + 0.587 * pixels[:, 1] + 0.114 * pixels[:, 2]
    return float(np.std(lum)) <= limiar_std and float(np.mean(np.std(pixels, axis=0))) <= limiar_std


def _manter_componentes_que_tocam_seed(mask_candidata: np.ndarray, mask_seed: np.ndarray, raio_contato: int) -> np.ndarray:
    if not np.any(mask_candidata):
        return np.zeros_like(mask_candidata, dtype=bool)
    seed = mask_seed.astype(np.uint8)
    if raio_contato > 0:
        seed = _dilatar_bool(seed > 0, raio_contato).astype(np.uint8)
    n_labels, labels_cc, _stats, _ = cv.connectedComponentsWithStats(mask_candidata.astype(np.uint8), connectivity=8)
    out = np.zeros_like(mask_candidata, dtype=bool)
    for label in range(1, n_labels):
        comp = labels_cc == label
        if np.any(comp & (seed > 0)):
            out[comp] = True
    return out

# ============================================================
# Coerência DLF-like
# ============================================================

def _vetor_mediano_mask(mask: np.ndarray, vect_field: np.ndarray) -> Tuple[int, int]:
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return 0, 0
    return int(round(float(np.median(vect_field[ys, xs, 0])))), int(round(float(np.median(vect_field[ys, xs, 1]))))


def _destinos_por_campo(mask_src: np.ndarray, vect_field: np.ndarray):
    hgt, wid = mask_src.shape[:2]
    ys, xs = np.where(mask_src)
    if len(ys) == 0:
        z = np.array([], dtype=np.int32)
        return z, z, z, z
    yd = ys + vect_field[ys, xs, 0].astype(np.int32)
    xd = xs + vect_field[ys, xs, 1].astype(np.int32)
    ok = (yd >= 0) & (yd < hgt) & (xd >= 0) & (xd < wid)
    return ys[ok], xs[ok], yd[ok], xd[ok]


def _mascara_destino_por_campo(mask_src: np.ndarray, vect_field: np.ndarray, labels: np.ndarray, destino=None) -> np.ndarray:
    out = np.zeros_like(mask_src, dtype=bool)
    _ys, _xs, yd, xd = _destinos_por_campo(mask_src, vect_field)
    if len(yd) == 0:
        return out
    ok = (labels[yd, xd] > 0) if destino is None else (labels[yd, xd] == int(destino))
    out[yd[ok], xd[ok]] = True
    return out


def _criar_kernels_dlf_circular(raio: int):
    raio = int(max(1, raio))
    yy, xx = np.mgrid[-raio:raio + 1, -raio:raio + 1]
    mask = (xx ** 2 + yy ** 2) <= raio ** 2
    dy = yy[mask].astype(np.float32)
    dx = xx[mask].astype(np.float32)
    n = int(mask.sum())
    X = np.stack([np.ones(n, dtype=np.float32), dy, dx], axis=1)
    G_inv = np.linalg.pinv(X.T @ X).astype(np.float32)
    k0 = mask.astype(np.float32)
    ky = (yy * mask).astype(np.float32)
    kx = (xx * mask).astype(np.float32)
    return k0, ky, kx, G_inv, n


def _erro_dlf_componente(u: np.ndarray, k0: np.ndarray, ky: np.ndarray, kx: np.ndarray, G_inv: np.ndarray) -> np.ndarray:
    u = u.astype(np.float32)
    q0 = cv.filter2D(u, cv.CV_32F, k0, borderType=cv.BORDER_REFLECT_101)
    qy = cv.filter2D(u, cv.CV_32F, ky, borderType=cv.BORDER_REFLECT_101)
    qx = cv.filter2D(u, cv.CV_32F, kx, borderType=cv.BORDER_REFLECT_101)
    beta0 = G_inv[0, 0] * q0 + G_inv[0, 1] * qy + G_inv[0, 2] * qx
    betay = G_inv[1, 0] * q0 + G_inv[1, 1] * qy + G_inv[1, 2] * qx
    betax = G_inv[2, 0] * q0 + G_inv[2, 1] * qy + G_inv[2, 2] * qx
    soma_u2 = cv.filter2D(u * u, cv.CV_32F, k0, borderType=cv.BORDER_REFLECT_101)
    sse = soma_u2 - (beta0 * q0 + betay * qy + betax * qx)
    return np.maximum(sse, 0.0).astype(np.float32)


def _erro_dlf_campo_local(vect_field: np.ndarray, raio: int) -> np.ndarray:
    k0, ky, kx, G_inv, n = _criar_kernels_dlf_circular(raio)
    di = vect_field[..., 0].astype(np.float32)
    dj = vect_field[..., 1].astype(np.float32)
    sse_di = _erro_dlf_componente(di, k0, ky, kx, G_inv)
    sse_dj = _erro_dlf_componente(dj, k0, ky, kx, G_inv)
    erro = np.sqrt((sse_di + sse_dj) / max(1, 2 * n)).astype(np.float32)
    try:
        erro = cv.medianBlur(erro, 3)
    except Exception:
        pass
    return erro


def _mascara_campo_localmente_coerente(vect_field: np.ndarray, mask_base: np.ndarray, parametros: Dict[str, Any]) -> np.ndarray:
    if not np.any(mask_base):
        return np.zeros_like(mask_base, dtype=bool)
    erro = _erro_dlf_campo_local(vect_field, int(parametros["raio_coerencia_campo"]))
    vals = erro[mask_base]
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return np.zeros_like(mask_base, dtype=bool)
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med)))
    lim = max(float(parametros["tolerancia_residuo_campo"]), med + float(parametros["fator_mad_residuo_campo"]) * (mad + 1e-6))
    return mask_base & (erro <= lim)


def _comparar_pixeis_por_campo(imagem_rgb: np.ndarray, src_mask: np.ndarray, dst_mask: np.ndarray, vect_field: np.ndarray, raio: int, limiar_mad_rgb: float, limiar_mad_luma: float, min_pixels: int):
    dst_tolerado = _dilatar_bool(dst_mask, raio)
    ys, xs, yd, xd = _destinos_por_campo(src_mask, vect_field)
    if len(ys) < min_pixels:
        return False, 0.0, float("inf"), float("inf")
    ok = dst_tolerado[yd, xd]
    cobertura = float(np.sum(ok)) / max(1, len(ok))
    if np.sum(ok) < min_pixels:
        return False, cobertura, float("inf"), float("inf")
    ys, xs, yd, xd = ys[ok], xs[ok], yd[ok], xd[ok]
    src = imagem_rgb[ys, xs].astype(np.float32)
    dst = imagem_rgb[yd, xd].astype(np.float32)
    diff = np.abs(src - dst)
    mad_rgb = float(np.mean(diff))
    src_luma = 0.299 * src[:, 0] + 0.587 * src[:, 1] + 0.114 * src[:, 2]
    dst_luma = 0.299 * dst[:, 0] + 0.587 * dst[:, 1] + 0.114 * dst[:, 2]
    mad_luma = float(np.mean(np.abs(src_luma - dst_luma)))
    return (mad_rgb <= limiar_mad_rgb and mad_luma <= limiar_mad_luma), cobertura, mad_rgb, mad_luma

# ============================================================
# Famílias origem/destino
# ============================================================

def _centroide_mask(mask_binaria):
    ys, xs = np.where(mask_binaria)
    if len(ys) == 0:
        return (-1.0, -1.0)
    return (float(np.mean(ys)), float(np.mean(xs)))


def _distancia_centroides(c1, c2):
    if c1[0] < 0 or c2[0] < 0:
        return float("inf")
    return float(np.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2))


def _coef_sobreposicao(mask_a, mask_b):
    area_a = int(np.sum(mask_a))
    area_b = int(np.sum(mask_b))
    if area_a <= 0 or area_b <= 0:
        return 0.0
    return int(np.sum(mask_a & mask_b)) / max(1, min(area_a, area_b))


def _cobertura(mask_menor, mask_maior):
    area = int(np.sum(mask_menor))
    if area <= 0:
        return 0.0
    return int(np.sum(mask_menor & mask_maior)) / area


def _areas_semelhantes(area_a, area_b, limiar):
    maior = max(area_a, area_b, 1)
    menor = min(area_a, area_b)
    return (1.0 - (menor / maior)) <= limiar


def _deslocamentos_compativeis(a, b, parametros):
    tol_base = float(parametros["tolerancia_deslocamento_conflito"])
    fator_var = float(parametros["fator_variacao_campo_compativel"])
    va = np.array([float(a.get("di_med", 0)), float(a.get("dj_med", 0))])
    vb = np.array([float(b.get("di_med", 0)), float(b.get("dj_med", 0))])
    dist_o = _distancia_centroides(a.get("centro_origem", (-1, -1)), b.get("centro_origem", (-1, -1)))
    if not np.isfinite(dist_o):
        dist_o = 0.0
    tol = tol_base + fator_var * dist_o
    return float(np.linalg.norm(va - vb)) <= tol, float(np.linalg.norm(va + vb)) <= tol


def _orientar_masks_para_a(a, b, invertida):
    if invertida:
        return b["destino_mask"], b["origem_mask"]
    return b["origem_mask"], b["destino_mask"]


def _atualizar_metricas_candidato(c):
    c["area_origem"] = int(np.sum(c["origem_mask"]))
    c["area_destino"] = int(np.sum(c["destino_mask"]))
    c["area_total"] = c["area_origem"] + c["area_destino"]
    c["area_menor"] = min(c["area_origem"], c["area_destino"])
    c["centro_origem"] = _centroide_mask(c["origem_mask"])
    c["centro_destino"] = _centroide_mask(c["destino_mask"])
    return c


def _unir_candidatos(a, b, invertida):
    b_o, b_d = _orientar_masks_para_a(a, b, invertida)
    novo = dict(a)
    novo["origem_mask"] = a["origem_mask"] | b_o
    novo["destino_mask"] = a["destino_mask"] | b_d
    novo["votos"] = int(a.get("votos", 0)) + int(b.get("votos", 0))
    wa = max(1, int(a.get("votos", 1)))
    wb = max(1, int(b.get("votos", 1)))
    sinal = -1 if invertida else 1
    novo["di_med"] = int(round((wa * int(a.get("di_med", 0)) + wb * sinal * int(b.get("di_med", 0))) / (wa + wb)))
    novo["dj_med"] = int(round((wa * int(a.get("dj_med", 0)) + wb * sinal * int(b.get("dj_med", 0))) / (wa + wb)))
    return _atualizar_metricas_candidato(novo)


def _relacao_contida_em(a, b, parametros, invertida):
    lim = float(parametros["limiar_contencao_relacao"])
    b_o, b_d = _orientar_masks_para_a(a, b, invertida)
    return _cobertura(a["origem_mask"], b_o) >= lim and _cobertura(a["destino_mask"], b_d) >= lim


def _extra_relevante(base_o, base_d, nova_o, nova_d, parametros):
    min_area = int(parametros["min_area_blob_relacao"])
    lim_extra = float(parametros["limiar_extra_relativo_uniao"])
    extra = int(np.sum(nova_o & (~base_o))) + int(np.sum(nova_d & (~base_d)))
    area_nova = int(np.sum(nova_o)) + int(np.sum(nova_d))
    return extra >= min_area or (area_nova > 0 and extra / area_nova >= lim_extra)


def _sobreposicao_relacoes(a, b, invertida):
    b_o, b_d = _orientar_masks_para_a(a, b, invertida)
    return min(_coef_sobreposicao(a["origem_mask"], b_o), _coef_sobreposicao(a["destino_mask"], b_d))


def _relacoes_duplicadas(a, b, parametros):
    lim_ov = float(parametros["limiar_sobreposicao_duplicata"])
    lim_area = float(parametros["limiar_area_semelhante"])
    tol_cent = float(parametros["tolerancia_centroide"])
    mesmo_par = ((a["origem_label"] == b["origem_label"] and a["destino_label"] == b["destino_label"]) or
                 (a["origem_label"] == b["destino_label"] and a["destino_label"] == b["origem_label"]))
    mesma, invertida = _deslocamentos_compativeis(a, b, parametros)
    inv = bool(invertida and not mesma)
    b_o, b_d = _orientar_masks_para_a(a, b, inv)
    ov = _coef_sobreposicao(a["origem_mask"], b_o) >= lim_ov and _coef_sobreposicao(a["destino_mask"], b_d) >= lim_ov
    centros = (_distancia_centroides(a["centro_origem"], _centroide_mask(b_o)) <= tol_cent and
               _distancia_centroides(a["centro_destino"], _centroide_mask(b_d)) <= tol_cent)
    areas = _areas_semelhantes(int(a["area_total"]), int(b["area_total"]), lim_area)
    return bool((mesmo_par and (areas or ov)) or ((mesma or invertida) and areas and (ov or centros)))


def _filtrar_relacoes_duplicadas(candidatos, parametros):
    ordenados = sorted(candidatos, key=lambda c: (int(c["votos"]), int(c["area_total"])), reverse=True)
    mantidos = []
    for cand in ordenados:
        duplicata = False
        for idx, atual in enumerate(mantidos):
            if _relacoes_duplicadas(cand, atual, parametros):
                duplicata = True
                if (int(cand["votos"]), int(cand["area_total"]), int(cand["area_menor"])) > (int(atual["votos"]), int(atual["area_total"]), int(atual["area_menor"])):
                    mantidos[idx] = cand
                break
        if not duplicata:
            mantidos.append(cand)
    return mantidos


def _resolver_conflitos_por_sobreposicao(candidatos, parametros):
    if len(candidatos) <= 1:
        return candidatos
    candidatos = sorted(candidatos, key=lambda c: (int(c["votos"]), int(c["area_total"])), reverse=True)
    max_iter = int(parametros["max_iter_resolucao_conflitos"])
    lim_ov = float(parametros["limiar_sobreposicao_conflito"])
    for _ in range(max_iter):
        mudou = False
        remover = set()
        adicionar = []
        n = len(candidatos)
        for i in range(n):
            if i in remover:
                continue
            for j in range(i + 1, n):
                if j in remover:
                    continue
                a, b = candidatos[i], candidatos[j]
                mesma, invertida = _deslocamentos_compativeis(a, b, parametros)
                if not (mesma or invertida):
                    continue
                inv = bool(invertida and not mesma)
                if _relacao_contida_em(a, b, parametros, inv) and not _extra_relevante(b["origem_mask"], b["destino_mask"], a["origem_mask"], a["destino_mask"], parametros):
                    remover.add(i)
                    mudou = True
                    break
                if _relacao_contida_em(b, a, parametros, inv):
                    b_o, b_d = _orientar_masks_para_a(a, b, inv)
                    if not _extra_relevante(a["origem_mask"], a["destino_mask"], b_o, b_d, parametros):
                        remover.add(j)
                        mudou = True
                        continue
                if _sobreposicao_relacoes(a, b, inv) >= lim_ov:
                    b_o, b_d = _orientar_masks_para_a(a, b, inv)
                    extra_a = _extra_relevante(b_o, b_d, a["origem_mask"], a["destino_mask"], parametros)
                    extra_b = _extra_relevante(a["origem_mask"], a["destino_mask"], b_o, b_d, parametros)
                    if extra_a or extra_b:
                        adicionar.append(_unir_candidatos(a, b, inv))
                        remover.add(i)
                        remover.add(j)
                        mudou = True
                        break
        if not mudou:
            break
        candidatos = [c for idx, c in enumerate(candidatos) if idx not in remover]
        candidatos.extend(adicionar)
        candidatos = _filtrar_relacoes_duplicadas(candidatos, parametros)
        candidatos = sorted(candidatos, key=lambda c: (int(c["votos"]), int(c["area_total"])), reverse=True)
    return candidatos


def _ponte_entre_masks(mask_a, mask_b, raio):
    a = _dilatar_bool(mask_a, raio)
    b = _dilatar_bool(mask_b, raio)
    return (a & b & (~mask_a) & (~mask_b)).astype(bool)


def _masks_tocam_ou_sobrepoem(mask_a, mask_b, raio):
    return bool(np.any(mask_a & mask_b) or np.any(_dilatar_bool(mask_a, raio) & mask_b))


def _validar_ponte_intermediaria(origem_a, origem_b, destino_a, destino_b, parametros):
    raio = int(parametros["raio_contato_familia"])
    min_area = int(parametros["min_area_ponte_familia"])
    return int(np.sum(_ponte_entre_masks(origem_a, origem_b, raio))) >= min_area and int(np.sum(_ponte_entre_masks(destino_a, destino_b, raio))) >= min_area


def _familias_adjacentes_e_compativeis(a, b, parametros):
    mesma, invertida = _deslocamentos_compativeis(a, b, parametros)
    if not (mesma or invertida):
        return False, False
    inv = bool(invertida and not mesma)
    b_o, b_d = _orientar_masks_para_a(a, b, inv)
    raio = int(parametros["raio_contato_familia"])
    if _masks_tocam_ou_sobrepoem(a["origem_mask"], b_o, raio) and _masks_tocam_ou_sobrepoem(a["destino_mask"], b_d, raio):
        return True, inv
    return bool(_validar_ponte_intermediaria(a["origem_mask"], b_o, a["destino_mask"], b_d, parametros)), inv


def _agrupar_familias_por_adjacencia(candidatos, parametros):
    if len(candidatos) <= 1:
        return candidatos
    candidatos = sorted(candidatos, key=lambda c: (int(c["area_total"]), int(c["votos"])), reverse=True)
    for _ in range(int(parametros["max_iter_agrupamento_familias"])):
        mudou = False
        usados = set()
        novos = []
        n = len(candidatos)
        i = 0
        while i < n:
            if i in usados:
                i += 1
                continue
            atual = candidatos[i]
            usados.add(i)
            houve = True
            while houve:
                houve = False
                for j in range(n):
                    if j in usados:
                        continue
                    unir, inv = _familias_adjacentes_e_compativeis(atual, candidatos[j], parametros)
                    if unir:
                        atual = _unir_candidatos(atual, candidatos[j], inv)
                        usados.add(j)
                        mudou = True
                        houve = True
            novos.append(atual)
            i += 1
        candidatos = _filtrar_relacoes_duplicadas(novos, parametros)
        candidatos = sorted(candidatos, key=lambda c: (int(c["area_total"]), int(c["votos"])), reverse=True)
        if not mudou:
            break
    return candidatos


def _familia_tem_correspondencia_visual(cand: Dict[str, Any], imagem_rgb: np.ndarray, vect_field: np.ndarray, parametros: Dict[str, Any]) -> bool:
    origem, destino = cand["origem_mask"], cand["destino_mask"]
    raio = int(parametros["raio_validacao_visual_familia"])
    min_pixels = int(parametros["min_pixels_validacao_visual"])
    min_cov = float(parametros["min_cobertura_campo_familia"])
    min_cov_dir = float(parametros["min_cobertura_campo_direcional"])
    lim_rgb = float(parametros["limiar_mad_rgb_familia"])
    lim_luma = float(parametros["limiar_mad_luma_familia"])
    ok_od, cov_od, _, _ = _comparar_pixeis_por_campo(imagem_rgb, origem, destino, vect_field, raio, lim_rgb, lim_luma, min_pixels)
    ok_do, cov_do, _, _ = _comparar_pixeis_por_campo(imagem_rgb, destino, origem, vect_field, raio, lim_rgb, lim_luma, min_pixels)
    cov_ok = (cov_od >= min_cov and cov_do >= min_cov_dir) or (cov_do >= min_cov and cov_od >= min_cov_dir)
    return bool(cov_ok and (ok_od or ok_do))


def _filtrar_familias_sem_correspondencia_visual(candidatos: List[Dict[str, Any]], imagem_rgb: np.ndarray, vect_field: np.ndarray, parametros: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [c for c in candidatos if _familia_tem_correspondencia_visual(c, imagem_rgb, vect_field, parametros)]


def _mascara_por_campo(labels, imagem_rgb, mask_origem, destino, vect_field, parametros, permitir_fallback_mascara=True):
    destino_exato = _mascara_destino_por_campo(mask_origem, vect_field, labels, destino=destino)
    if np.any(destino_exato):
        return destino_exato
    if permitir_fallback_mascara:
        fallback = _mascara_destino_por_campo(mask_origem, vect_field, labels, destino=None)
        if _mascara_eh_homogenea(imagem_rgb, fallback, float(parametros["limiar_homogeneidade_fallback"]), int(parametros["min_votos_relacao"])):
            return fallback
    return np.zeros_like(labels, dtype=bool)


def _expandir_relacao_origem(labels, vect_field, origem, destino, origem_seed, destino_label_por_pixel, parametros):
    if not np.any(origem_seed):
        return origem_seed.astype(bool), 0, 0
    raio = int(parametros["raio_expansao"])
    min_area = int(parametros["min_area_blob_relacao"])
    base = labels == origem
    votos = base & (destino_label_por_pixel == destino)
    coerente = _mascara_campo_localmente_coerente(vect_field, base, parametros)
    suporte = _manter_componentes_que_tocam_seed(coerente & base, origem_seed | votos, raio)
    suporte = suporte | origem_seed | votos
    if raio > 0:
        k = 2 * raio + 1
        suporte = cv.morphologyEx(suporte.astype(np.uint8), cv.MORPH_CLOSE, cv.getStructuringElement(cv.MORPH_ELLIPSE, (k, k))).astype(bool)
        suporte = suporte & base
    suporte = _remover_blobs_pequenos(suporte, min_area)
    di_med, dj_med = _vetor_mediano_mask(suporte | origem_seed, vect_field)
    return suporte, di_med, dj_med


def _criar_candidatos_relacoes(labels, imagem_rgb, vect_field, destino_label_por_pixel, destino_y_por_pixel, destino_x_por_pixel, relacoes_fortes, parametros):
    hgt, wid = labels.shape[:2]
    min_area = int(parametros["min_area_blob_relacao"])
    raio = int(parametros["raio_expansao"])
    candidatos = []
    for origem, destino, n_votos in relacoes_fortes:
        origem_seed = (labels == origem) & (destino_label_por_pixel == destino)
        if not np.any(origem_seed):
            continue
        origem_pixels, di_med, dj_med = _expandir_relacao_origem(labels, vect_field, origem, destino, origem_seed, destino_label_por_pixel, parametros)
        if not np.any(origem_pixels):
            continue
        destino_pixels = _mascara_por_campo(labels, imagem_rgb, origem_pixels, destino, vect_field, parametros, True)
        yd = destino_y_por_pixel[origem_seed]
        xd = destino_x_por_pixel[origem_seed]
        ok = (yd >= 0) & (yd < hgt) & (xd >= 0) & (xd < wid)
        yd = yd[ok]
        xd = xd[ok]
        if len(yd) > 0:
            destino_pixels[yd, xd] = True
        if np.any(destino_pixels) and raio > 0:
            k = 2 * raio + 1
            destino_pixels = cv.morphologyEx(destino_pixels.astype(np.uint8), cv.MORPH_CLOSE, cv.getStructuringElement(cv.MORPH_ELLIPSE, (k, k))).astype(bool)
            exato = _remover_blobs_pequenos(destino_pixels & (labels == destino), min_area)
            if np.any(exato):
                destino_pixels = exato
            else:
                fallback = destino_pixels & (labels > 0)
                if _mascara_eh_homogenea(imagem_rgb, fallback, float(parametros["limiar_homogeneidade_fallback"]), int(parametros["min_votos_relacao"])):
                    destino_pixels = _remover_blobs_pequenos(fallback, min_area)
                else:
                    destino_pixels = np.zeros_like(labels, dtype=bool)
        if not np.any(destino_pixels):
            continue
        if int(np.sum(origem_pixels)) < min_area or int(np.sum(destino_pixels)) < min_area:
            continue
        cand = {"origem_label": int(origem), "destino_label": int(destino), "votos": int(n_votos), "di_med": int(di_med), "dj_med": int(dj_med), "origem_mask": origem_pixels, "destino_mask": destino_pixels}
        candidatos.append(_atualizar_metricas_candidato(cand))
    return candidatos

# ============================================================
# Visualização original restaurada
# ============================================================

def _colorir_componentes_mascara(imagem_rgb, mask, vect_field, p, min_dn, alpha=ALPHA_REGIAO):
    saida = imagem_rgb.astype(np.float32)
    hgt, wid = imagem_rgb.shape[:2]
    parametros = estima_parametros_visualizacao(wid, hgt, p, min_dn)
    _status_etapa(9, 12, "Rotulando componentes conectados da máscara inicial.")
    n_labels, labels, _stats, _ = cv.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n_labels <= 1 or not np.any(labels > 0):
        return imagem_rgb.copy()
    destino_label_por_pixel = np.zeros_like(labels, dtype=np.int32)
    destino_y_por_pixel = np.full_like(labels, -1, dtype=np.int32)
    destino_x_por_pixel = np.full_like(labels, -1, dtype=np.int32)
    votos = {}
    ys, xs = np.where(labels > 0)
    for y, x in zip(ys, xs):
        origem = int(labels[y, x])
        if origem <= 0:
            continue
        di = int(vect_field[y, x, 0])
        dj = int(vect_field[y, x, 1])
        yd = y + di
        xd = x + dj
        if yd < 0 or yd >= hgt or xd < 0 or xd >= wid:
            continue
        destino = int(labels[yd, xd])
        if destino <= 0 or destino == origem:
            continue
        destino_label_por_pixel[y, x] = destino
        destino_y_por_pixel[y, x] = yd
        destino_x_por_pixel[y, x] = xd
        votos[(origem, destino)] = votos.get((origem, destino), 0) + 1
    _status_etapa(10, 12, "Computando votos origem/destino a partir do campo de deslocamentos.")
    min_votos = int(parametros["min_votos_relacao"])
    relacoes = [(o, d, v) for (o, d), v in votos.items() if v >= min_votos]
    if not relacoes:
        return imagem_rgb.copy()
    relacoes.sort(key=lambda item: item[2], reverse=True)
    _status_etapa(11, 12, "Criando, agrupando, resolvendo conflitos e validando famílias.")
    candidatos = _criar_candidatos_relacoes(labels, imagem_rgb, vect_field, destino_label_por_pixel, destino_y_por_pixel, destino_x_por_pixel, relacoes, parametros)
    if not candidatos:
        return imagem_rgb.copy()
    candidatos = _agrupar_familias_por_adjacencia(candidatos, parametros)
    candidatos = _resolver_conflitos_por_sobreposicao(candidatos, parametros)
    candidatos = _filtrar_relacoes_duplicadas(candidatos, parametros)
    candidatos = _filtrar_familias_sem_correspondencia_visual(candidatos, imagem_rgb, vect_field, parametros)
    if not candidatos:
        return imagem_rgb.copy()
    candidatos = sorted(candidatos, key=lambda c: int(c["area_total"]), reverse=True)
    cores = _gerar_cores_distintas(len(candidatos))
    raio_o = int(parametros["raio_pintura_origem"])
    raio_d = int(parametros["raio_pintura_destino"])
    k_close = int(parametros["kernel_fechamento"])
    blur = int(parametros["blur_alpha"])
    for idx, cand in enumerate(candidatos):
        cor = np.array(cores[idx], dtype=np.float32)
        alpha_o = _preparar_mascara_visual_relacao(cand["origem_mask"], raio_o, k_close, blur) * float(alpha)
        saida = alpha_o[..., None] * cor + (1.0 - alpha_o[..., None]) * saida
        alpha_d = _preparar_mascara_visual_relacao(cand["destino_mask"], raio_d, k_close, blur) * float(alpha)
        saida = alpha_d[..., None] * cor + (1.0 - alpha_d[..., None]) * saida
    return np.clip(saida, 0, 255).astype(np.uint8)


def _criar_imagem_resultado(imagem_rgb, mask, vect_field, p, min_dn):
    if mask is None or not np.any(mask):
        return imagem_rgb.copy()
    return _colorir_componentes_mascara(imagem_rgb, mask, vect_field, p, min_dn, alpha=ALPHA_REGIAO)

# ============================================================
# Pipeline
# ============================================================

def _redimensionar_para_patchmatch(imagem_rgb: np.ndarray, max_lado: int):
    hgt, wid = imagem_rgb.shape[:2]
    escala = min(1.0, float(max_lado) / float(max(hgt, wid)))
    if escala >= 1.0:
        return imagem_rgb, 1.0
    nova_largura = max(1, int(round(wid * escala)))
    nova_altura = max(1, int(round(hgt * escala)))
    imagem_proc = cv.resize(imagem_rgb, (nova_largura, nova_altura), interpolation=cv.INTER_AREA)
    return imagem_proc, escala


def _executar_patchmatch(image_float: np.ndarray, p: int, min_dn: int, n_rs_candidates: int, n_iter: int, zernike_threads: int):
    zernike_filters, cache_hit = _obter_zernike_filters_cache(p, MAX_ZRD)
    if cache_hit:
        _status_etapa(4, 12, f"Reutilizando filtros de Zernike do cache (p={p}, max_zrd={MAX_ZRD}).")
    else:
        _status_etapa(4, 12, f"Calculando filtros de Zernike e armazenando no cache (p={p}, max_zrd={MAX_ZRD}).")
    _status_etapa(5, 12, f"Inicializando PatchMatch e calculando momentos de Zernike ({zernike_threads} thread(s)).")
    pm = PatchMatch(
        image_float,
        p=p,
        max_zrd=MAX_ZRD,
        min_dn=min_dn,
        n_rs_candidates=n_rs_candidates,
        zernike_filters=zernike_filters,
        zernike_threads=zernike_threads,
    )
    for i in range(n_iter):
        _status_etapa(6, 12, f"Executando PatchMatch: iteração {i + 1}/{n_iter}.")
        pm.iterate()
    return pm


def _processar_imagem(caminho_imagem: str, pasta_saida: str, controls: Dict[str, Any]):
    caminho = Path(caminho_imagem)
    nome_base = caminho.stem
    _status_etapa(1, 12, f"{caminho.name}: lendo imagem de entrada.")
    imagem_rgb = _abrir_imagem_rgb(str(caminho))
    hgt, wid = imagem_rgb.shape[:2]
    _status_etapa(2, 12, f"{caminho.name}: estimando parâmetros automáticos e lendo controles da UI.")
    p = _get_int(controls, "p", P_PADRAO, 2, 20)
    n_rs_candidates = _get_int(controls, "n_rs_candidates", N_RS_CANDIDATES_PADRAO, 1, 20)
    n_iter = _get_int(controls, "n_iter", N_ITER_PADRAO, 1, MAX_N_ITERATIONS)
    max_lado = _get_int(controls, "max_lado_patchmatch", MAX_LADO_PATCHMATCH_PADRAO, 600, 6000)
    zernike_threads = _get_int(controls, "zernike_threads", ZERNIKE_THREADS_PADRAO, 1, max(1, os.cpu_count() or 1))

    imagem_proc, escala = _redimensionar_para_patchmatch(imagem_rgb, max_lado)
    hgt_proc, wid_proc = imagem_proc.shape[:2]
    min_dn = estima_min_dn(wid_proc, hgt_proc)
    min_region = estima_min_region_size(wid_proc, hgt_proc)

    if escala < 1.0:
        _status_etapa(3, 12, f"{caminho.name}: redimensionando para {wid_proc}x{hgt_proc} antes do PatchMatch (escala={escala:.3f}).")
    else:
        _status_etapa(3, 12, f"{caminho.name}: usando resolução original {wid_proc}x{hgt_proc} no PatchMatch.")

    if min(hgt_proc, wid_proc) < 2 * p + 1:
        _status(f"{caminho.name}: imagem muito pequena para p={p}. Salvando imagem original.")
        resultado = imagem_rgb.copy()
    else:
        _status(f"{caminho.name}: PatchMatch sem Numba (p={p}, n_rs_candidates={n_rs_candidates}, n_iter={n_iter}, max_lado={max_lado}).")
        pm = _executar_patchmatch(imagem_proc.astype(np.float32), p, min_dn, n_rs_candidates, n_iter, zernike_threads)
        _status_etapa(7, 12, "Calculando máscara inicial pela coerência do campo de deslocamentos.")
        mask = compute_mask_1(pm.vect_field, pm.m, pm.n, pm.p, min_region).astype(bool)
        _status_etapa(8, 12, "Gerando visualização por famílias origem/destino.")
        resultado_proc = _criar_imagem_resultado(imagem_proc, mask, pm.vect_field, pm.p, min_dn)
        if escala < 1.0:
            resultado = cv.resize(resultado_proc, (wid, hgt), interpolation=cv.INTER_LINEAR)
        else:
            resultado = resultado_proc

    tmp = os.path.join(os.getenv("TEMP") or pasta_saida, f"{PREFIXO_SAIDA}PatchMatch_{nome_base}.tmp.{EXTENSAO_SAIDA}")
    final = os.path.join(pasta_saida, f"{PREFIXO_SAIDA}PatchMatch_{nome_base}.{EXTENSAO_SAIDA}")
    _status_etapa(12, 12, f"{caminho.name}: salvando imagem de resultado.")
    _salvar_rgb(tmp, resultado)
    saida = replace_com_incremento(tmp, final)
    _status(f"{caminho.name}: resultado salvo em {saida}")

# ============================================================
# Entrada PeriTASK
# ============================================================

def executar(arquivos, controls, pasta_saida):
    if controls is None:
        controls = {}
    imagens = selecionar_arquivos(arquivos, "imagem")
    imagens = filtrar_arquivos(imagens, prefixo=PREFIXO_SAIDA, extensao=EXTENSAO_SAIDA)
    if not imagens:
        _status("Nenhuma imagem compatível foi selecionada.")
        _progress(100)
        return
    Path(pasta_saida).mkdir(parents=True, exist_ok=True)
    total = len(imagens)
    ultimo = -1
    _status(f"Iniciando PatchMatch em {total} imagem(ns).")
    for i, imagem in enumerate(imagens, start=1):
        try:
            _status(f"Processando imagem {i}/{total}: {Path(imagem).name}")
            _processar_imagem(imagem, pasta_saida, controls)
        except Exception as exc:
            _status(f"Erro ao processar {Path(imagem).name}: {exc}")
            _status(traceback.format_exc())
        prog = int((i / total) * 100)
        if prog != ultimo:
            _progress(prog)
            ultimo = prog
    _progress(100)

# ============================================================
# Execução direta
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Detector copy-paste PatchMatch/Zernike DLF-like sem Numba - PeriTASK")
    parser.add_argument("imagens", nargs="+", help="Imagem(ns) de entrada")
    parser.add_argument("--saida", default=".", help="Pasta de saída")
    parser.add_argument("--p", default=str(P_PADRAO), help="Raio do patch. Default: 5")
    parser.add_argument("--n-rs-candidates", default=str(N_RS_CANDIDATES_PADRAO), help="Candidatos na busca aleatória. Default: 5")
    parser.add_argument("--n-iter", default=str(N_ITER_PADRAO), help="Número de iterações. Default: 5")
    parser.add_argument("--max-lado-patchmatch", default=str(MAX_LADO_PATCHMATCH_PADRAO), help="Maior lado usado internamente no PatchMatch. Default: 1400")
    parser.add_argument("--zernike-threads", default=str(ZERNIKE_THREADS_PADRAO), help="Threads para convoluções Zernike. Default: até 4")
    args = parser.parse_args()
    executar(
        args.imagens,
        {
            "p": args.p,
            "n_rs_candidates": args.n_rs_candidates,
            "n_iter": args.n_iter,
            "max_lado_patchmatch": args.max_lado_patchmatch,
            "zernike_threads": args.zernike_threads,
        },
        args.saida,
    )
