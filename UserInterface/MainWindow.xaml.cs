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
            ConfigurarComboBox();
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

            string argumento_ui_Base64 = payload_ui.CriarArgumentoUiBase64(
                ComboBoxOption.id,
                CollectUIState()
            );

            var psi = processo_python.CriarProcessStartInfoModoNormal(
                argumento_itens_selecionados,
                argumento_ui_Base64
            );

            execucao_python.Executar(psi, this);
        }

        private void ComboBox1_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (ComboBox1.SelectedItem is ComboBoxOption item)
            {
                RenderUI(item);
            }
        }


        private ComboBoxOptionsConfig _config;

        private void ConfigurarComboBox()
        {
            _config = ComboBoxOptionsUI.Configurar(ComboBox1);
        }

        private void RenderUI(ComboBoxOption option)
        {
            interface_dinamica.Renderizar(
                option,
                DynamicPanel,
                _renderedControls
            );
        }

        private Dictionary<string, object> CollectUIState()
        {
            return interface_dinamica.ColetarEstado(_renderedControls);
        }
    }
}
