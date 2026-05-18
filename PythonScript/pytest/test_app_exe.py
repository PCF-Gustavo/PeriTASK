"""
===========================================================
TESTE DE EXECUÇÃO REAL DO EXE
===========================================================

Este teste valida se as principais funcionalidades da aplicação
executam corretamente a partir do executável final.

✔ O que este teste valida:
- Execução real do EXE
- Parsing dos argumentos CLI
- Inicialização completa da aplicação
- Geração correta dos arquivos de saída
- Arquivos não vazios
- Integridade básica do output
"""

import os
import sys
import csv
import subprocess
import pytest
import shutil
from pathlib import Path
from utilitario_pytest import BASE_DIR, ROOT, EXE_PATH
sys.path.append(str(ROOT))
from utilitario.outros import obter_videos

pasta_saida = Path(os.getenv("USERPROFILE")) / "Desktop" / "PeriTASK_pytest"
if pasta_saida.exists(): shutil.rmtree(pasta_saida)

if not EXE_PATH.exists():
    pytest.skip(f"Exe não encontrado: {EXE_PATH}")


videos = obter_videos(list((BASE_DIR / "videos").iterdir()))
videos_argumentos = "|".join(str(v) for v in videos)


# ===========================
# HELPERS
# ===========================

def executar(args):
    result = subprocess.run(
        args,
        capture_output=True,
        text=True
    )

    
    print("\n===== STDOUT =====\n")
    print(result.stdout)

    print("\n===== STDERR =====\n")
    print(result.stderr)


    assert result.returncode == 0, (
        f"Execução falhou com código {result.returncode}"
    )


def validar_arquivo_existe(path):
    assert path.exists(), (
        f"Arquivo não foi criado: {path}"
    )

    assert path.stat().st_size > 0, (
        f"Arquivo vazio: {path}"
    )


def validar_txt(path):
    validar_arquivo_existe(path)

    content = path.read_text(encoding="utf-8-sig").strip()

    assert content, "TXT vazio"

    linhas = [l.strip() for l in content.splitlines() if l.strip()]

    assert len(linhas) > 0, (
        "TXT sem conteúdo válido"
    )


def validar_csv(path):
    validar_arquivo_existe(path)

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = list(csv.reader(f))

    assert len(reader) >= 2, (
        "CSV sem header ou sem linhas"
    )

    header = reader[0]

    assert len(header) > 0, (
        "CSV sem colunas"
    )


# ===========================
# TESTES
# ===========================

def test_output_txt():

    output = pasta_saida / "caminho_dos_arquivos.txt"

    args = [
        str(EXE_PATH),
        videos_argumentos,
        "lista_caminhos_txt",
        "--benchmark"
    ]

    executar(args)

    validar_txt(output)


def test_output_csv_simplificado():

    output = pasta_saida / "tabela_simplificada_de_informacoes.csv"

    args = [
        str(EXE_PATH),
        videos_argumentos,
        "videos_csv_simplificado",
        "--benchmark"
    ]

    executar(args)

    validar_csv(output)


def test_output_csv_completo():

    output = pasta_saida / "tabela_completa_de_informacoes.csv"

    args = [
        str(EXE_PATH),
        videos_argumentos,
        "videos_csv_completo",
        "--benchmark"
    ]

    executar(args)

    validar_csv(output)