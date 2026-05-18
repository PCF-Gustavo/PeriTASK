import platform
from pathlib import Path
import sys


# =========================
# PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parent  # PeriTASK\PythonScript\pytest
ROOT = BASE_DIR.parent  # PeriTASK\PythonScript
EXE_PATH = BASE_DIR.parents[1] / "Instalador/build/main.dist/PythonScript.exe"

sys.path.append(str(ROOT))
from processador_combo_box_options import carregar_combo_box_options

# =========================
# MACHINE NAME
# =========================

ALIASES = {
    "MA2023127403": "notebook",
}


def get_machine_name():
    name = platform.node().strip().upper()
    return ALIASES.get(name, name.lower())

machine_name = get_machine_name()

def obter_combo_box_options_ids():
    data = carregar_combo_box_options()
    return [item["id"] for item in data["combo_box_options"]]