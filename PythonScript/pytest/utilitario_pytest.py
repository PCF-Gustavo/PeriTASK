import platform
from pathlib import Path


# =========================
# PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parent  # PeriTASK\PythonScript\pytest
ROOT = BASE_DIR.parent  # PeriTASK\PythonScript
EXE_PATH = BASE_DIR.parents[1] / "Instalador/build/main.dist/PythonScript.exe"


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