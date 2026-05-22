"""
===========================================================
COMPARAÇÃO DO BENCHMARK ATUAL COM A REFERÊNCIA
===========================================================
"""

from __future__ import annotations

import json
from numbers import Number
from pathlib import Path
from typing import Any

from utilitario_pytest import (
    benchmark_report_path,
    benchmark_report_referencia_path,
    benchmark_report_comparacao_path,
)


TOLERANCIA_PERCENTUAL = 10.0
TOLERANCIA_ABSOLUTA_S = 0.05


def carregar_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def eh_numero_comparavel(valor: Any) -> bool:
    """
    bool é subclasse de int em Python, então precisa ser excluído.
    """
    return isinstance(valor, Number) and not isinstance(valor, bool)


def caminho_deve_ser_ignorado(caminho: tuple[str, ...]) -> bool:
    """
    Remove trechos que não representam resultado de benchmark comparável.
    """
    partes_ignoradas = {
        "run_info",
        "input_files",
        "system",
    }

    return any(parte in partes_ignoradas for parte in caminho)


def caminho_eh_mean(caminho: tuple[str, ...]) -> bool:
    """
    Retorna True somente para métricas cujo último campo é mean.

    Exemplo aceito:
        ...statistics.time_s.mean
        ...statistics.cpu_peak.mean

    Exemplos ignorados:
        ...statistics.time_s.min
        ...statistics.time_s.max
    """
    return bool(caminho) and caminho[-1] == "mean"


def caminho_eh_overhead_direto(caminho: tuple[str, ...]) -> bool:
    """
    Overheads diretos não possuem mean/min/max.

    Exemplos:
        teste_benchmark_overhead_contrato.overhead_contrato_s
        teste_benchmark_comunicacao_UI_PythonScript.overhead_comunicacao_ui_pythonscript_s
    """
    if not caminho:
        return False

    nome_campo = caminho[-1]

    return nome_campo.startswith("overhead_")


def caminho_eh_metrica_tempo_s(caminho: tuple[str, ...]) -> bool:
    """
    Retorna True para métricas de tempo em segundos.

    Exemplos:
        ...statistics.time_s.mean
        teste_benchmark_overhead_contrato.overhead_contrato_s
        teste_benchmark_comunicacao_UI_PythonScript.overhead_comunicacao_ui_pythonscript_s
    """
    if not caminho:
        return False

    nome_campo = caminho[-1]

    # Exemplo: ...time_s.mean
    if nome_campo == "mean" and len(caminho) >= 2:
        return caminho[-2].endswith("_s")

    # Exemplo: overhead_contrato_s
    return nome_campo.endswith("_s")


def caminho_parece_benchmark(caminho: tuple[str, ...]) -> bool:
    """
    Mantém somente métricas que fazem sentido para comparação final:

    - métricas mean dentro de results/statistics;
    - overheads diretos.
    """
    if caminho_deve_ser_ignorado(caminho):
        return False

    if caminho_eh_overhead_direto(caminho):
        return True

    if "results" in caminho and caminho_eh_mean(caminho):
        return True

    return False


def iterar_numericos_comparaveis(
    obj: Any,
    caminho: tuple[str, ...] = (),
):
    """
    Percorre recursivamente o JSON da referência e emite apenas folhas numéricas
    que parecem métricas de benchmark comparáveis.
    """
    if isinstance(obj, dict):
        for chave, valor in obj.items():
            yield from iterar_numericos_comparaveis(
                valor,
                caminho + (str(chave),),
            )
        return

    if eh_numero_comparavel(obj) and caminho_parece_benchmark(caminho):
        yield caminho, float(obj)


def obter_por_caminho(obj: Any, caminho: tuple[str, ...]) -> Any:
    atual = obj

    for parte in caminho:
        if not isinstance(atual, dict):
            raise KeyError(caminho)

        if parte not in atual:
            raise KeyError(caminho)

        atual = atual[parte]

    return atual


