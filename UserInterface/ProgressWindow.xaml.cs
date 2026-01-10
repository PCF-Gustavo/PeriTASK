using System;
using System.Diagnostics;
using System.Windows;
using System.IO;


namespace UserInterface
{
    public partial class ProgressWindow : Window
    {
        private readonly Process _process;
        private readonly ProgressViewModel _vm;
        private readonly string _arquivoTmp;


        public ProgressWindow(Process process)
        {
            InitializeComponent();

            _process = process;

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            _arquivoTmp = Path.Combine(baseDir, "caminho_dos_arquivos.txt.tmp");

            _vm = new ProgressViewModel(CancelarProcesso);
            DataContext = _vm;

            _process.OutputDataReceived += Process_OutputDataReceived;
            _process.Exited += Process_Exited;
            _process.EnableRaisingEvents = true;

            _process.BeginOutputReadLine();
        }


        private void Process_OutputDataReceived(object sender, DataReceivedEventArgs e)
        {
            if (string.IsNullOrWhiteSpace(e.Data))
                return;

            if (e.Data.StartsWith("PROGRESS:") &&
                int.TryParse(e.Data.Replace("PROGRESS:", ""), out int valor))
            {
                Dispatcher.Invoke(() => _vm.Progress = valor);
            }
        }

        private void Process_Exited(object sender, EventArgs e)
        {
            Dispatcher.Invoke(() =>
            {
                Close();
            });
        }

        private void CancelarProcesso()
        {
            try
            {
                if (!_process.HasExited)
                {
                    _process.Kill(entireProcessTree: true);
                    _process.CancelOutputRead();
                }
            }
            catch { }

            Close();
            Application.Current.Shutdown();
        }


    }
}



