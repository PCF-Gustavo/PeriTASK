from pathlib import Path
import sys

def obter_pasta_raiz():
    exe_path = Path(sys.argv[0])

    # Se for um executável real
    if exe_path.suffix == ".exe":
        return exe_path.parent

    # Caso contrário, está rodando como script
    # return Path(__file__).parent.parent.parent
    return Path(__file__).resolve().parents[2]