import sys
import time

def modo_benchmark_pytest():
    return "--benchmark_pytest" in sys.argv

def emitir_evento_MSTest(evento):
    if ("--benchmark_MSTest" in sys.argv):
        print(f"BENCHMARK:{evento}", flush=True)
        time.sleep(5)