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
        private readonly List<string> itens_selecionados;

        public MainWindow()
        {
            InitializeComponent();

            itens_selecionados = Environment.GetCommandLineArgs()
                                               .Skip(1) //ignora o exe
                                               .ToList();
        }

        private void Button_teste_Click(object sender, RoutedEventArgs e)
        {
            if (itens_selecionados == null || itens_selecionados.Count == 0)
            {
                MessageBox.Show("Nenhum arquivo recebido.");
                return;
            }

            ExecutarPython(itens_selecionados);
        }


        private void ExecutarPython(List<string> arquivos)
        {
            string argumentosPython = string.Join("|", arquivos);

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string pythonExe = Path.Combine(baseDir, "PythonScript.exe");

            var psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = $"\"{argumentosPython}\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            var process = new Process
            {
                StartInfo = psi,
                EnableRaisingEvents = true
            };

            process.Start();

            // 🔹 ABRE A JANELA DE PROGRESSO E ENTREGA O PROCESS
            var progressWindow = new ProgressWindow(process)
            {
                Owner = this
            };

            progressWindow.ShowDialog();

            // 🔹 APÓS O PYTHON TERMINAR E A JANELA FECHAR
            this.Close();
        }

    }
}
