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
    public class StartupBenchmarkColdTest
    {
        private static readonly string BaseDir =
            AppDomain.CurrentDomain.BaseDirectory;

        private static readonly string ExePath =
            Path.GetFullPath(
                Path.Combine(
                    BaseDir,
                    @"..\..\..\..\Instalador\dist\PythonScript.exe"));

        private static readonly string EmptyStandbyPath =
            Path.Combine(BaseDir, "tools", "EmptyStandbyList.exe");

        [TestMethod]
        public void Benchmark_Cold_Startup_Time()
        {
            Assert.IsTrue(File.Exists(ExePath),
                $"Executável não encontrado: {ExePath}");

            Assert.IsTrue(File.Exists(EmptyStandbyPath),
                $"EmptyStandbyList não encontrado: {EmptyStandbyPath}");

            const int runs = 5;

            List<double> results = new();

            for (int i = 0; i < runs; i++)
            {
                ForceColdCache();

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

        private void ForceColdCache()
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = EmptyStandbyPath,
                    Arguments = "standbylist",
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                using var process = Process.Start(psi);
                process?.WaitForExit(3000);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Falha ao limpar cache: {ex.Message}");
            }

            // pequeno delay ajuda o Windows a estabilizar
            System.Threading.Thread.Sleep(1000);
        }

        private void SaveResults(List<double> results)
        {
            if (results.Count == 0)
                throw new Exception("Nenhum resultado coletado.");

            double mean = results.Average();
            double median = results.OrderBy(x => x).ElementAt(results.Count / 2);
            double min = results.Min();
            double max = results.Max();

            double stddev = Math.Sqrt(results.Average(v =>
                Math.Pow(v - mean, 2)));

            var output = new
            {
                runs_total = results.Count,

                statistics = new
                {
                    mean,
                    median,
                    min,
                    max,
                    stddev
                },

                runs = results
            };

            string file = Path.GetFullPath(
                Path.Combine(
                    BaseDir,
                    @"..\..\..\StartupBenchmarkColdTest_result.json"));

            File.WriteAllText(
                file,
                JsonSerializer.Serialize(output, new JsonSerializerOptions
                {
                    WriteIndented = true
                }));
        }
    }
}