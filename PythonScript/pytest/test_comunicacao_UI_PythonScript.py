import os
import sys
import subprocess
from pathlib import Path
from utilitario_pytest import ROOT

sys.path.append(str(ROOT))
from processador_argumento_ui import carregar_combo_box_options


def test_comunicacao_UI_PythonScript():
    ui_exe = (
        Path(__file__).resolve().parents[2]
        / "UserInterface"
        / "bin"
        / "x64"
        / "Debug"
        / "net8.0-windows"
        / "UserInterface.exe"
    )

    data = carregar_combo_box_options()

    rotas = [item["id"] for item in data["combo_box_options"]]

    assert rotas, "Nenhuma rota encontrada no combo_box_options.json"

    pasta_teste = Path(os.getenv("TEMP")) / "PeriTASK_UI_CLI_Test"
    pasta_teste.mkdir(parents=True, exist_ok=True)

    arquivo_teste = pasta_teste / "arquivo_teste.txt"
    arquivo_teste.write_text(
        "arquivo usado no teste de integração UI -> Python",
        encoding="utf-8"
    )

    falhas = []

    for rota in rotas:
        result = subprocess.run(
            [
                str(ui_exe),
                "--benchmark",
                "--route",
                rota,
                str(arquivo_teste),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        saida = (result.stdout or "") + "\n" + (result.stderr or "")

        marcador_ready = "BENCHMARK:PERITASK_READY"
        marcador_rota = f"BENCHMARK:ROTA:{rota}"

        if result.returncode != 0:
            falhas.append(
                f"Rota '{rota}' retornou código {result.returncode}\n\n{saida}"
            )
            continue

        if marcador_ready not in saida:
            falhas.append(
                f"Rota '{rota}' não emitiu marcador de inicialização: "
                f"{marcador_ready}\n\n{saida}"
            )

        if marcador_rota not in saida:
            falhas.append(
                f"Rota '{rota}' não emitiu marcador esperado: "
                f"{marcador_rota}\n\n{saida}"
            )

    assert not falhas, "\n\n" + "\n\n".join(falhas)