using System.Windows;

namespace UserInterface
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            if (e.Args.Contains("--benchmark"))
            {
                int exitCode = Benchmark.ExecutarBenchmarkCli(e.Args);
                Shutdown(exitCode);
                return;
            }

            ShutdownMode = ShutdownMode.OnMainWindowClose;

            var mainWindow = new MainWindow();
            MainWindow = mainWindow;
            mainWindow.Show();
        }
    }
}