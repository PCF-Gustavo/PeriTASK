using System;
using System.Diagnostics;
using System.Windows;

namespace UserInterface
{
    public partial class ProgressWindow : Window
    {
        private readonly ProgressViewModel _vm;

        public ProgressWindow(Process process)
        {
            InitializeComponent();

            _vm = new ProgressViewModel();
            DataContext = _vm;

            process.OutputDataReceived += Process_OutputDataReceived;
            process.BeginOutputReadLine();
        }

        private void Process_OutputDataReceived(object sender, DataReceivedEventArgs e)
        {
            if (string.IsNullOrWhiteSpace(e.Data))
                return;

            // PROGRESS:42
            if (e.Data.StartsWith("PROGRESS:"))
            {
                if (double.TryParse(e.Data.Substring(9), out double valor))
                {
                    Dispatcher.Invoke(() =>
                    {
                        _vm.Progress = valor;
                    });
                }
            }
            // DONE
            else if (e.Data == "DONE")
            {
                Dispatcher.Invoke(() =>
                {
                    _vm.Progress = 100;
                    Close(); // 🔹 FECHA AO CONCLUIR
                });
            }
        }
    }
}
