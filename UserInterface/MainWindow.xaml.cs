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
        private List<string> arquivos_selecionados;

        public MainWindow()
        {
            InitializeComponent();

            // pega os argumentos (ignora o exe)
            arquivos_selecionados = Environment.GetCommandLineArgs()
                                               .Skip(1)
                                               .ToList();
        }

        private void Button_Click(object sender, RoutedEventArgs e)
        {
            if (arquivos_selecionados == null || arquivos_selecionados.Count == 0)
            {
                MessageBox.Show("Nenhum arquivo recebido.");
                return;
            }

            ExecutarPython(arquivos_selecionados);

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
        }
    }
}
