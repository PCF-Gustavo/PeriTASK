"""
===========================================================
TESTE DE EXECUÇÃO REAL DO EXE
===========================================================

Este teste valida se as principais funcionalidades da aplicação
executam corretamente a partir do executável final.

✔ O que este teste valida:
- Le funções de combo_box_options.json
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
from utilitario_pytest import BASE_DIR, ROOT, EXE_PATH, obter_combo_box_options_ids, criar_argumento_ui
sys.path.append(str(ROOT))

pasta_saida = Path(os.getenv("USERPROFILE")) / "Desktop" / "PeriTASK_pytest"

if pasta_saida.exists():
    shutil.rmtree(pasta_saida)

if not EXE_PATH.exists():
    pytest.skip(f"Exe não encontrado: {EXE_PATH}")


# ===========================
# INPUTS FIXOS
# ===========================

arquivos = [str(p) for p in (BASE_DIR / "videos").iterdir() if p.is_file()]
arquivos_argumentos = "|".join(arquivos)

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


def validar_arquivo(path: Path):
    assert path.exists(), f"Arquivo não foi criado: {path}"
    assert path.stat().st_size > 0, f"Arquivo vazio: {path}"


def validar_csv(path: Path):
    validar_arquivo(path)

    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    assert len(rows) >= 2, "CSV sem header ou sem linhas"
    assert len(rows[0]) > 0, "CSV sem colunas"


def validar_txt(path: Path):
    validar_arquivo(path)

    content = path.read_text(encoding="utf-8-sig").strip()

    assert content, "TXT vazio"
    assert len(content.splitlines()) > 0, "TXT sem linhas válidas"


# ===========================
# TESTE GENÉRICO
# ===========================

@pytest.mark.parametrize("func_id", obter_combo_box_options_ids())
def test_exe_execucao_generica(func_id):
    if pasta_saida.exists():
        shutil.rmtree(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    args = [
        str(EXE_PATH),
        arquivos_argumentos,
        criar_argumento_ui(func_id),
        "--benchmark"
    ]

    executar(args)

    # validação GENÉRICA de saída (sem saber tipo exato)
    arquivos = list(pasta_saida.glob("*"))

    for f in arquivos:
        validar_arquivo(f)

        if f.suffix == ".csv":
            validar_csv(f)
        elif f.suffix == ".txt":
            validar_txt(f)