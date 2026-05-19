using System;
using System.Diagnostics;
using System.IO;

namespace UserInterface
{
    public static class processo_python
    {
        public static ProcessStartInfo CriarProcessStartInfoModoNormal(
            string argumentoItensSelecionados,
            string argumentoUiBase64
        )
        {
            string argumentosPython = $"\"{argumentoItensSelecionados}\" \"{argumentoUiBase64}\"";

            return new ProcessStartInfo
            {
                FileName = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "PythonScript.exe"),
                Arguments = argumentosPython,
                UseShellExecute = false,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };
        }

        public static ProcessStartInfo CriarProcessStartInfoBenchmark(
            string solutionRoot,
            string argumentoItensSelecionados,
            string argumentoUiBase64
        )
        {
#if DEBUG
            string pythonExe = Path.Combine(
                solutionRoot,
                "PythonScript",
                "venv",
                "Scripts",
                "python.exe"
            );

            string mainPy = Path.Combine(
                solutionRoot,
                "PythonScript",
                "main.py"
            );

            return new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = $"\"{mainPy}\" \"{argumentoItensSelecionados}\" \"{argumentoUiBase64}\" --benchmark",
                WorkingDirectory = Path.Combine(solutionRoot, "PythonScript"),
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };
#else
            string pythonExe = Path.Combine(
                AppDomain.CurrentDomain.BaseDirectory,
                "PythonScript.exe"
            );

            return new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = $"\"{argumentoItensSelecionados}\" \"{argumentoUiBase64}\" --benchmark",
                WorkingDirectory = AppDomain.CurrentDomain.BaseDirectory,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };
#endif
        }
    }
}