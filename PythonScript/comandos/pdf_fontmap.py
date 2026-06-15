"""
Comando importado do projeto https://github.com/khyale/pdf-fontmap
"""

import argparse
import colorsys
import fitz
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict


# ══════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════

CLASSES_COR = {
    "dominante":  "#2176AE",
    "secundaria": "#57B8FF",
    "rara":       "#FBB13C",
    "outlier":    "#D62246",
    "unica":      "#7B2D8B",
}

CLASSES_LABEL = {
    "dominante":  "Dominante  (> 40%)",
    "secundaria": "Secundaria (5-40%)",
    "rara":       "Rara       (1-5%)",
    "outlier":    "Outlier    (< 1%)",
    "unica":      "Unica      (1 span)",
}

CLASSES_RGBA = {
    "dominante":  (33,  118, 174,  55),
    "secundaria": (87,  184, 255,  65),
    "rara":       (251, 177,  60, 120),
    "outlier":    (214,  34,  70, 160),
    "unica":      (123,  45, 139, 175),
}

LIMIARES_FREQ = {"dominante": 0.40, "secundaria": 0.05, "rara": 0.01}
DPI_PADRAO    = 150


# ══════════════════════════════════════════════════════════════
# ESTRUTURAS DE DADOS
# ══════════════════════════════════════════════════════════════

@dataclass
class SpanTipografico:
    pagina: int
    bloco_idx: int
    linha_idx: int
    span_idx: int
    texto: str
    font_name: str
    fonte_tamanho: float
    estilo: str
    fonte_flags: int
    fonte_cor: str
    bbox_x0: float
    bbox_y0: float
    bbox_x1: float
    bbox_y1: float
    largura_bbox: float
    altura_bbox: float
    area_bbox: float
    is_bold: bool
    is_italic: bool
    is_monospace: bool
    is_serif: bool
    origem_x: float
    origem_y: float
    subset_prefix: str
    font_xref: int


@dataclass
class EvidenciaFonte:
    style_id: str
    font_name: str
    tamanho_pt: float
    estilo: str
    cor_hex: str
    classe: str
    total_spans: int
    span_pct: float
    area_cobertura_pct: float
    isolamento_medio: float
    isolamento_max: float
    is_embutida: bool
    subset_prefix: str
    cor_hsl: tuple
    paginas_encontradas: list


# ══════════════════════════════════════════════════════════════
# AUXILIARES
# ══════════════════════════════════════════════════════════════

def _limpar_nome_fonte(nome: str) -> str:
    if len(nome) > 7 and nome[6] == "+" and nome[:6].isupper():
        nome = nome[7:]
    if nome.startswith("*"):
        nome = nome[1:]
    if len(nome) > 2 and nome[-1] in "HV" and nome[-2] == "-":
        idx = nome[:-2].rfind("-")
        if idx > 0:
            nome = nome[:idx]
    idx = nome.rfind("-")
    if idx > 0 and nome[idx + 1:].isdigit() and len(nome[idx + 1:]) >= 4:
        nome = nome[:idx]
    return nome


def _extrair_subset(nome_raw: str) -> str:
    if len(nome_raw) > 7 and nome_raw[6] == "+" and nome_raw[:6].isupper():
        return nome_raw[:6]
    return ""


def _decodificar_flags(flags: int) -> dict:
    return {
        "is_bold":      bool(flags & 16),
        "is_italic":    bool(flags & 2),
        "is_monospace": bool(flags & 8),
        "is_serif":     bool(flags & 4),
    }


def _estilo_str(is_bold: bool, is_italic: bool, is_monospace: bool) -> str:
    if is_monospace:           return "monospace"
    if is_bold and is_italic:  return "bold-italic"
    if is_bold:                return "bold"
    if is_italic:              return "italic"
    return "regular"


def _cor_para_hex(cor_int: int) -> str:
    return f"#{(cor_int >> 16) & 0xFF:02X}{(cor_int >> 8) & 0xFF:02X}{cor_int & 0xFF:02X}"


def _hex_para_fitz(hex_cor: str) -> tuple:
    h = hex_cor.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def _classificar(n: int, freq: float) -> str:
    if n == 1:                              return "unica"
    if freq >= LIMIARES_FREQ["dominante"]:  return "dominante"
    if freq >= LIMIARES_FREQ["secundaria"]: return "secundaria"
    if freq >= LIMIARES_FREQ["rara"]:       return "rara"
    return "outlier"


def gerar_paleta_hsl(ids: list) -> dict:
    """Paleta HSL para lista de IDs (style_id ou font_name)."""
    NCORES = 15
    chaves = sorted(set(ids))
    paleta = {}
    for i, k in enumerate(chaves):
        matiz    = (i % NCORES) / NCORES
        r, g, b  = colorsys.hls_to_rgb(matiz, 0.55, 0.78)
        alpha    = 170 if i < NCORES else (100 if i < NCORES * 2 else 55)
        paleta[k] = (int(r * 255), int(g * 255), int(b * 255), alpha)
    return paleta


def parse_paginas(s: str) -> list:
    paginas = set()
    for parte in s.split(","):
        parte = parte.strip()
        if "-" in parte:
            a, b = parte.split("-", 1)
            paginas.update(range(int(a), int(b) + 1))
        else:
            paginas.add(int(parte))
    return sorted(paginas)


def _garantir_subset_col(df: pd.DataFrame) -> pd.DataFrame:
    if "subset_prefix" not in df.columns:
        df["subset_prefix"] = ""
    df["subset_prefix"] = df["subset_prefix"].fillna("").astype(str)
    return df


