using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;

namespace UserInterface
{
    public static class Benchmark
    {
        public static int ExecutarBenchmarkCli(string[] args)
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
                string solutionRoot = Caminhos.EncontrarRaizSolucao(baseDir);

                string comboPath = Path.Combine(
                    solutionRoot,
                    "Compartilhado",
                    "catalogo_de_comandos.json"
                );

                if (!File.Exists(comboPath))
                {
                    Console.WriteLine($"BENCHMARK:ERRO:catalogo_de_comandos.json não encontrado: {comboPath}");
                    return 4;
                }

                ValidarRotaExiste(comboPath, rota);

                string argumentoItensSelecionados = string.Join("|", itensSelecionados);

                string argumentoUiBase64 = payload_ui.CriarArgumentoUiBase64Benchmark(rota);

                var psi = processo_python.CriarProcessStartInfoBenchmark(
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
                .GetProperty("comandos")
                .EnumerateArray();

            bool existe = opcoes.Any(item =>
                item.TryGetProperty("id", out var idProp) &&
                idProp.GetString() == rota
            );

            if (!existe)
                throw new InvalidOperationException(
                    $"Rota não encontrada no catalogo_de_comandos.json: {rota}"
                );
        }
    }
}
