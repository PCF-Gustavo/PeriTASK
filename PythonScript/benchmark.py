import sys
import time

def modo_benchmark_MSTest():
    return "--benchmark_MSTest" in sys.argv

def modo_benchmark_pytest():
    return "--benchmark_pytest" in sys.argv

def emitir_evento(evento):
    if modo_benchmark_MSTest():
        print(f"BENCHMARK:{evento}", flush=True)
        time.sleep(5)