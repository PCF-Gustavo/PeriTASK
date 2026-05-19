using System;
using System.Diagnostics;
using System.Windows;

namespace UserInterface
{
    public static class execucao_python
    {
        public static void Executar(ProcessStartInfo psi, Window janelaPrincipal)
        {
            var process = new Process { StartInfo = psi, EnableRaisingEvents = true };

            ProgressViewModel progressViewModel = null;

            progressViewModel = new ProgressViewModel(
                cancelar: () =>
                {
                    if (!process.HasExited)
                        process.Kill();

                    Application.Current.Shutdown();
                },
                continuar: () =>
                {
                    if (!process.HasExited)
                    {
                        progressViewModel.Status_Python = "Continuando...";
                        progressViewModel.AguardandoContinuar = false;

                        process.StandardInput.WriteLine("CONTINUAR");
                        process.StandardInput.Flush();
                    }
                }
            );

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
            janelaPrincipal.Close();

            // Captura saída do Python
            process.OutputDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                {
                    progressWindow.Dispatcher.Invoke(() =>
                    {
                        saida_python.ProcessarLinha(e.Data, progressViewModel);
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
                        saida_python.ProcessarErro(e.Data, progressViewModel);
                    });
                }
            };

            // Fecha a janela quando o processo Python terminar
            process.Exited += (s, e) =>
            {
                progressWindow.Dispatcher.Invoke(() =>
                {
                    if (process.ExitCode == 0)
                    {
                        progressViewModel.Progress = 100; // garante barra cheia

                        progressWindow.FechamentoProgramatico = true;
                        progressWindow.Close();
                    }
                });
            };

            progressViewModel.Status_Python = "Carregando Python...";

            // Inicia o processo
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
        }
    }
}