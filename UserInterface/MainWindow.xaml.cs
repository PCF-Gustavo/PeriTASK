using System.Windows;
using System.Windows.Controls;

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

            if (!janela_principal.ValidarItensSelecionados(itens_selecionados))
                return;


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


        private void ConfigurarComboBox()
        {
            ComboBoxOptionsUI.Configurar(ComboBox1);
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
