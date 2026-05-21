using System.Windows;
using System.Windows.Controls;
using System.Text.RegularExpressions;

namespace UserInterface
{
    public static class interface_dinamica
    {
        public static void Renderizar(
    ComboBoxOption option,
    Grid dynamicPanel,
    Dictionary<string, Control> renderedControls
)
        {
            renderedControls.Clear();

            dynamicPanel.Children.Clear();
            dynamicPanel.RowDefinitions.Clear();
            dynamicPanel.ColumnDefinitions.Clear();

            var controls = option?.ui?.controls;

            if (controls == null || controls.Count == 0)
                return;

            int maxRow = controls
                .Where(c => c.position?.row != null)
                .Select(c => c.position.row.Value)
                .DefaultIfEmpty(0)
                .Max();

            int maxColumn = controls
                .Where(c => c.position?.column != null)
                .Select(c => c.position.column.Value)
                .DefaultIfEmpty(0)
                .Max();

            for (int i = 0; i <= maxRow; i++)
            {
                dynamicPanel.RowDefinitions.Add(
                    new RowDefinition
                    {
                        Height = GridLength.Auto
                    }
                );
            }

            for (int i = 0; i <= maxColumn; i++)
            {
                dynamicPanel.ColumnDefinitions.Add(
                    new ColumnDefinition
                    {
                        Width = GridLength.Auto
                    }
                );
            }

            foreach (var control in controls)
            {
                if (control.type == "checkbox")
                {
                    var checkbox = new CheckBox
                    {
                        Name = control.id,
                        Content = control.text,
                        IsEnabled = control.enabled ?? true,
                        IsChecked = control.@checked ?? false,
                        ToolTip = string.IsNullOrWhiteSpace(control.screenTip)
                            ? null
                            : control.screenTip,
                        Margin = new Thickness(0, 0, 15, 5)
                    };

                    PosicionarNoGrid(checkbox, control);

                    renderedControls[control.id] = checkbox;
                    dynamicPanel.Children.Add(checkbox);

                    continue;
                }

                if (control.type == "editbox")
                {
                    var container = new StackPanel
                    {
                        Orientation = Orientation.Horizontal,
                        Margin = new Thickness(0, 0, 15, 5),
                        ToolTip = string.IsNullOrWhiteSpace(control.screenTip)
                            ? null
                            : control.screenTip
                    };

                    var label = new TextBlock
                    {
                        Text = control.text,
                        VerticalAlignment = VerticalAlignment.Center,
                        Margin = new Thickness(0, 0, 5, 0)
                    };

                    string valorInicial = control.@default ?? "";

                    var textBox = new TextBox
                    {
                        Name = control.id,
                        Text = valorInicial,
                        Tag = TextoEhValido(valorInicial, control.regex)
                            ? valorInicial
                            : "",
                        IsEnabled = control.enabled ?? true,
                        Width = CalcularLarguraEditBoxEmCaracteres(control.displayWidth),
                        VerticalAlignment = VerticalAlignment.Center,
                        ToolTip = string.IsNullOrWhiteSpace(control.screenTip)
                            ? null
                            : control.screenTip
                    };

                    if (control.stringsize.HasValue && control.stringsize.Value > 0)
                    {
                        textBox.MaxLength = control.stringsize.Value;
                    }

                    if (!string.IsNullOrWhiteSpace(control.regex))
                    {
                        textBox.LostFocus += (s, e) =>
                        {
                            AtualizarUltimoValorValidoOuRestaurar(textBox, control.regex);
                        };
                    }

                    container.Children.Add(label);
                    container.Children.Add(textBox);

                    PosicionarNoGrid(container, control);

                    renderedControls[control.id] = textBox;
                    dynamicPanel.Children.Add(container);

                    continue;
                }
            }
        }
        private static double CalcularLarguraEditBoxEmCaracteres(int? displayWidth)
        {
            const int larguraPadraoEmCaracteres = 10;
            const double larguraMediaCaractere = 8.0;
            const double paddingHorizontalTextBox = 18.0;

            int quantidadeCaracteres = displayWidth ?? larguraPadraoEmCaracteres;

            if (quantidadeCaracteres < 1)
                quantidadeCaracteres = 1;

            return (quantidadeCaracteres * larguraMediaCaractere) + paddingHorizontalTextBox;
        }
        private static void PosicionarNoGrid(FrameworkElement element, ControlConfig control)
        {
            int row = control.position?.row ?? 0;
            int column = control.position?.column ?? 0;

            Grid.SetRow(element, row);
            Grid.SetColumn(element, column);
        }


        private static bool TextoEhValido(string texto, string regex)
        {
            if (string.IsNullOrWhiteSpace(regex))
                return true;

            return Regex.IsMatch(texto ?? "", regex);
        }


        private static void AtualizarUltimoValorValidoOuRestaurar(TextBox textBox, string regex)
        {
            string valorAtual = textBox.Text ?? "";

            if (TextoEhValido(valorAtual, regex))
            {
                textBox.Tag = valorAtual;
                return;
            }

            string ultimoValorValido = textBox.Tag as string ?? "";
            textBox.Text = ultimoValorValido;
        }
        public static Dictionary<string, object> ColetarEstado(
            Dictionary<string, Control> renderedControls
        )
        {
            var result = new Dictionary<string, object>();

            foreach (var kvp in renderedControls)
            {
                switch (kvp.Value)
                {
                    case CheckBox cb:
                        result[kvp.Key] = cb.IsChecked ?? false;
                        break;

                    case TextBox tb:
                        result[kvp.Key] = tb.Text;
                        break;
                }
            }

            return result;
        }
    }
}
