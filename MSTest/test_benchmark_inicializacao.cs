using Microsoft.VisualStudio.TestTools.UnitTesting;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace MSTest
{
    [TestClass]
    public class test_benchmark_inicializacao
    {
        public TestContext TestContext { get; set; }
        //===========================
        //CONFIG RUNS
        //===========================
        const int WARMUP_RUNS = 1;
        const int USED_RUNS = 9;

        private static readonly string ExePath =
            Path.GetFullPath(
                Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory,
                    @"..\..\..\..\Instalador\build\main.dist\PythonScript.exe"));

        [TestMethod]
        public void Benchmark_Startup_Time()
        {
            Assert.IsTrue(File.Exists(ExePath),
                $"Executável não encontrado: {ExePath}");



            List<double> results = new();

            for (int i = 0; i < WARMUP_RUNS+USED_RUNS; i++)
            {
                ProcessStartInfo psi = new()
                {
                    FileName = ExePath,
                    Arguments = "--benchmark_MSTest",
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                using Process process = Process.Start(psi);

                Stopwatch sw = Stopwatch.StartNew();

                while (!process.StandardOutput.EndOfStream)
                {
                    string line = process.StandardOutput.ReadLine();

                    if (line != null && line.Contains("PERITASK_READY"))
                    {
                        sw.Stop();
                        results.Add(sw.Elapsed.TotalSeconds);
                        break;
                    }
                }

                if (!process.HasExited)
                    process.Kill(true);
            }

            SaveResults(results);
        }

        private void SaveResults(List<double> results)
        {
            if (results.Count == 0)
                throw new Exception("Nenhum resultado coletado.");

            // ignora primeira execução (warmup)
            var valid = results.Skip(WARMUP_RUNS).ToList();

            double mean = Math.Round(valid.Average(), 4);
            double min = Math.Round(valid.Min(), 4);
            double max = Math.Round(valid.Max(), 4);

            Console.WriteLine($"tempo médio: {mean} segundos");

            var output = new
            {
                run_info = new
                {
                    warmup_runs = results.Count - valid.Count,
                    used_runs = valid.Count,
                },

                results = new
                {
                    statistics = new
                    {
                        time_s = new
                        {
                            mean,
                            min,
                            max
                        }
                    }
                }
            };

            Dictionary<string, string> aliases = new()
            {
                ["MA2023127403"] = "notebook",
            };

            string machineName = Environment.MachineName;

            if (aliases.TryGetValue(machineName, out string alias))
                machineName = alias;

            string file = Path.GetFullPath(
                Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory,
                    $@"..\..\..\test_benchmark_inicializacao_{machineName}.json"));

            File.WriteAllText(
                file,
                JsonSerializer.Serialize(output, new JsonSerializerOptions
                {
                    WriteIndented = true
                }));
        }
    }
}