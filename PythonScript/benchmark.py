import sys
import time

def modo_benchmark_pytest():
    return "--benchmark" in sys.argv

def emitir_evento_pytest(evento):
    if ("--benchmark" in sys.argv):
        print(f"BENCHMARK:{evento}", flush=True)
