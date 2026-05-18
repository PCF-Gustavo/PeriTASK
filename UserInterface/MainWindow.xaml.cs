using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Windows;
using System.IO;
using System.Windows.Controls;
using static UserInterface.MainWindow;
using Microsoft.VisualBasic;

namespace UserInterface
{
    public partial class MainWindow : Window
    {
        private readonly List<string> itens_selecionados;
        private readonly Dictionary<string, Control> _renderedControls = new();

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
            LoadConfig();
            LoadComboBox();
        }

        private void Button_ok_Click(object sender, RoutedEventArgs e)
        {
            //Executa PythonScript
            string argumento_itens_selecionados = string.Join("|", itens_selecionados);

            if (ComboBox1.SelectedItem is not ComboBoxOption ComboBoxOption)
            {
                MessageBox.Show("Selecione uma opção na ComboBox.", "PeriTASK",
                    MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            var payload = new
            {
                combo_box_options_id = ComboBoxOption.id,
                controls = CollectUIState()
            };

            string argumento_ui = System.Text.Json.JsonSerializer.Serialize(payload);

            string argumento_ui_Base64 = Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(argumento_ui));

            string argumentosPython = $"\"{argumento_itens_selecionados}\" \"{argumento_ui_Base64}\"";

            var psi = new ProcessStartInfo
            {
                FileName = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "PythonScript.exe"),
                Arguments = argumentosPython,
                UseShellExecute = false,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

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
                        else if (e.Data.StartsWith("PAUSE:"))
                        {
                            progressViewModel.Status_Python = e.Data.Replace("PAUSE:", "");
                            progressViewModel.AguardandoContinuar = true;
                        }
                        else
                        {
                            progressViewModel.Status_Python = e.Data;
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
                        progressViewModel.Status_Python = e.Data;
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

        private void ComboBox1_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (ComboBox1.SelectedItem is ComboBoxOption item)
            {
                RenderUI(item);
            }
        }


        private ComboBoxOptionsConfig _config;
        private void LoadConfig()
        {
            string path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Compartilhado", "combo_box_options.json" );
            var json = File.ReadAllText(path);

            _config = System.Text.Json.JsonSerializer.Deserialize<ComboBoxOptionsConfig>(json);
        }

        private void LoadComboBox()
        {
            ComboBox1.ItemsSource = _config.combo_box_options;
            ComboBox1.DisplayMemberPath = "label";
        }

        private void RenderUI(ComboBoxOption option)
        {
            _renderedControls.Clear();
            DynamicPanel.Children.Clear();

            var controls = option?.ui?.controls;
            if (controls == null)
                return;

            
            foreach (var control in controls)
            {
                
                if (control.type != "checkbox")
                    continue;

                var checkbox = new CheckBox
                {
                    Name = control.id,
                    Content = control.text,
                    IsEnabled = control.enabled ?? true,
                    IsChecked = control.@checked ?? false
                };
                _renderedControls[control.id] = checkbox;
                DynamicPanel.Children.Add(checkbox);
            }
        }

        private Dictionary<string, object> CollectUIState()
        {
            var result = new Dictionary<string, object>();

            foreach (var kvp in _renderedControls)
            {
                switch (kvp.Value)
                {
                    case CheckBox cb:
                        result[kvp.Key] = cb.IsChecked ?? false;
                        break;
                }
            }

            return result;
        }
    }

    public class ComboBoxOption
    {
        public string id { get; set; }
        public string label { get; set; }
        public UiConfig ui { get; set; }
    }

    public class UiConfig
    {
        public List<ControlConfig> controls { get; set; }
    }

    public class ControlConfig
    {
        public string type { get; set; }
        public string id { get; set; }
        public string text { get; set; }
        public bool? enabled { get; set; }
        public bool? @checked { get; set; }
    }

    public class ComboBoxOptionsConfig
    {
        public List<ComboBoxOption> combo_box_options { get; set; }
    }

}
