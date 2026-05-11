using Microsoft.VisualStudio.TestTools.UnitTesting;
using System;
using System.IO;
using System.Text.Json;

namespace MSTest
{
    [TestClass]
    public class zGenerate_Benchmark_Report
    {
        [TestMethod]
        public void GenerateBenchmarkReport()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;

            Dictionary<string, string> aliases = new()
            {
                ["MA2023127403"] = "notebook",
            };

            string machineName = Environment.MachineName;

            if (aliases.TryGetValue(machineName, out string alias))
                machineName = alias;

            // =========================
            // MSTest results
            // =========================
            string test_benchmark_inicializacao_str =
                Path.GetFullPath(Path.Combine(baseDir,
                $@"..\..\..\test_benchmark_inicializacao_{machineName}.json"));

            // =========================
            // Pytest result
            // =========================
            string test_benchmark_aplicacao_completa_str =
                Path.GetFullPath(Path.Combine(baseDir,
                $@"..\..\..\..\PythonScript\pytest\test_benchmark_aplicacao_completa_{machineName}.json"));

            // =========================
            // validações simples
            // =========================
            if (!File.Exists(test_benchmark_inicializacao_str))
                Assert.Fail($"Arquivo não encontrado: {test_benchmark_inicializacao_str}");

            if (!File.Exists(test_benchmark_aplicacao_completa_str))
                Assert.Fail($"Arquivo não encontrado: {test_benchmark_aplicacao_completa_str}");

            // =========================
            // leitura dos JSONs
            // =========================
            var MSTestJson = JsonSerializer.Deserialize<object>(
                File.ReadAllText(test_benchmark_inicializacao_str));

            var pytestJson = JsonSerializer.Deserialize<object>(
                File.ReadAllText(test_benchmark_aplicacao_completa_str));

            // =========================
            // merge final
            // =========================
            var combined = new
            {
                test_benchmark_inicializacao = MSTestJson,
                test_benchmark_aplicacao_completa = pytestJson
            };

            // =========================
            // output
            // =========================
            string outputPath = Path.GetFullPath(Path.Combine(
                baseDir,
                $@"..\..\..\..\BenchmarkReport_{machineName}.json"));

            File.WriteAllText(
                outputPath,
                JsonSerializer.Serialize(combined, new JsonSerializerOptions
                {
                    WriteIndented = true
                })
            );

            Assert.IsTrue(File.Exists(outputPath),
                "Falha ao gerar report combinado.");
        }
    }
}