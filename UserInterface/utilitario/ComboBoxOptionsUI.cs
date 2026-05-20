using System.Windows.Controls;

namespace UserInterface
{
    public static class ComboBoxOptionsUI
    {
        public static ComandosConfig Configurar(ComboBox comboBox)
        {
            ComandosConfig config = ComboBoxOptions.Carregar();

            comboBox.ItemsSource = config.comandos;
            comboBox.DisplayMemberPath = "label";

            return config;
        }
    }
}