def calcular_diferenca_percentual(
    referencia: float,
    atual: float,
) -> float | None:
    """
    Retorna diferença percentual relativa à referência.

    Se referência for zero:
    - atual zero => 0%;
    - atual diferente de zero => percentual indefinido.
    """
    if referencia == 0:
        if atual == 0:
            return 0.0

        return None

    return ((atual - referencia) / abs(referencia)) * 100.0


def diferenca_ultrapassa_tolerancia(
    caminho: tuple[str, ...],
    referencia: float,
    atual: float,
    tolerancia_percentual: float,
    tolerancia_absoluta_s: float = TOLERANCIA_ABSOLUTA_S,
) -> bool:
    """
    Retorna True somente se a diferença deve aparecer no relatório.

    Regra adicional:
    - se a métrica for de tempo em segundos e a diferença absoluta for
      menor ou igual a tolerancia_absoluta_s, ignora a diferença.
    """
    diferenca_absoluta = abs(atual - referencia)

    if (
        caminho_eh_metrica_tempo_s(caminho)
        and diferenca_absoluta <= tolerancia_absoluta_s
    ):
        return False

    diferenca_percentual = calcular_diferenca_percentual(
        referencia,
        atual,
    )

    if diferenca_percentual is None:
        return True

    return abs(diferenca_percentual) > tolerancia_percentual


def formatar_nome_metrica(caminho: tuple[str, ...]) -> str:
    """
    Deixa o nome da métrica mais legível removendo partes estruturais
    que não agregam muito no relatório.

    Exemplo:
        teste_benchmark_engine_python.results.videos_csv_simplificado.statistics.time_s.mean

    Vira:
        teste_benchmark_engine_python.videos_csv_simplificado.time_s.mean
    """
    partes_removidas = {
        "results",
        "statistics",
    }

    partes = [
        parte
        for parte in caminho
        if parte not in partes_removidas
    ]

    return ".".join(partes)


def montar_item_diferenca(
    caminho: tuple[str, ...],
    referencia: float,
    atual: float,
) -> dict[str, Any]:
    diferenca_percentual = calcular_diferenca_percentual(
        referencia,
        atual,
    )

    item = {
        "métrica": formatar_nome_metrica(caminho),
        "referencia": round(referencia, 6),
        "atual": round(atual, 6),
    }

    if diferenca_percentual is None:
        item["diferenca_percentual"] = None
    else:
        item["diferenca_percentual"] = round(diferenca_percentual, 2)

    return item


def comparar_benchmark_reports(
    referencia_json: dict[str, Any],
    atual_json: dict[str, Any],
    tolerancia_percentual: float = TOLERANCIA_PERCENTUAL,
) -> dict[str, Any]:
    diferencas = []

    for caminho, valor_referencia in iterar_numericos_comparaveis(
        referencia_json
    ):
        try:
            valor_atual = obter_por_caminho(atual_json, caminho)
        except KeyError:
            # Retrocompatibilidade:
            # se existe na referência mas não existe no atual, ignora.
            continue

        if not eh_numero_comparavel(valor_atual):
            continue

        valor_atual = float(valor_atual)

        if diferenca_ultrapassa_tolerancia(
            caminho,
            valor_referencia,
            valor_atual,
            tolerancia_percentual,
        ):
            diferencas.append(
                montar_item_diferenca(
                    caminho,
                    valor_referencia,
                    valor_atual,
                )
            )

    diferencas.sort(key=lambda item: item["métrica"])

    return {
        "diferencas": diferencas,
    }


def teste_gerar_comparacao():
    referencia_path = benchmark_report_referencia_path()
    atual_path = benchmark_report_path()
    output_path = benchmark_report_comparacao_path()

    assert referencia_path.exists(), (
        f"Benchmark de referência não encontrado: {referencia_path}"
    )

    assert atual_path.exists(), (
        f"Benchmark atual não encontrado: {atual_path}. "
        "Execute primeiro gerar_relatorio.py."
    )

    referencia_json = carregar_json(referencia_path)
    atual_json = carregar_json(atual_path)

    comparacao = comparar_benchmark_reports(
        referencia_json,
        atual_json,
        tolerancia_percentual=TOLERANCIA_PERCENTUAL,
    )

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(comparacao, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), (
        f"Falha ao gerar relatório de comparação: {output_path}"
    )