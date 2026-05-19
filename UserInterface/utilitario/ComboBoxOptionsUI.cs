using System.Windows.Controls;

namespace UserInterface
{
    public static class ComboBoxOptionsUI
    {
        public static ComboBoxOptionsConfig Configurar(ComboBox comboBox)
        {
            ComboBoxOptionsConfig config = ComboBoxOptions.Carregar();

            comboBox.ItemsSource = config.combo_box_options;
            comboBox.DisplayMemberPath = "label";

            return config;
        }
    }
}