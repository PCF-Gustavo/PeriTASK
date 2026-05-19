using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Windows;

namespace UserInterface
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            if (e.Args.Contains("--benchmark"))
            {
                int exitCode = ExecutarBenchmarkCli(e.Args);
                Shutdown(exitCode);
                return;
            }

            ShutdownMode = ShutdownMode.OnMainWindowClose;

            var mainWindow = new MainWindow();
            MainWindow = mainWindow;
            mainWindow.Show();
        }

        private int ExecutarBenchmarkCli(string[] args)
        {
            try
            {
                string rota = ObterValorDepoisDe(args, "--route");

                if (string.IsNullOrWhiteSpace(rota))
                {
                    Console.WriteLine("BENCHMARK:ERRO:Argumento --route não informado");
                    return 2;
                }

                var itensSelecionados = args
                    .Where(a => a != "--benchmark")
                    .Where(a => a != "--route")
                    .Where(a => a != rota)
                    .ToList();

                if (itensSelecionados.Count == 0)
                {
                    Console.WriteLine("BENCHMARK:ERRO:Nenhum arquivo informado");
                    return 3;
                }

                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string solutionRoot = EncontrarRaizSolucao(baseDir);

                string comboPath = Path.Combine(
                    solutionRoot,
                    "Compartilhado",
                    "combo_box_options.json"
                );

                if (!File.Exists(comboPath))
                {
                    Console.WriteLine($"BENCHMARK:ERRO:combo_box_options.json não encontrado: {comboPath}");
                    return 4;
                }

                ValidarRotaExiste(comboPath, rota);

                string argumentoItensSelecionados = string.Join("|", itensSelecionados);

                var payload = new
                {
                    combo_box_options_id = rota,
                    controls = new { }
                };

                string argumentoUiJson = JsonSerializer.Serialize(payload);

                string argumentoUiBase64 = Convert.ToBase64String(
                    Encoding.UTF8.GetBytes(argumentoUiJson)
                );

                var psi = CriarProcessStartInfoPython(
                    solutionRoot,
                    argumentoItensSelecionados,
                    argumentoUiBase64
                );

                using var process = new Process();
                process.StartInfo = psi;

                process.OutputDataReceived += (_, ev) =>
                {
                    if (!string.IsNullOrWhiteSpace(ev.Data))
                    {
                        Console.WriteLine(ev.Data);
                        Console.Out.Flush();
                    }
                };

                process.ErrorDataReceived += (_, ev) =>
                {
                    if (!string.IsNullOrWhiteSpace(ev.Data))
                    {
                        Console.Error.WriteLine(ev.Data);
                        Console.Error.Flush();
                    }
                };

                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();

                return process.ExitCode;
            }
            catch (Exception ex)
            {
                Console.WriteLine("BENCHMARK:ERRO:" + ex);
                return 1;
            }
        }

        private static string ObterValorDepoisDe(string[] args, string nomeArgumento)
        {
            int index = Array.IndexOf(args, nomeArgumento);

            if (index >= 0 && index + 1 < args.Length)
                return args[index + 1];

            return null;
        }

        private static void ValidarRotaExiste(string comboPath, string rota)
        {
            string json = File.ReadAllText(comboPath, Encoding.UTF8);

            using var doc = JsonDocument.Parse(json);

            var opcoes = doc.RootElement
                .GetProperty("combo_box_options")
                .EnumerateArray();

            bool existe = opcoes.Any(item =>
                item.TryGetProperty("id", out var idProp) &&
                idProp.GetString() == rota
            );

            if (!existe)
                throw new InvalidOperationException(
                    $"Rota não encontrada no combo_box_options.json: {rota}"
                );
        }

        private static ProcessStartInfo CriarProcessStartInfoPython(
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

        private static string EncontrarRaizSolucao(string inicio)
        {
            var dir = new DirectoryInfo(inicio);

            while (dir != null)
            {
                if (File.Exists(Path.Combine(dir.FullName, "PeriTASK.sln")))
                    return dir.FullName;

                dir = dir.Parent;
            }

            throw new DirectoryNotFoundException(
                "Não foi possível encontrar a raiz da solução PeriTASK.sln"
            );
        }
    }
}