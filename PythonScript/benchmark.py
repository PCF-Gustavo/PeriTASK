import sys
import time

MODO_BENCHMARK = "--benchmark" in sys.argv

def emitir_evento(evento):
    if MODO_BENCHMARK:
        print(f"BENCHMARK:{evento}", flush=True)
        time.sleep(5)