using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Windows;
using System.IO;
using System.Windows.Controls;

namespace UserInterface
{
    public partial class MainWindow : Window
    {
        private readonly List<string> itens_selecionados;

        public MainWindow()
        {
            // Pega argumentos da linha de comando
            itens_selecionados = Environment.GetCommandLineArgs().Skip(1).ToList();

            // Executa apenas se não estiver no debug
            if (!Debugger.IsAttached)
            {
                if (itens_selecionados == null || itens_selecionados.Count == 0)
                {
                    MessageBox.Show("Nenhum arquivo recebido.", "PeriTASK", 
                        MessageBoxButton.OK, MessageBoxImage.Error);
                    Application.Current.Shutdown();
                    return;
                }
            }

            InitializeComponent();
        }

        private void Button_ok_Click(object sender, RoutedEventArgs e)
        {
            //Executa PythonScript
            string argumento_itens_selecionados = string.Join("|", itens_selecionados);

            if (ComboBox1.SelectedItem is not ComboBoxItem item)
            {
                MessageBox.Show("Selecione uma opção na ComboBox.", "PeriTASK",
                    MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }
            string selecao_ComboBox = item.Content.ToString();
            
            string argumentosPython = $"\"{argumento_itens_selecionados}\" \"{selecao_ComboBox}\"";

            var psi = new ProcessStartInfo
            {
                FileName = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "PythonScript.exe"),
                Arguments = argumentosPython,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            var process = new Process { StartInfo = psi, EnableRaisingEvents = true };

            // Cria ViewModel com CancelCommand
            var progressViewModel = new ProgressViewModel(() =>
            {
                if (!process.HasExited)
                    process.Kill();
                Application.Current.Shutdown();
            });

            // Cria janela de progresso e associa ViewModel
            var progressWindow = new ProgressWindow
            {
                DataContext = progressViewModel
            };

            // Mostra janela de progresso
            Application.Current.MainWindow = progressWindow;
            progressWindow.Show();

            // 🔥 FORÇA RENDER IMEDIATO
            progressWindow.Dispatcher.Invoke(
                System.Windows.Threading.DispatcherPriority.Render,
                new Action(() => { })
            );

            // Fecha janela principal
            this.Close();

            // Captura saída do Python
            process.OutputDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                {
                    progressWindow.Dispatcher.Invoke(() =>
                    {
                        // Atualiza barra de progresso
                        if (e.Data.StartsWith("PROGRESS:"))
                        {
                            if (int.TryParse(e.Data.Replace("PROGRESS:", ""), out int _progresso))
                                progressViewModel.Progress = _progresso;
                        }
                        // Atualiza Status
                        else if (e.Data.StartsWith("STATUS:"))
                            progressViewModel.Status_Python = e.Data.Replace("STATUS:", "");
                        else
                        {
                            // 👇 QUALQUER PRINT DO PYTHON
                            MessageBox.Show(e.Data, "PeriTASK",
                                MessageBoxButton.OK, MessageBoxImage.Error);
                        }
                    });
                }
            };

            // Captura erros do Python
            process.ErrorDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                {
                    progressWindow.Dispatcher.Invoke(() =>
                    {
                        progressViewModel.Status_Python = "Erro: " + e.Data;
                    });
                }
            };

            // Fecha a janela quando o processo Python terminar
            process.Exited += (s, e) =>
            {
                progressWindow.Dispatcher.Invoke(() =>
                {
                    progressViewModel.Progress = 100; // garante barra cheia
                    progressWindow.Close();
                });
            };

            // Inicia o processo
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
        }
    }
}
