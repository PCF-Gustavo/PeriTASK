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
    public class StartupBenchmarkHotTest
    {
        private static readonly string ExePath =
            Path.GetFullPath(
                Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory,
                    @"..\..\..\..\Instalador\dist\PythonScript.exe"));

        [TestMethod]
        public void Benchmark_Startup_Time()
        {
            Assert.IsTrue(File.Exists(ExePath),
                $"Executável não encontrado: {ExePath}");

            const int runs = 10;

            List<double> results = new();

            for (int i = 0; i < runs; i++)
            {
                ProcessStartInfo psi = new()
                {
                    FileName = ExePath,
                    Arguments = "--benchmark",
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
            var valid = results.Skip(1).ToList();

            double mean = valid.Average();
            double median = valid.OrderBy(x => x).ElementAt(valid.Count / 2);
            double min = valid.Min();
            double max = valid.Max();

            double stddev = Math.Sqrt(valid.Average(v =>
                Math.Pow(v - mean, 2)));

            var output = new
            {
                runs_total = results.Count,
                runs_used = valid.Count,
                ignored_runs = 1,

                statistics = new
                {
                    mean,
                    median,
                    min,
                    max,
                    stddev
                },

                runs = valid
            };

            string file = Path.GetFullPath(
                Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory,
                    @"..\..\..\StartupBenchmarkHotTest_result.json"));

            File.WriteAllText(
                file,
                JsonSerializer.Serialize(output, new JsonSerializerOptions
                {
                    WriteIndented = true
                }));
        }
    }
}