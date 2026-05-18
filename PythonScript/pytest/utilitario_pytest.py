import platform
from pathlib import Path
import sys
import json
import base64


# =========================
# PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parent  # PeriTASK\PythonScript\pytest
ROOT = BASE_DIR.parent  # PeriTASK\PythonScript
EXE_PATH = BASE_DIR.parents[1] / "Instalador/build/main.dist/PythonScript.exe"

sys.path.append(str(ROOT))
from processador_argumento_ui import carregar_combo_box_options

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

def criar_argumento_ui(combo_box_options_id, controls=None):
    if controls is None:
        controls = {}

    payload = {
        "combo_box_options_id": combo_box_options_id,
        "controls": controls
    }

    json_payload = json.dumps(payload, ensure_ascii=False)
    return base64.b64encode(json_payload.encode("utf-8")).decode("utf-8")