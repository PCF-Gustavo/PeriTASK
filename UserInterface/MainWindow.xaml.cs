using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Windows;
using System.IO;

namespace UserInterface
{
    public partial class MainWindow : Window
    {
        private List<string> _arquivosSelecionados;

        public MainWindow()
        {
            InitializeComponent();

            // pega os argumentos (ignora o exe)
            _arquivosSelecionados = Environment.GetCommandLineArgs()
                                               .Skip(1)
                                               .ToList();
        }

        private void Button_Click(object sender, RoutedEventArgs e)
        {
            if (_arquivosSelecionados == null || _arquivosSelecionados.Count == 0)
            {
                MessageBox.Show("Nenhum arquivo recebido.");
                return;
            }

            ExecutarPython(_arquivosSelecionados);

            this.Close();
        }

        private void ExecutarPython(List<string> arquivos)
        {
            // junta no formato esperado pelo Python
            string argumentosPython = string.Join("|", arquivos);

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string pythonExe = Path.Combine(baseDir, "PythonScript.exe");

            var psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = $"\"{argumentosPython}\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi);
            //string resultado = process.StandardOutput.ReadToEnd();
            //process.WaitForExit();

            // opcional: mostrar onde o txt foi criado
            //if (!string.IsNullOrWhiteSpace(resultado))
            //{
            //    MessageBox.Show($"Arquivo criado em:\n{resultado.Trim()}");
            //}
        }
    }
}
