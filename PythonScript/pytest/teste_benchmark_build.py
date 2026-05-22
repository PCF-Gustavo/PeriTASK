"""
===========================================================
BENCHMARK: TEMPO DE BUILD RELEASE DO INSTALADOR
===========================================================
Mede:
- Instalador via MSBuild Release|x64

Observação:
- O Instalador.wixproj já inclui o build do projeto como um todo:
  AddContextMenu, UserInterface e PythonScript via Nuitka.

Também registra:
- tempo total do build do instalador
- tamanho final do instalador .msi em MB
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from utilitario_pytest import (
    BASE_DIR,
    PROJECT_ROOT,
    machine_name,
    benchmark_build_path
)


# ===========================
# CONFIGURAÇÃO
# ===========================

CONFIGURATION = "Release"
PLATFORM = "x64"


PROJECT_TO_BUILD = {
    "name": "Instalador",
    "type": "msbuild",
    "path": PROJECT_ROOT / "Instalador" / "Instalador.wixproj",
    "configuration": CONFIGURATION,
    "platform": PLATFORM,
}


# ===========================
# MSBUILD
# ===========================

def encontrar_msbuild() -> str:
    """
    Localiza preferencialmente o MSBuild do Visual Studio completo,
    antes de cair para BuildTools ou PATH.

    Ordem:
    1. Visual Studio Community
    2. Visual Studio Professional
    3. Visual Studio Enterprise
    4. Visual Studio BuildTools
    5. PATH
    """
    vswhere = (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft Visual Studio"
        / "Installer"
        / "vswhere.exe"
    )

    produtos_preferidos = [
        "Microsoft.VisualStudio.Product.Community",
        "Microsoft.VisualStudio.Product.Professional",
        "Microsoft.VisualStudio.Product.Enterprise",
        "Microsoft.VisualStudio.Product.BuildTools",
    ]

    if vswhere.exists():
        for produto in produtos_preferidos:
            result = subprocess.run(
                [
                    str(vswhere),
                    "-latest",
                    "-products",
                    produto,
                    "-requires",
                    "Microsoft.Component.MSBuild",
                    "-find",
                    r"MSBuild\Current\Bin\MSBuild.exe",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            candidatos = [
                Path(linha.strip())
                for linha in result.stdout.splitlines()
                if linha.strip()
            ]

            for candidato in candidatos:
                if candidato.exists():
                    return str(candidato)

    caminhos_padrao = [
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"),
    ]

    for candidato in caminhos_padrao:
        if candidato.exists():
            return str(candidato)

    msbuild = shutil.which("msbuild")
    if msbuild:
        return msbuild

    assert False, (
        "MSBuild não encontrado. "
        "Verifique se o Visual Studio 2022 ou Build Tools está instalado "
        "com o componente MSBuild."
    )


def criar_args_build(project: dict) -> list[str]:
    project_path = project["path"]
    project_configuration = project.get("configuration", CONFIGURATION)
    project_platform = project.get("platform", PLATFORM)

    assert project_path.exists(), f"Projeto não encontrado: {project_path}"

    args = [
        encontrar_msbuild(),
        str(project_path),
        "/t:Build",
        f"/p:Configuration={project_configuration}",
        f"/p:Platform={project_platform}",
        "/m",
        "/v:minimal",
        "/nologo",
    ]

    # Quando o Instalador.wixproj é compilado diretamente,
    # SolutionDir não vem automaticamente da .sln.
    # O .wixproj usa $(SolutionDir) para localizar PythonScript\venv,
    # Compartilhado, Instalador\build etc.
    solution_dir = str(PROJECT_ROOT) + "\\"
    args.append(f"/p:SolutionDir={solution_dir}")

    return args


# ===========================
# TAMANHO DO INSTALADOR
# ===========================

def obter_info_instalador() -> dict:
    pasta_instalador = (
        PROJECT_ROOT
        / "Instalador"
        / "bin"
        / PLATFORM
        / CONFIGURATION
    )

    candidatos = list(pasta_instalador.glob("*.msi"))
    assert candidatos, f"Nenhum instalador .msi encontrado em: {pasta_instalador}"

    instalador = max(candidatos, key=lambda p: p.stat().st_mtime)
    tamanho_mb = instalador.stat().st_size / (1024 * 1024)

    return {
        "size_mb": round(tamanho_mb, 2),
    }


# ===========================
# MEDIÇÃO
# ===========================

def medir_build_instalador(project: dict) -> float:
    args = criar_args_build(project)

    inicio = time.perf_counter()
    result = subprocess.run(
        args,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    fim = time.perf_counter()

    tempo_s = round(fim - inicio, 2)

    assert result.returncode == 0, (
        f"Build do projeto '{project['name']}' falhou "
        f"com código {result.returncode}.\n\n"
        f"Comando:\n{' '.join(args)}\n\n"
        f"STDOUT:\n{result.stdout}\n\n"
        f"STDERR:\n{result.stderr}"
    )

    return tempo_s


# ===========================
# TESTE / BENCHMARK
# ===========================

def teste_benchmark_build():
    time_s = medir_build_instalador(PROJECT_TO_BUILD)
    info_instalador = obter_info_instalador()

    output = {
        "time_s": time_s,
        "size_mb": info_instalador["size_mb"],
    }

    output_path = benchmark_build_path()
    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    assert output_path.exists(), f"Falha ao gerar arquivo: {output_path}"