def ler_csv_pericial(caminho) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return pd.read_csv(Path(caminho), encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Nao foi possivel decodificar '{caminho}'.")


def _pil_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Carrega fonte para legendas Pillow. Compativel com Windows e Linux."""
    if bold:
        caminhos = [
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        caminhos = [
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        ]
    for c in caminhos:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════
# EXTRATOR
# ══════════════════════════════════════════════════════════════

class ExtratorFontesPDF:
    def __init__(self, caminho_pdf, paginas_base0=None, min_tamanho_texto=1):
        self.caminho_pdf            = Path(caminho_pdf)
        self.paginas_base0          = paginas_base0
        self.min_tamanho_texto      = min_tamanho_texto
        self._spans                 = []
        self._df                    = None
        self._fontes_embutidas      = set()
        self._fontes_embutidas_xref = set()
        self._subset_map            = {}
        self._metadados_doc         = {}

    def extrair(self) -> pd.DataFrame:
        with fitz.open(self.caminho_pdf) as doc:
            self._extrair_metadados(doc)
            self._mapear_fontes_embutidas(doc)
            paginas = self.paginas_base0 if self.paginas_base0 is not None else range(doc.page_count)
            for n in paginas:
                n = int(n)
                if 0 <= n < doc.page_count:
                    self._processar_pagina(doc[n], n)
                else:
                    print(f"  Aviso: pagina {n+1} fora do intervalo ({doc.page_count} pags).")
        self._df = self._montar_dataframe()
        return self._df

    def _extrair_metadados(self, doc):
        meta = doc.metadata or {}
        self._metadados_doc = {
            "titulo":                meta.get("title", ""),
            "criador":               meta.get("creator", ""),
            "produtor":              meta.get("producer", ""),
            "data_criacao":          meta.get("creationDate", ""),
            "data_modificacao":      meta.get("modDate", ""),
            "num_paginas":           doc.page_count,
            "revisoes_incrementais": self._detectar_revisoes(),
        }

    def _detectar_revisoes(self) -> bool:
        try:
            with open(self.caminho_pdf, "rb") as f:
                return f.read().count(b"%%EOF") > 1
        except Exception:
            return False

    def _mapear_fontes_embutidas(self, doc):
        for n in range(doc.page_count):
            for fonte in doc[n].get_fonts(full=True):
                ext      = (fonte[1] or "").strip().lower()
                nome_raw = fonte[3] or ""
                nome     = _limpar_nome_fonte(nome_raw)
                subset   = _extrair_subset(nome_raw)
                if ext and ext != "n/a":
                    self._fontes_embutidas.add(nome)
                    self._fontes_embutidas_xref.add(int(fonte[0]))
                    if nome not in self._subset_map:
                        self._subset_map[nome] = subset

    def _processar_pagina(self, page, num_pag: int):
        xref_map = {
            _limpar_nome_fonte(fonte[3] or ""): int(fonte[0])
            for fonte in page.get_fonts(full=True)
            if fonte[0] > 0
        }
        dic = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for b_i, bloco in enumerate(dic.get("blocks", [])):
            if bloco.get("type") != 0:
                continue
            for l_i, linha in enumerate(bloco.get("lines", [])):
                for s_i, span in enumerate(linha.get("spans", [])):
                    self._processar_span(span, num_pag, b_i, l_i, s_i, xref_map)

    def _processar_span(self, span, pagina, b_i, l_i, s_i, xref_map=None):
        texto = span.get("text", "").strip()
        if len(texto) < self.min_tamanho_texto:
            return
        nome_raw  = span.get("font", "Desconhecida")
        nome      = _limpar_nome_fonte(nome_raw)
        font_xref = (xref_map or {}).get(nome, 0)
        subset    = self._subset_map.get(nome, _extrair_subset(nome_raw))
        flags     = _decodificar_flags(span.get("flags", 0))
        estilo    = _estilo_str(flags["is_bold"], flags["is_italic"], flags["is_monospace"])
        bbox      = span.get("bbox", (0, 0, 0, 0))
        orig      = span.get("origin", (bbox[0], bbox[1]))
        larg      = round(bbox[2] - bbox[0], 2)
        alt       = round(bbox[3] - bbox[1], 2)
        self._spans.append(SpanTipografico(
            pagina=pagina + 1, bloco_idx=b_i, linha_idx=l_i, span_idx=s_i,
            texto=texto[:120], font_name=nome,
            fonte_tamanho=round(span.get("size", 0.0), 2),
            estilo=estilo, fonte_flags=span.get("flags", 0),
            fonte_cor=_cor_para_hex(span.get("color", 0)),
            bbox_x0=round(bbox[0], 2), bbox_y0=round(bbox[1], 2),
            bbox_x1=round(bbox[2], 2), bbox_y1=round(bbox[3], 2),
            largura_bbox=larg, altura_bbox=alt, area_bbox=round(larg * alt, 2),
            is_bold=flags["is_bold"], is_italic=flags["is_italic"],
            is_monospace=flags["is_monospace"], is_serif=flags["is_serif"],
            origem_x=round(orig[0], 2), origem_y=round(orig[1], 2),
            subset_prefix=subset, font_xref=font_xref,
        ))

    def _montar_dataframe(self) -> pd.DataFrame:
        if not self._spans:
            return pd.DataFrame()
        df = pd.DataFrame([asdict(s) for s in self._spans])
        df = _garantir_subset_col(df)
        sub_label      = df["subset_prefix"].where(df["subset_prefix"] != "", "nosub")
        df["style_id"] = (df["font_name"] + "@"
                          + sub_label + "@"
                          + df["estilo"] + "@"
                          + df["fonte_tamanho"].round(1).astype(str) + "pt@"
                          + df["fonte_cor"])
        df["is_embutida"] = df["font_xref"].isin(self._fontes_embutidas_xref)
        df["isolamento"]  = self._calcular_isolamento(df)
        return df

    def _calcular_isolamento(self, df: pd.DataFrame) -> pd.Series:
        TOL_Y     = 4.0
        FATOR_GAP = 5.0
        iso = pd.Series(0.0, index=df.index, dtype=float)
        for pagina in sorted(df["pagina"].unique()):
            df_pag = df[df["pagina"] == pagina]
            if df_pag.empty:
                continue
            ordenado    = df_pag.sort_values(["bbox_y0", "bbox_x0"])
            linhas: list = []
            linha_atual: list = []
            y_ref = None
            for orig_idx, row in ordenado.iterrows():
                y = float(row["bbox_y0"])
                span_info = (orig_idx, str(row["style_id"]),
                             float(row["bbox_x0"]), float(row["bbox_x1"]),
                             float(row["fonte_tamanho"]))
                if y_ref is None or abs(y - y_ref) <= TOL_Y:
                    linha_atual.append(span_info)
                    if y_ref is None:
                        y_ref = y
                else:
                    if linha_atual:
                        linhas.append(linha_atual)
                    linha_atual = [span_info]
                    y_ref = y
            if linha_atual:
                linhas.append(linha_atual)
            for linha in linhas:
                n = len(linha)
                if n <= 1:
                    continue
                for i in range(n):
                    orig_idx, fid, x0_i, x1_i, tam_i = linha[i]
                    limiar = tam_i * FATOR_GAP
                    dif = 0; viz = 0
                    if i > 0:
                        _, fid_esq, _, x1_esq, _ = linha[i - 1]
                        if x0_i - x1_esq <= limiar:
                            viz += 1
                            if fid_esq != fid:
                                dif += 1
                    if i < n - 1:
                        _, fid_dir, x0_dir, _, _ = linha[i + 1]
                        if x0_dir - x1_i <= limiar:
                            viz += 1
                            if fid_dir != fid:
                                dif += 1
                    iso[orig_idx] = dif / viz if viz > 0 else 1.0
        return iso

    def salvar_csv(self, caminho) -> bool:
        """Salva CSV. Retorna False sem salvar se ja existir."""
        caminho = Path(caminho)
        if caminho.exists():
            print(f"  [EXISTENTE] {caminho} — ignorado")
            return False
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._df.to_csv(caminho, index=False, encoding="utf-8-sig")
        print(f"  CSV salvo em: {caminho}")
        return True

    def imprimir_resumo(self):
        def _val(v): return v if v and str(v).strip() else "(ausente)"
        df = self._df
        m  = self._metadados_doc
        n_emb = len(self._fontes_embutidas)
        n_ext = max(df["font_name"].nunique() - n_emb, 0)
        rev   = "[ATENCAO] SIM — possivel edicao posterior" \
                if m.get("revisoes_incrementais") else "Nao detectadas"
        print("\n" + "=" * 65)
        print("  EXTRACAO DE METADADOS E FONTES")
        print("=" * 65)
        print(f"  Arquivo          : {self.caminho_pdf.name}")
        print(f"  Paginas totais   : {m.get('num_paginas', '?')}")
        print(f"  Titulo           : {_val(m.get('titulo'))}")
        print(f"  Criador          : {_val(m.get('criador'))}")
        print(f"  Produtor         : {_val(m.get('produtor'))}")
        print(f"  Criado em        : {_val(m.get('data_criacao'))}")
        print(f"  Modificado em    : {_val(m.get('data_modificacao'))}")
        print(f"  Revisoes increm. : {rev}")
        print(f"  Spans extraidos  : {len(df)}")
        print(f"  Estilos distintos: {df['style_id'].nunique()}")
        print(f"  Fontes embutidas : {n_emb}")
        print(f"  Fontes externas  : {n_ext}\n")

    @property
    def dataframe(self):         return self._df
    @property
    def fontes_embutidas(self):  return self._fontes_embutidas
    @property
    def metadados(self):         return self._metadados_doc


# ══════════════════════════════════════════════════════════════
# ANALISADOR
# ══════════════════════════════════════════════════════════════

class AnalisadorFontes:
    def __init__(self, df: pd.DataFrame, fontes_embutidas=None):
        if df.empty:
            raise ValueError("DataFrame vazio.")
        self._df               = df.copy()
        self._fontes_embutidas = fontes_embutidas or set()
        self._resultados: dict = {}
        # Duas paletas: por style_id (L=1) e por font_name (L=0)
        self._paleta        = gerar_paleta_hsl(self._df["style_id"].unique().tolist())
        self._paleta_fontes = gerar_paleta_hsl(self._df["font_name"].unique().tolist())

    def analisar(self) -> dict:
        for pag in sorted(self._df["pagina"].unique()):
            self._resultados[int(pag)] = self._analisar_pagina(int(pag))
        return self._resultados

    def _analisar_pagina(self, pagina: int) -> list:
        df_pag   = self._df[self._df["pagina"] == pagina]
        total_sp = len(df_pag)
        area_tot = df_pag["area_bbox"].sum()
        pags_glob = self._df.groupby("style_id")["pagina"].apply(
            lambda x: sorted(int(v) for v in x.unique())
        ).to_dict()
        df_pag = _garantir_subset_col(df_pag)
        agg = df_pag.groupby("style_id").agg(
            font_name     =("font_name",     "first"),
            tamanho_pt    =("fonte_tamanho", "first"),
            estilo        =("estilo",        "first"),
            cor_hex       =("fonte_cor",     "first"),
            subset_prefix =("subset_prefix", "first"),
            is_embutida   =("is_embutida",   "any"),
            total_spans   =("style_id",      "count"),
            area_total    =("area_bbox",     "sum"),
            iso_medio     =("isolamento",    "mean"),
            iso_max       =("isolamento",    "max"),
        ).reset_index()
        evids = []
        for _, row in agg.iterrows():
            fid  = row["style_id"]
            n    = int(row["total_spans"])
            freq = n / total_sp if total_sp > 0 else 0
            area = float(row["area_total"]) / area_tot * 100 if area_tot > 0 else 0
            evids.append(EvidenciaFonte(
                style_id           = fid,
                font_name          = row["font_name"],
                tamanho_pt         = round(float(row["tamanho_pt"]), 1),
                estilo             = row["estilo"],
                cor_hex            = row["cor_hex"],
                classe             = _classificar(n, freq),
                total_spans        = n,
                span_pct           = round(freq * 100, 2),
                area_cobertura_pct = round(area, 2),
                isolamento_medio   = round(float(row["iso_medio"]), 3),
                isolamento_max     = round(float(row["iso_max"]), 3),
                is_embutida        = bool(row["is_embutida"]),
                subset_prefix      = str(row.get("subset_prefix", "")),
                cor_hsl            = self._paleta.get(fid, (128, 128, 128, 160)),
                paginas_encontradas = pags_glob.get(fid, [pagina]),
            ))
        return sorted(evids, key=lambda e: e.span_pct, reverse=True)

    # ── Agregacao por font_name ───────────────────────────────

    def _agg_por_font_name(self, evids: list) -> list:
        """Agrega EvidenciaFonte por font_name. Retorna lista de dicts."""
        grupos = defaultdict(lambda: {"spans": 0, "area": 0.0, "span_pct": 0.0, "emb": False})
        for e in evids:
            g = grupos[e.font_name]
            g["spans"]    += e.total_spans
            g["area"]     += e.area_cobertura_pct
            g["span_pct"] += e.span_pct
            if e.is_embutida:
                g["emb"] = True
        total = sum(g["spans"] for g in grupos.values())
        resultado = []
        for nome, g in grupos.items():
            freq = g["spans"] / total if total > 0 else 0
            resultado.append({
                "font_name": nome,
                "freq":      g["spans"],
                "classe":    _classificar(g["spans"], freq),
                "span_pct":  round(g["span_pct"], 1),
                "area_pct":  round(g["area"], 1),
                "emb":       "Sim" if g["emb"] else "Nao",
            })
        return sorted(resultado, key=lambda x: x["span_pct"], reverse=True)

    # ── Saida no terminal ─────────────────────────────────────

    def imprimir_evidencias(self, level: int = 0):
        if not self._resultados:
            raise RuntimeError("Execute analisar() primeiro.")
        if level == 0:
            self._imprimir_l0()
        else:
            self._imprimir_l1()

    def _imprimir_l0(self):
        cab = f"  {'FONTE':<28} {'FREQ':>6}  {'CLASSE':<12}  {'SPAN%':>6}  {'AREA%':>6}  EMB"
        sep = "  " + "-" * 72
        for pag, evids in sorted(self._resultados.items()):
            stats = self._agg_por_font_name(evids)
            print(f"\n  PAGINA {pag}  ({len(stats)} fonte(s) distinta(s))")
            print(cab); print(sep)
            for s in stats:
                print(f"  {s['font_name']:<28} {s['freq']:>6}  {s['classe']:<12}"
                      f"  {s['span_pct']:>5.1f}%  {s['area_pct']:>5.1f}%  {s['emb']}")

    def _imprimir_l1(self):
        cab = f"  {'ESTILO':<42} {'FREQ':>6}  {'CLASSE':<12}  {'SPAN%':>6}  {'AREA%':>6}"
        sep = "  " + "-" * 78
        for pag, evids in sorted(self._resultados.items()):
            print(f"\n  PAGINA {pag}  ({len(evids)} estilo(s) distinto(s))")
            print(cab); print(sep)
            for e in evids:
                lbl = e.style_id[:40]
                print(f"  {lbl:<42} {e.total_spans:>6}  {e.classe:<12}"
                      f"  {e.span_pct:>5.1f}%  {e.area_cobertura_pct:>5.1f}%")

    # ── Exportacao CSV ────────────────────────────────────────

    def exportar_csv(self, caminho, level: int = 0) -> bool:
        """Exporta agregado. Retorna False sem salvar se ja existir."""
        if not self._resultados:
            raise RuntimeError("Execute analisar() primeiro.")
        caminho = Path(caminho)
        if caminho.exists():
            print(f"  [EXISTENTE] {caminho} — ignorado")
            return False
        caminho.parent.mkdir(parents=True, exist_ok=True)
        linhas = []
        for pag, evids in sorted(self._resultados.items()):
            if level == 0:
                for s in self._agg_por_font_name(evids):
                    linhas.append({
                        "pagina":             pag,
                        "font_name":          s["font_name"],
                        "total_spans":        s["freq"],
                        "span_pct":           s["span_pct"],
                        "classe":             s["classe"],
                        "area_cobertura_pct": s["area_pct"],
                        "embutida":           s["emb"],
                    })
            else:
                for e in evids:
                    linhas.append({
                        "pagina":             pag,
                        "style_id":           e.style_id,
                        "font_name":          e.font_name,
                        "subset_prefix":      e.subset_prefix or "-",
                        "estilo":             e.estilo,
                        "tamanho_pt":         e.tamanho_pt,
                        "cor_hex":            e.cor_hex,
                        "total_spans":        e.total_spans,
                        "span_pct":           e.span_pct,
                        "classe":             e.classe,
                        "area_cobertura_pct": e.area_cobertura_pct,
                    })
        pd.DataFrame(linhas).to_csv(caminho, index=False, encoding="utf-8-sig")
        nome_csv = "fontes_extraidas.csv" if level == 0 else "estilos_extraidos.csv"
        print(f"  CSV salvo em: {caminho.parent / nome_csv}")
        return True

    @property
    def resultados(self):       return self._resultados
    @property
    def paleta(self):           return self._paleta
    @property
    def paleta_fontes(self):    return self._paleta_fontes


# ══════════════════════════════════════════════════════════════
# HISTOGRAMAS
# ══════════════════════════════════════════════════════════════

def _agg_font_name_para_hist(evids: list) -> tuple:
    """Agrega por font_name para histogramas L=0.
    Retorna (rotulos, vals_f, vals_a, cores, counts, classes)."""
    grupos = defaultdict(lambda: {"spans": 0.0, "area": 0.0, "total_spans": 0})
    for e in evids:
        grupos[e.font_name]["spans"]       += e.span_pct
        grupos[e.font_name]["area"]        += e.area_cobertura_pct
        grupos[e.font_name]["total_spans"] += e.total_spans
    items = sorted(grupos.items(), key=lambda x: x[1]["spans"], reverse=True)
    rotulos, vals_f, vals_a, cores, counts, classes = [], [], [], [], [], []
    for nome, g in items:
        rotulos.append(nome)
        vals_f.append(round(g["spans"], 2))
        vals_a.append(round(g["area"], 2))
        counts.append(g["total_spans"])
        freq = g["spans"] / 100.0
        if g["total_spans"] == 1:                cls = "unica"
        elif freq >= LIMIARES_FREQ["dominante"]:  cls = "dominante"
        elif freq >= LIMIARES_FREQ["secundaria"]: cls = "secundaria"
        elif freq >= LIMIARES_FREQ["rara"]:       cls = "rara"
        else:                                     cls = "outlier"
        cores.append(CLASSES_COR[cls])
        classes.append(cls)
    return rotulos, vals_f, vals_a, cores, counts, classes


def _agg_style_id_para_hist(evids: list) -> tuple:
    """Dados por style_id para histogramas L=1.
    Retorna (rotulos, vals_f, vals_a, cores, counts, classes).
    rotulos = label abreviado FontName@tam@estilo."""
    rotulos, vals_f, vals_a, cores, counts, classes = [], [], [], [], [], []
    for e in sorted(evids, key=lambda x: x.span_pct, reverse=True):
        lbl = f"{e.font_name}@{e.tamanho_pt}@{e.estilo}"
        rotulos.append(lbl)
        vals_f.append(round(e.span_pct, 2))
        vals_a.append(round(e.area_cobertura_pct, 2))
        counts.append(e.total_spans)
        cores.append(CLASSES_COR[e.classe])
        classes.append(e.classe)
    return rotulos, vals_f, vals_a, cores, counts, classes


def _gerar_hist(evids: list, caminho: Path, dpi: int, level: int, tipo: str = "freq"):
    """
    Gera histograma de frequencia (tipo='freq') ou cobertura de area (tipo='area').
    L=0: barras por font_name. L=1: barras por style_id.

    Freq:  barras = span_pct | rotulo = total_spans | legenda de classe canto inferior direito
    Area:  barras = area_pct | rotulo = span_pct%
           L=1: eixo-y numerado 1-N + legenda de estilos abaixo da figura
           L=0: nome da fonte no eixo-y
    Ambos: linhas tracejadas em 1% e a cada 5%.
    """
    from matplotlib.patches import Patch

    if level == 0:
        rotulos, vals_f, vals_a, cores, counts, classes = _agg_font_name_para_hist(evids)
    else:
        rotulos, vals_f, vals_a, cores, counts, classes = _agg_style_id_para_hist(evids)

    n       = len(rotulos)
    vals    = vals_f if tipo == "freq" else vals_a
    max_val = max(vals) if vals else 10
    eixo_x  = "Percentual de spans (%)" if tipo == "freq" else "Cobertura de area (%)"

    # Rotulos do eixo Y: numeros para L=1 area, nome completo nos outros casos
    y_labels = rotulos
    if level == 1 and tipo == "area":
        y_labels = [str(i + 1) for i in range(n)]

    # Altura minima 4, 0.55 por barra + extra se tiver legenda abaixo
    extra_bottom = 0.0
    if level == 1 and tipo == "area" and n > 0:
        n_colunas   = min(3, n)
        n_linhas    = (n + n_colunas - 1) // n_colunas
        extra_bottom = max(0.10, n_linhas * 0.045)

    fig_h = max(4, n * 0.55)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    fig.patch.set_facecolor("#0F1117")
    ax.set_facecolor("#1A1D27")
    ax.barh(y_labels, vals, color=cores, edgecolor="#2A2D3A", linewidth=0.6, height=0.65)

    # ── Linhas tracejadas ──────────────────────────────────────
    # Cinza em 1% e a cada 5%
    ax.axvline(1, color="#555566", linestyle=":", linewidth=0.7, alpha=0.5)
    for x in range(5, int(max_val) + 15, 5):
        ax.axvline(x, color="#555566", linestyle=":", linewidth=0.7, alpha=0.5)

    # Coloridas nos limiares de classe (apenas histograma de freq)
    if tipo == "freq":
        for cls, lim, lbl in [("rara", 1, "1%"),
                               ("secundaria", 5, "5%"),
                               ("dominante", 40, "40%")]:
            ax.axvline(lim, color=CLASSES_COR[cls], linestyle="--",
                       linewidth=0.9, alpha=0.8)
            ax.text(lim + 0.3, n - 0.5, lbl,
                    color=CLASSES_COR[cls], fontsize=6, va="top")

    # ── Rotulos ao lado das barras ─────────────────────────────
    offset = max_val * 0.012 + 0.3
    if tipo == "freq":
        bar_labels = [str(c) for c in counts]
    else:
        bar_labels = [f"{v:.1f}%" for v in vals_f]

    for i, (v, lbl) in enumerate(zip(vals, bar_labels)):
        ax.text(v + offset, i, lbl,
                color="#CCCCCC", fontsize=7, va="center", ha="left")

    # ── Legenda de classe (canto inferior direito, apenas freq) ─
    if tipo == "freq":
        classes_pres = list(dict.fromkeys(classes))
        handles = [
            Patch(facecolor=CLASSES_COR[cls], label=CLASSES_LABEL[cls])
            for cls in ["dominante", "secundaria", "rara", "outlier", "unica"]
            if cls in classes_pres
        ]
        if handles:
            ax.legend(handles=handles, loc="lower right",
                      facecolor="#1A1D27", edgecolor="#3A3A5A",
                      labelcolor="#AAAAAA", fontsize=7,
                      framealpha=0.9)

    # ── Eixos e titulo ─────────────────────────────────────────
    cat_label   = "Fonte (font_name)" if level == 0 else "Estilo (style_id)"
    titulo_graf = ("Frequencia" if tipo == "freq" else "Cobertura de Area") + f" por {cat_label}"
    ax.set_xlabel(eixo_x, color="#CCCCCC", fontsize=10)
    ax.set_title(titulo_graf, color="white", fontsize=12, fontweight="bold", pad=12)
    ax.tick_params(colors="#AAAAAA", labelsize=8)
    ax.spines[:].set_color("#2A2D3A")
    # Margem direita para nao cortar os rotulos das barras
    ax.set_xlim(right=max_val * 1.18)
    ax.invert_yaxis()

    # ── Legenda abaixo da figura (L=1 area) ───────────────────
    if level == 1 and tipo == "area" and n > 0:
        n_colunas = min(3, n)
        itens = [f"{i+1}— {lbl}" for i, lbl in enumerate(rotulos)]
        rows  = [itens[j:j + n_colunas] for j in range(0, len(itens), n_colunas)]
        leg_txt = "\n".join(["   ".join(r) for r in rows])
        fig.text(0.01, 0.005, leg_txt,
                 color="#888899", fontsize=6.5, fontfamily="monospace",
                 va="bottom", ha="left", transform=fig.transFigure,
                 bbox=dict(facecolor="#0F1117", edgecolor="#2A2D3A",
                           alpha=0.9, boxstyle="round,pad=0.4"))

    plt.tight_layout()
    plt.savefig(caminho, dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()


# ══════════════════════════════════════════════════════════════
# MAPA DE CALOR
# ══════════════════════════════════════════════════════════════

class MapaCalorFontes:
    """Gera overlays e relatorio PDF por pagina."""

    def __init__(self, caminho_pdf, df_spans: pd.DataFrame,
                 resultados: dict, paleta: dict, paleta_fontes: dict,
                 dpi: int = DPI_PADRAO, limiar_spans: float = 100.0, level: int = 0):
        self.caminho_pdf   = Path(caminho_pdf)
        self.df            = df_spans.copy()
        self.resultados    = resultados
        self.paleta        = paleta           # style_id → RGBA
        self.paleta_fontes = paleta_fontes    # font_name → RGBA
        self.zoom          = dpi / 72
        self.dpi           = dpi
        self.limiar_spans  = limiar_spans     # span_pct <= limiar para aparecer no overlay_spans
        self.level         = level

        # _cat_map: {pagina: {chave: classe}}
        # L=0: chave = font_name  |  L=1: chave = style_id
        self._cat_map: dict = {}
        for pag, evids in resultados.items():
            if level == 0:
                self._cat_map[int(pag)] = {
                    s["font_name"]: s["classe"]
                    for s in self._agg_font_name(evids)
                }
            else:
                self._cat_map[int(pag)] = {e.style_id: e.classe for e in evids}

    # ── Helpers de classificacao ──────────────────────────────

    def _agg_font_name(self, evids: list) -> list:
        """Agrega por font_name incluindo unica. Usado para _cat_map L=0."""
        grupos = defaultdict(lambda: {"spans": 0.0, "total_spans": 0})
        for e in evids:
            grupos[e.font_name]["spans"]       += e.span_pct
            grupos[e.font_name]["total_spans"] += e.total_spans
        resultado = []
        for nome, g in grupos.items():
            freq = g["spans"] / 100.0
            if g["total_spans"] == 1:                cls = "unica"
            elif freq >= LIMIARES_FREQ["dominante"]:  cls = "dominante"
            elif freq >= LIMIARES_FREQ["secundaria"]: cls = "secundaria"
            elif freq >= LIMIARES_FREQ["rara"]:       cls = "rara"
            else:                                     cls = "outlier"
            resultado.append({"font_name": nome, "classe": cls})
        return resultado

    # ── Renderizacao ──────────────────────────────────────────

    def _renderizar_pagina(self, doc, num_pag_base0: int) -> Image.Image:
        page = doc[int(num_pag_base0)]
        mat  = fitz.Matrix(self.zoom, self.zoom)
        pix  = page.get_pixmap(matrix=mat, alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")

    # ── Overlay spans (HSL por fonte ou estilo) ───────────────

    def _gerar_overlay_spans(self, imagem: Image.Image,
                              spans_pag: pd.DataFrame,
                              evids: list) -> tuple:
        """
        Pinta spans cujo font_name (L=0) ou style_id (L=1) tenha span_pct <= limiar_spans.
        Retorna (imagem_com_overlay, leg_itens).
        leg_itens ordenados por span_pct desc = mesma ordem da tabela pag 1.
        """
        overlay = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)

        if self.level == 0:
            # Agrega span_pct por font_name
            fontes_pct = defaultdict(float)
            for e in evids:
                fontes_pct[e.font_name] += e.span_pct
            fontes_vis = {fn for fn, pct in fontes_pct.items()
                          if pct <= self.limiar_spans}

            for _, sp in spans_pag.iterrows():
                fn = sp.get("font_name", "")
                if fn not in fontes_vis:
                    continue
                x0, y0, x1, y1 = (sp["bbox_x0"] * self.zoom, sp["bbox_y0"] * self.zoom,
                                   sp["bbox_x1"] * self.zoom, sp["bbox_y1"] * self.zoom)
                if x1 - x0 < 1 or y1 - y0 < 1:
                    continue
                r, g, b, a = self.paleta_fontes.get(fn, (128, 128, 128, 120))
                draw.rectangle([x0, y0, x1, y1], fill=(r, g, b, a))

            # Legenda: mesma ordem da tabela (span_pct desc)
            fn_list   = sorted(fontes_vis, key=lambda fn: -fontes_pct.get(fn, 0))
            leg_itens = [(self.paleta_fontes.get(fn, (128, 128, 128, 160)), fn[:28])
                         for fn in fn_list]
        else:
            # Filtra por span_pct do style_id
            fids_vis = {e.style_id for e in evids if e.span_pct <= self.limiar_spans}

            for _, sp in spans_pag.iterrows():
                fid = sp.get("style_id", "")
                if fid not in fids_vis:
                    continue
                x0, y0, x1, y1 = (sp["bbox_x0"] * self.zoom, sp["bbox_y0"] * self.zoom,
                                   sp["bbox_x1"] * self.zoom, sp["bbox_y1"] * self.zoom)
                if x1 - x0 < 1 or y1 - y0 < 1:
                    continue
                r, g, b, a = self.paleta.get(fid, (128, 128, 128, 120))
                draw.rectangle([x0, y0, x1, y1], fill=(r, g, b, a))

            # Legenda: order da tabela (evids ja esta em span_pct desc)
            evid_map  = {e.style_id: e for e in evids}
            sids_ord  = [e.style_id for e in evids if e.style_id in fids_vis]
            leg_itens = []
            for i, sid in enumerate(sids_ord):
                e   = evid_map.get(sid)
                lbl = f"s{i+1}@{e.font_name[:18]}" if e else sid[:28]
                leg_itens.append((self.paleta.get(sid, (128, 128, 128, 160)), lbl))

        return Image.alpha_composite(imagem, overlay), leg_itens

    # ── Overlay classe de frequencia ──────────────────────────

    def _gerar_overlay_classe(self, imagem: Image.Image,
                               spans_pag: pd.DataFrame,
                               pagina: int) -> tuple:
        """
        Retorna (imagem_com_overlay, cats_presentes).
        Chave de lookup: font_name (L=0) ou style_id (L=1).
        """
        ALPHA   = {"dominante": 180, "secundaria": 170, "rara": 180, "outlier": 200, "unica": 200}
        cat_pag = self._cat_map.get(int(pagina), {})
        overlay = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)
        cats_presentes: set = set()

        for _, sp in spans_pag.iterrows():
            key = sp.get("font_name", "") if self.level == 0 else sp.get("style_id", "")
            cat = cat_pag.get(key, None)
            if cat is None:
                continue
            cats_presentes.add(cat)
            x0, y0, x1, y1 = (sp["bbox_x0"] * self.zoom, sp["bbox_y0"] * self.zoom,
                               sp["bbox_x1"] * self.zoom, sp["bbox_y1"] * self.zoom)
            if x1 - x0 < 1 or y1 - y0 < 1:
                continue
            r, g, b, _ = CLASSES_RGBA[cat]
            a           = ALPHA.get(cat, 180)
            draw.rectangle([x0, y0, x1, y1], fill=(r, g, b, a))
            if cat in ("outlier", "unica"):
                draw.rectangle([x0, y0, x1, y1], outline=(r, g, b, 230),
                               width=max(1, int(self.zoom)))

        return Image.alpha_composite(imagem, overlay), cats_presentes

    # ── Legendas ──────────────────────────────────────────────

    def _adicionar_legenda(self, imagem: Image.Image,
                           itens: list, titulo: str) -> Image.Image:
        """Legenda lateral generica. itens = [(rgba, label), ...]."""
        LG = 255; PAD = 10; HI = 22; FS = 11
        nova = Image.new("RGBA", (imagem.width + LG, imagem.height), (18, 20, 32, 255))
        nova.paste(imagem, (0, 0))
        draw = ImageDraw.Draw(nova)
        lx   = imagem.width + PAD
        fb   = _pil_font(FS, bold=True)
        fn_  = _pil_font(FS - 1, bold=False)

        y = PAD
        draw.text((lx, y), titulo, fill=(200, 200, 220, 255), font=fb)
        y += FS + 6
        draw.line([(lx, y), (nova.width - PAD, y)], fill=(60, 60, 90, 255))
        y += 6

        for rgba, label in itens:
            if y + HI > nova.height - PAD:
                break
            r, g, b = rgba[0], rgba[1], rgba[2]
            draw.rectangle([lx, y + 2, lx + 12, y + 14], fill=(r, g, b, 230))
            draw.text((lx + 16, y), str(label)[:28], fill=(210, 210, 230, 255), font=fn_)
            y += HI

        return nova

    def _adicionar_legenda_classe(self, imagem: Image.Image,
                                   cats_presentes: set) -> Image.Image:
        LG = 225; PAD = 10; HI = 26; FS = 11
        nova = Image.new("RGBA", (imagem.width + LG, imagem.height), (18, 20, 32, 255))
        nova.paste(imagem, (0, 0))
        draw = ImageDraw.Draw(nova)
        lx   = imagem.width + PAD
        fb   = _pil_font(FS, bold=True)
        fn_  = _pil_font(FS - 1, bold=False)

        y = PAD
        draw.text((lx, y), "CLASSE", fill=(200, 200, 220, 255), font=fb)
        y += FS + 6
        draw.line([(lx, y), (nova.width - PAD, y)], fill=(60, 60, 90, 255))
        y += 6

        for cat in ["dominante", "secundaria", "rara", "outlier", "unica"]:
            if cat not in cats_presentes:
                continue
            r, g, b, _ = CLASSES_RGBA[cat]
            draw.rectangle([lx, y + 2, lx + 12, y + 14], fill=(r, g, b, 230))
            draw.text((lx + 16, y), CLASSES_LABEL[cat], fill=(210, 210, 230, 255), font=fn_)
            y += HI

        return nova

    # ── Processamento por pagina ──────────────────────────────

    def processar_paginas(self, pasta_saida: Path):
        sufixo = "fontes" if self.level == 0 else "estilos"
        pasta_saida = Path(pasta_saida)

        NOMES = {
            "spans":  f"overlay_spans_{sufixo}.png",
            "classe": f"overlay_spans_{sufixo}_classe.png",
            "hist":   f"hist_{sufixo}_classe.png",
            "cob":    f"cobertura_{sufixo}_classe.png",
            "rel":    f"relatorio_{sufixo}.pdf",
        }

        with fitz.open(self.caminho_pdf) as doc:
            for pag, evids in sorted(self.resultados.items()):
                pasta = pasta_saida / f"pag-{pag}"
                pasta.mkdir(parents=True, exist_ok=True)

                paths     = {k: pasta / v for k, v in NOMES.items()}
                existentes = [k for k, p in paths.items() if p.exists()]
                pendentes  = [k for k, p in paths.items() if not p.exists()]

                for k in existentes:
                    print(f"  [EXISTENTE] pag-{pag}/{NOMES[k]} — ignorado")

                if not pendentes:
                    continue

                print(f"\n  Pagina {pag}:")

                spans_pag    = self.df[self.df["pagina"] == pag]
                needs_render = "spans" in pendentes or "classe" in pendentes
                img_base     = self._renderizar_pagina(doc, int(pag) - 1) if needs_render else None

                # overlay_spans
                if "spans" in pendentes:
                    img_sp, leg_itens = self._gerar_overlay_spans(img_base.copy(), spans_pag, evids)
                    titulo_leg = "FONTES" if self.level == 0 else "ESTILOS"
                    img_sp_leg = self._adicionar_legenda(img_sp, leg_itens, titulo_leg)
                    img_sp_leg.convert("RGB").save(paths["spans"], dpi=(self.dpi, self.dpi))
                    print(f"    {NOMES['spans']}")

                # overlay_classe
                if "classe" in pendentes:
                    img_cls, cats = self._gerar_overlay_classe(img_base.copy(), spans_pag, pag)
                    img_cls_leg   = self._adicionar_legenda_classe(img_cls, cats)
                    img_cls_leg.convert("RGB").save(paths["classe"], dpi=(self.dpi, self.dpi))
                    print(f"    {NOMES['classe']}")

                # histogramas
                if "hist" in pendentes:
                    _gerar_hist(evids, paths["hist"], self.dpi, self.level, tipo="freq")
                    print(f"    {NOMES['hist']}")

                if "cob" in pendentes:
                    _gerar_hist(evids, paths["cob"], self.dpi, self.level, tipo="area")
                    print(f"    {NOMES['cob']}")

                # relatorio PDF
                if "rel" in pendentes:
                    self._gerar_relatorio_pdf(
                        paths["rel"], pag, evids, spans_pag,
                        paths["spans"], paths["classe"]
                    )
                    print(f"    {NOMES['rel']}")

    # ── Relatorio PDF ─────────────────────────────────────────

    def _gerar_relatorio_pdf(self, caminho_pdf: Path, pag: int,
                              evids: list, spans_pag: pd.DataFrame,
                              p_overlay_spans: Path, p_overlay_classe: Path):
        """
        PDF por pagina — 3 paginas:
          Pag 1: cabecalho + tabela de evidencias
          Pag 2: overlay_spans com anotacoes popup
          Pag 3: overlay_classe com anotacoes popup
        """
        doc      = fitz.open()
        evid_map = {e.style_id: e for e in evids}

        # Pag 1 — tabela
        self._pagina_tabela(doc, pag, evids)

        # Pag 2 — overlay spans + popups
        if self.level == 0:
            fontes_pct = defaultdict(float)
            for e in evids:
                fontes_pct[e.font_name] += e.span_pct
            fids_vis_spans = {e.style_id for e in evids
                              if fontes_pct.get(e.font_name, 0) <= self.limiar_spans}
        else:
            fids_vis_spans = {e.style_id for e in evids
                              if e.span_pct <= self.limiar_spans}

        limiar_str  = f"  [limiar: {self.limiar_spans:.0f}%]" if self.limiar_spans < 100.0 else ""
        titulo_sp   = f"Overlay por {'Fonte' if self.level == 0 else 'Estilo'} (HSL){limiar_str}"
        info = self._pagina_imagem(doc, str(p_overlay_spans), titulo_sp, pag)
        if info:
            pg2, img_w, img_h, pg_w, pg_h = info
            self._anotar_overlay(pg2, spans_pag, evid_map, fids_vis_spans,
                                 img_w, img_h, pg_w, pg_h)

        # Pag 3 — overlay classe + popups
        fids_vis_cls = {e.style_id for e in evids}
        info = self._pagina_imagem(doc, str(p_overlay_classe),
                                   "Overlay por Classe de Frequencia", pag)
        if info:
            pg3, img_w, img_h, pg_w, pg_h = info
            self._anotar_overlay(pg3, spans_pag, evid_map, fids_vis_cls,
                                 img_w, img_h, pg_w, pg_h)

        doc.save(str(caminho_pdf), garbage=4, deflate=True)
        doc.close()

    def _pagina_tabela(self, doc, pag: int, evids: list):
        """Pagina 1 do relatorio: cabecalho + tabela."""
        pg   = fitz.open()  # dummy — usamos doc abaixo
        pg   = doc.new_page(width=595, height=842)  # A4 portrait
        MARG = 30

        # Cabecalho
        pg.draw_rect(fitz.Rect(0, 0, 595, 58), color=None, fill=(0.07, 0.08, 0.13))
        pg.insert_text((MARG, 22),
                       "RELATORIO DE ANALISE TIPOGRAFICA",
                       fontsize=13, color=(0.9, 0.9, 1.0), fontname="helv")
        pg.insert_text((MARG, 42),
                       f"Arquivo: {self.caminho_pdf.name}   |   Pagina: {pag}",
                       fontsize=8, color=(0.6, 0.7, 0.9), fontname="helv")

        # Subtitulo
        nivel_label = "FONTES (font_name)" if self.level == 0 else "ESTILOS (style_id)"
        y = 74
        pg.insert_text((MARG, y),
                       f"TABELA DE EVIDENCIAS — {nivel_label}",
                       fontsize=9, color=(0.2, 0.2, 0.35), fontname="hebo")
        y += 16

        if self.level == 0:
            self._tabela_l0(pg, pag, evids, y, MARG)
        else:
            self._tabela_l1(pg, pag, evids, y, MARG)

    def _tabela_l0(self, pg, pag: int, evids: list, y: int, MARG: int):
        """Tabela L=0: Fonte | Freq | Classe | Span% | Area% | Emb"""
        rows = AnalisadorFontes._agg_por_font_name(None, evids)

        # Colunas: x_swatch, x_nome, x_freq, x_cls, x_span, x_area, x_emb
        CS = MARG
        C  = [CS + 13, CS + 13, CS + 163, CS + 213, CS + 308, CS + 363, CS + 418]
        HDRS = ["Fonte", "Freq", "Classe", "Span%", "Area%", "Emb"]
        CX   = [C[1], C[2], C[3], C[4], C[5], C[6]]

        pg.draw_rect(fitz.Rect(MARG, y, 565, y + 16), color=None, fill=(0.12, 0.14, 0.22))
        for hdr, cx in zip(HDRS, CX):
            pg.insert_text((cx + 2, y + 12), hdr,
                           fontsize=7.5, color=(0.8, 0.8, 1.0), fontname="hebo")
        y += 18

        for i, s in enumerate(rows):
            if y > 810:
                break
            bg = (0.11, 0.12, 0.19) if i % 2 == 0 else (0.09, 0.10, 0.16)
            pg.draw_rect(fitz.Rect(MARG, y, 565, y + 14), color=None, fill=bg)

            # Swatch de cor do font_name
            r_c, g_c, b_c, _ = self.paleta_fontes.get(s["font_name"], (128, 128, 128, 160))
            pg.draw_rect(fitz.Rect(CS + 1, y + 2, CS + 11, y + 12),
                         color=None, fill=(r_c/255, g_c/255, b_c/255))

            cor_cls = _hex_para_fitz(CLASSES_COR.get(s["classe"], "#888888"))
            vals = [
                (C[1], s["font_name"][:22],           (0.85, 0.85, 0.95)),
                (C[2], str(s["freq"]),                 (0.75, 0.75, 0.90)),
                (C[3], s["classe"],                    cor_cls),
                (C[4], f"{s['span_pct']:.1f}%",        (0.85, 0.85, 0.95)),
                (C[5], f"{s['area_pct']:.1f}%",        (0.85, 0.85, 0.95)),
                (C[6], s["emb"],
                       (0.5, 0.9, 0.5) if s["emb"] == "Sim" else (0.9, 0.4, 0.4)),
            ]
            for x, txt, cor in vals:
                pg.insert_text((x, y + 11), str(txt), fontsize=7, color=cor, fontname="cour")
            y += 15

        pg.draw_line((MARG, y), (565, y), color=(0.4, 0.4, 0.6), width=0.5)
        pg.insert_text((MARG, y + 10),
                       "Nota: evidencias factuais. Interpretacao e conclusao sao de responsabilidade do analista.",
                       fontsize=7, color=(0.5, 0.5, 0.6), fontname="helv")

    def _tabela_l1(self, pg, pag: int, evids: list, y: int, MARG: int):
        """Tabela L=1: Estilo | Freq | Classe | Span% | Area%"""
        CS = MARG
        C  = [CS + 13, CS + 13, CS + 213, CS + 263, CS + 358, CS + 413]
        HDRS = ["Estilo", "Freq", "Classe", "Span%", "Area%"]
        CX   = [C[1], C[2], C[3], C[4], C[5]]

        pg.draw_rect(fitz.Rect(MARG, y, 565, y + 16), color=None, fill=(0.12, 0.14, 0.22))
        for hdr, cx in zip(HDRS, CX):
            pg.insert_text((cx + 2, y + 12), hdr,
                           fontsize=7.5, color=(0.8, 0.8, 1.0), fontname="hebo")
        y += 18

        for i, e in enumerate(evids):
            if y > 810:
                break
            bg = (0.11, 0.12, 0.19) if i % 2 == 0 else (0.09, 0.10, 0.16)
            pg.draw_rect(fitz.Rect(MARG, y, 565, y + 14), color=None, fill=bg)

            r_c, g_c, b_c, _ = self.paleta.get(e.style_id, (128, 128, 128, 160))
            pg.draw_rect(fitz.Rect(CS + 1, y + 2, CS + 11, y + 12),
                         color=None, fill=(r_c/255, g_c/255, b_c/255))

            cor_cls  = _hex_para_fitz(CLASSES_COR.get(e.classe, "#888888"))
            lbl_est  = f"{e.font_name[:14]}@{e.tamanho_pt}@{e.estilo[:7]}"
            vals = [
                (C[1], lbl_est,                        (0.85, 0.85, 0.95)),
                (C[2], str(e.total_spans),              (0.75, 0.75, 0.90)),
                (C[3], e.classe,                        cor_cls),
                (C[4], f"{e.span_pct:.1f}%",            (0.85, 0.85, 0.95)),
                (C[5], f"{e.area_cobertura_pct:.1f}%",  (0.85, 0.85, 0.95)),
            ]
            for x, txt, cor in vals:
                pg.insert_text((x, y + 11), str(txt), fontsize=7, color=cor, fontname="cour")
            y += 15

        pg.draw_line((MARG, y), (565, y), color=(0.4, 0.4, 0.6), width=0.5)
        pg.insert_text((MARG, y + 10),
                       "Nota: evidencias factuais. Interpretacao e conclusao sao de responsabilidade do analista.",
                       fontsize=7, color=(0.5, 0.5, 0.6), fontname="helv")

    def _pagina_imagem(self, doc, caminho_img: str, titulo: str, pag: int):
        """Cria pagina adaptada ao aspect ratio da imagem. Retorna (pg, img_w, img_h, pg_w, pg_h)."""
        if not Path(caminho_img).exists():
            return None
        with Image.open(caminho_img) as im:
            img_w, img_h = im.size
        HEADER   = 32
        MARG     = 8
        MAX_LADO = 1100
        escala   = min(MAX_LADO / img_w, (MAX_LADO - HEADER) / img_h)
        pg_w     = int(img_w * escala) + MARG * 2
        pg_h     = int(img_h * escala) + HEADER + MARG
        pg = doc.new_page(width=pg_w, height=pg_h)
        pg.draw_rect(fitz.Rect(0, 0, pg_w, HEADER), color=None, fill=(0.07, 0.08, 0.13))
        pg.insert_text((MARG + 4, HEADER - 10),
                       f"Pag. {pag}  ---  {titulo}",
                       fontsize=9, color=(0.9, 0.9, 1.0), fontname="helv")
        pg.insert_image(fitz.Rect(MARG, HEADER, pg_w - MARG, pg_h - MARG),
                        filename=caminho_img)
        return pg, img_w, img_h, pg_w, pg_h

    def _anotar_overlay(self, pag, spans_pag: pd.DataFrame,
                         evid_map: dict, fids_visiveis: set,
                         img_w: int, img_h: int, pg_w: int, pg_h: int):
        """Adiciona anotacoes popup clicaveis sobre cada span visivel."""
        HEADER = 32
        MARG   = 8
        sx     = (pg_w - 2 * MARG) / img_w
        sy     = (pg_h - HEADER - MARG) / img_h

        for _, sp in spans_pag.iterrows():
            fid = sp.get("style_id", "")
            if fid not in fids_visiveis:
                continue
            e = evid_map.get(fid)
            if not e:
                continue

            x0 = MARG + float(sp["bbox_x0"]) * self.zoom * sx
            y0 = HEADER + float(sp["bbox_y0"]) * self.zoom * sy
            x1 = MARG + float(sp["bbox_x1"]) * self.zoom * sx
            y1 = HEADER + float(sp["bbox_y1"]) * self.zoom * sy

            if x1 - x0 < 1 or y1 - y0 < 1:
                continue

            texto_span = str(sp.get("texto", ""))[:80]
            iso_span   = float(sp.get("isolamento", 0.0))

            conteudo = (
                f"Texto     : \"{texto_span}\"\n"
                f"Isolamento: {iso_span:.3f}"
                f"{'  [ISOLADO]' if iso_span >= 1.0 else ''}\n"
                f"\nNome      : {e.font_name}\n"
                f"Subset    : {e.subset_prefix if e.subset_prefix else '-'}\n"
                f"Estilo    : {e.estilo}\n"
                f"Tamanho   : {e.tamanho_pt}pt\n"
                f"Cor       : {e.cor_hex}\n"
                f"Embutida  : {'Sim' if e.is_embutida else 'NAO'}"
            )
            titulo = f"{e.font_name} {e.tamanho_pt}pt — \"{texto_span[:40]}\""

            r, g, b, _ = self.paleta.get(fid, (128, 128, 128, 160))
            annot = pag.add_highlight_annot(fitz.Rect(x0, y0, x1, y1))
            annot.set_colors(stroke=(r/255, g/255, b/255))
            annot.set_info(content=conteudo, title=titulo)
            annot.update(opacity=0.3)


# ══════════════════════════════════════════════════════════════
# ARGPARSE + MAIN
# ══════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf-fontmap",
        description="Analise Tipografica em PDF",
    )
    p.add_argument("arquivo",     help="PDF a analisar")
    p.add_argument("pasta_saida", nargs="?", default="output", help="Pasta de saida (padrao: output)")
    p.add_argument("--paginas",       default=None,
                   help="Ex: '1,3-5,9'")
    p.add_argument("--overlay-spans", type=float, default=100.0, dest="overlay_spans",
                   help="Pinta no overlay apenas tipos com span%% <= limiar (padrao: 100)")
    p.add_argument("--dpi",  type=int, default=DPI_PADRAO,
                   help="Resolucao de renderizacao (padrao: 150)")
    p.add_argument("-L", type=int, default=0, dest="level", choices=[0, 1],
                   help="Nivel de analise: 0=fontes/font_name (padrao), 1=estilos/style_id")
    return p


def main():
    args        = _build_parser().parse_args()
    pdf_path    = Path(args.arquivo)
    pasta_saida = Path(args.pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    level       = args.level

    paginas_alvo = parse_paginas(args.paginas) if args.paginas else None

    print(f"\n{'='*60}")
    print(f"  PDF-FONTMAP — ANALISE TIPOGRAFICA  (nivel L={level})")
    print(f"{'='*60}")

    # ── 1. Spans: extrair ou reutilizar CSV ───────────────────
    csv_spans = pasta_saida / "analise_spans.csv"

    if csv_spans.exists():
        df_existing = ler_csv_pericial(csv_spans)
        pags_exist  = set(int(p) for p in df_existing["pagina"].unique())
        pags_need   = set(paginas_alvo) if paginas_alvo else None

        if pags_need is None or pags_need.issubset(pags_exist):
            print(f"\n  Carregando spans de: {csv_spans}")
            df = df_existing
            if paginas_alvo:
                df = df[df["pagina"].isin(paginas_alvo)].copy()
            df = _garantir_subset_col(df)
            if "style_id" not in df.columns:
                sub_label      = df["subset_prefix"].where(df["subset_prefix"] != "", "nosub")
                df["style_id"] = (df["font_name"] + "@" + sub_label + "@"
                                  + df["estilo"] + "@"
                                  + df["fonte_tamanho"].round(1).astype(str) + "pt@"
                                  + df["fonte_cor"])
            if "is_embutida" not in df.columns:
                df["is_embutida"] = False
            if "isolamento" not in df.columns:
                df["isolamento"] = 0.0
            fontes_embutidas = set(
                df[df["is_embutida"] == True]["font_name"].unique()
            ) if "is_embutida" in df.columns else set()
            print(f"  {len(df)} spans, {df['pagina'].nunique()} pagina(s) carregadas.")
        else:
            faltando = sorted(pags_need - pags_exist) if pags_need else []
            print(f"\n  Paginas {faltando} ausentes no CSV existente. Reprocessando PDF...")
            paginas_base0 = [p - 1 for p in paginas_alvo] if paginas_alvo else None
            extrator = ExtratorFontesPDF(pdf_path, paginas_base0=paginas_base0)
            df = extrator.extrair()
            extrator.imprimir_resumo()
            df.to_csv(csv_spans, index=False, encoding="utf-8-sig")
            print(f"  CSV salvo em: {csv_spans}")
            fontes_embutidas = extrator.fontes_embutidas
    else:
        paginas_base0 = [p - 1 for p in paginas_alvo] if paginas_alvo else None
        extrator = ExtratorFontesPDF(pdf_path, paginas_base0=paginas_base0)
        df = extrator.extrair()
        extrator.imprimir_resumo()
        extrator.salvar_csv(csv_spans)
        fontes_embutidas = extrator.fontes_embutidas

    if df.empty:
        print("  Nenhum span extraido. Encerrando.")
        return

    # ── 2. Analise ────────────────────────────────────────────
    print("\n  Analisando fontes...")
    analisador = AnalisadorFontes(df, fontes_embutidas)
    analisador.analisar()
    analisador.imprimir_evidencias(level)

    # CSV agregado (fontes_extraidas.csv ou estilos_extraidos.csv)
    nome_csv_agg = "fontes_extraidas.csv" if level == 0 else "estilos_extraidos.csv"
    analisador.exportar_csv(pasta_saida / nome_csv_agg, level)

    # ── 3. Overlays e relatorio ───────────────────────────────
    print("\n  Gerando overlays e relatorios...")
    mapa = MapaCalorFontes(
        pdf_path,
        df_spans      = df,
        resultados    = analisador.resultados,
        paleta        = analisador.paleta,
        paleta_fontes = analisador.paleta_fontes,
        dpi           = args.dpi,
        limiar_spans  = args.overlay_spans,
        level         = level,
    )
    mapa.processar_paginas(pasta_saida)

    # ── Resumo final ──────────────────────────────────────────
    sufixo = "fontes" if level == 0 else "estilos"
    print(f"\n  Concluido. Resultados em: {pasta_saida}/")
    for pag in sorted(analisador.resultados.keys()):
        print(f"  pag-{pag}/  relatorio_{sufixo}.pdf  "
              f"overlay_spans_{sufixo}.png  overlay_spans_{sufixo}_classe.png  "
              f"hist_{sufixo}_classe.png  cobertura_{sufixo}_classe.png")
    print()


# ============================================================
# Integração PeriTASK
# ============================================================

def _peritask_status(msg: str) -> None:
    print(f"STATUS:{msg}", flush=True)


def _peritask_progress(valor: int) -> None:
    valor = max(0, min(100, int(valor)))
    print(f"PROGRESS:{valor}", flush=True)


def _controle_str(controls, chave: str, padrao: str = "") -> str:
    try:
        valor = controls.get(chave, padrao) if controls else padrao
    except Exception:
        valor = padrao
    if valor is None:
        return padrao
    return str(valor).strip()


def _controle_int(controls, chave: str, padrao: int, minimo: int, maximo: int) -> int:
    try:
        valor = int(float(_controle_str(controls, chave, str(padrao)).replace(",", ".")))
    except Exception:
        valor = padrao
    return max(minimo, min(maximo, valor))


def _controle_float(controls, chave: str, padrao: float, minimo: float, maximo: float) -> float:
    try:
        valor = float(_controle_str(controls, chave, str(padrao)).replace(",", "."))
    except Exception:
        valor = padrao
    return max(minimo, min(maximo, valor))


def _nome_pasta_seguro(nome: str) -> str:
    permitido = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- "
    limpo = "".join(c if c in permitido else "_" for c in nome).strip(" ._")
    return limpo or "pdf"


def _nivel_peritask(controls) -> int:
    valor = _controle_str(controls, "nivel_analise", "0").lower()
    if valor.startswith("1") or valor in {"estilo", "estilos", "style", "style_id", "l1", "l=1"}:
        return 1
    return 0


def _executar_pdf_peritask(caminho_pdf: str, controls, pasta_saida: str) -> None:
    """Executa o fluxo original do pdf-fontmap usando parâmetros vindos da UI PeriTASK."""
    import sys as _sys

    pdf_path = Path(caminho_pdf)
    pasta_base = Path(pasta_saida)
    pasta_base.mkdir(parents=True, exist_ok=True)

    # Uma subpasta por PDF evita colisão de analise_spans.csv quando vários PDFs são selecionados.
    pasta_pdf = pasta_base / f"pdf_fontmap_{_nome_pasta_seguro(pdf_path.stem)}"
    pasta_pdf.mkdir(parents=True, exist_ok=True)

    nivel = _nivel_peritask(controls)
    dpi = _controle_int(controls, "dpi", DPI_PADRAO, 36, 600)
    overlay_spans = _controle_float(controls, "overlay_spans", 100.0, 0.0, 100.0)
    paginas = _controle_str(controls, "paginas", "0")

    argv = ["pdf_fontmap.py", str(pdf_path), str(pasta_pdf), "-L", str(nivel), "--dpi", str(dpi), "--overlay-spans", str(overlay_spans)]
    if paginas != "0":
        argv.extend(["--paginas", paginas])

    _peritask_status(f"PDF-FontMap: analisando {pdf_path.name}")
    antigo_argv = list(_sys.argv)
    try:
        _sys.argv = argv
        main()
    finally:
        _sys.argv = antigo_argv


def executar(arquivos, controls, pasta_saida):
    """
    Entrada padrão do PeriTASK.

    Parâmetros esperados em controls:
      - nivel_analise: 0/fontes ou 1/estilos
      - paginas: vazio, "1", "1,3-5,9" etc.
      - overlay_spans: 0 a 100
      - dpi: 36 a 600
    """
    arquivos_pdf = [str(a) for a in (arquivos or []) if str(a).lower().endswith(".pdf")]
    total = len(arquivos_pdf)

    if total == 0:
        _peritask_status("PDF-FontMap: nenhum PDF selecionado.")
        _peritask_progress(100)
        return []

    _peritask_progress(0)
    saidas = []
    for idx, caminho_pdf in enumerate(arquivos_pdf, start=1):
        _peritask_status(f"PDF-FontMap: arquivo {idx}/{total}")
        _executar_pdf_peritask(caminho_pdf, controls or {}, pasta_saida)
        pasta_pdf = Path(pasta_saida) / f"pdf_fontmap_{_nome_pasta_seguro(Path(caminho_pdf).stem)}"
        saidas.append(str(pasta_pdf))
        _peritask_progress(round(idx * 100 / total))

    _peritask_status("PDF-FontMap: concluído.")
    _peritask_progress(100)
    return saidas


if __name__ == "__main__":
    main()