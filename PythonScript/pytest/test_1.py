import sys
import time
import json
import statistics
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent))
from PythonScript import main

def medir(nome, func, rodadas=10, ignorar=1):
    runs_all = []

    # executa tudo (incluindo warm-up)
    for _ in range(rodadas):
        inicio = time.perf_counter()
        func()
        fim = time.perf_counter()
        runs_all.append(fim - inicio)

    # separa warm-up
    runs_used = runs_all[ignorar:]
    ignored_runs = runs_all[:ignorar]

    return nome, {
        "runs_total": rodadas,
        "runs_used": len(runs_used),
        "ignored_runs": len(ignored_runs),

        "statistics": {
            "mean": statistics.mean(runs_used),
            "median": statistics.median(runs_used),
            "min": min(runs_used),
            "max": max(runs_used),
            "stddev": statistics.stdev(runs_used) if len(runs_used) > 1 else 0
        },

        "runs": [round(t, 6) for t in runs_used]
    }


def test_pipeline():

    videos = [
        str(p) for p in (BASE_DIR / "videos").iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".mov", ".avi", ".dav", ".avi"}
    ]

    resultados = []

    def run_txt():
        sys.argv = [
            "PythonScript.exe",
            "|".join(videos),
            "Arquivos -> lista de caminhos em .txt",
            "--benchmark_pytest"
        ]
        main()

    nome, dados = medir("txt", run_txt, rodadas=10, ignorar=1)
    resultados.append((nome, dados))

    # simplificado
    def run_simplificado():
        sys.argv = [
            "PythonScript.exe",
            "|".join(videos),
            "Vídeos -> tabela simplificada de informações em .csv",
            "--benchmark_pytest"
        ]
        main()

    nome, dados = medir("simplificado", run_simplificado, rodadas=10, ignorar=1)
    resultados.append((nome, dados))

    # completo
    def run_completo():
        sys.argv = [
            "PythonScript.exe",
            "|".join(videos),
            "Vídeos -> tabela completa de informações em .csv",
            "--benchmark_pytest"
        ]
        main()

    nome, dados = medir("completo", run_completo, rodadas=10, ignorar=1)
    resultados.append((nome, dados))

    output = {
        "videos": videos,
        "resultados": resultados
    }
    
    import platform
    aliases = {
    "MA2023127403": "notebook",
    }   
    machine_name = platform.node().strip().upper()
    machine_name = aliases.get(machine_name, machine_name.lower())
    
    with open(BASE_DIR / f"PythonScriptSelection_{machine_name}_result.json", "w", encoding="utf-8-sig") as f:
        json.dump(output, f, indent=4)