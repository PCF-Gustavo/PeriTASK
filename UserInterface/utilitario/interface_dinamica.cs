using System.Windows;
using System.Windows.Controls;
using System.Text.RegularExpressions;
using System.Globalization;
using System.Windows.Media;

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
                if (control.type == "dropdown")
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

                    var comboBox = new ComboBox
                    {
                        Name = control.id,
                        IsEnabled = control.enabled ?? true,
                        MinWidth = 0,
                        Padding = new Thickness(2, 0, 2, 0),
                        VerticalAlignment = VerticalAlignment.Center,
                        ToolTip = string.IsNullOrWhiteSpace(control.screenTip)
                            ? null
                            : control.screenTip
                    };

                    comboBox.Width = CalcularLarguraDropdown(control, comboBox);

                    if (control.items != null)
                    {
                        foreach (var item in control.items)
                        {
                            comboBox.Items.Add(item);
                        }
                    }

                    if (!string.IsNullOrWhiteSpace(control.@default))
                    {
                        comboBox.SelectedItem = control.@default;
                    }

                    if (comboBox.SelectedItem == null && comboBox.Items.Count > 0)
                    {
                        comboBox.SelectedIndex = 0;
                    }

                    container.Children.Add(label);
                    container.Children.Add(comboBox);

                    PosicionarNoGrid(container, control);

                    renderedControls[control.id] = comboBox;
                    dynamicPanel.Children.Add(container);

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
                        MinWidth = 0,
                        Padding = new Thickness(2, 0, 2, 0),
                        VerticalAlignment = VerticalAlignment.Center,
                        ToolTip = string.IsNullOrWhiteSpace(control.screenTip)
                            ? null
                            : control.screenTip
                    };

                    textBox.Width = CalcularLarguraEditBoxEmCaracteres(
                        control.stringsize,
                        textBox
                    );

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
        private static double CalcularLarguraDropdown(
    ControlConfig control,
    ComboBox comboBox
)
        {
            IEnumerable<string> textos = control.items ?? Enumerable.Empty<string>();

            if (!string.IsNullOrWhiteSpace(control.@default))
            {
                textos = textos.Append(control.@default);
            }

            string maiorTexto = textos
                .Where(texto => texto != null)
                .OrderByDescending(texto => MedirTextoEmPixels(texto, comboBox))
                .FirstOrDefault() ?? "";

            if (string.IsNullOrEmpty(maiorTexto))
            {
                maiorTexto = "0";
            }

            double larguraTexto = MedirTextoEmPixels(maiorTexto, comboBox);

            // Espaço para padding, borda e botão/seta do ComboBox.
            const double extraComboBox = 24.0;

            return Math.Ceiling(larguraTexto + extraComboBox);
        }

        private static double CalcularLarguraEditBoxEmCaracteres(
            int? width,
            TextBox textBox
        )
        {
            string textoMedicao = CriarTextoMedicao(width);

            double larguraTexto = MedirTextoEmPixels(textoMedicao, textBox);

            // Espaço interno mínimo para borda e padding do TextBox.
            const double extraTextBox = 8.0;

            return Math.Ceiling(larguraTexto + extraTextBox);
        }

        private static double MedirTextoEmPixels(
    string texto,
    Control controleReferencia
)
        {
            var typeface = new Typeface(
                controleReferencia.FontFamily,
                controleReferencia.FontStyle,
                controleReferencia.FontWeight,
                controleReferencia.FontStretch
            );

            var formattedText = new FormattedText(
                texto,
                CultureInfo.CurrentUICulture,
                FlowDirection.LeftToRight,
                typeface,
                controleReferencia.FontSize,
                Brushes.Black,
                VisualTreeHelper.GetDpi(controleReferencia).PixelsPerDip
            );

            return formattedText.WidthIncludingTrailingWhitespace;
        }

        private static string CriarTextoMedicao(int? width)
        {
            const int larguraPadraoEmCaracteres = 10;

            int quantidadeCaracteres = width ?? larguraPadraoEmCaracteres;

            if (quantidadeCaracteres < 1)
                quantidadeCaracteres = 1;

            return new string('0', quantidadeCaracteres);
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

                    case ComboBox comboBox:
                        result[kvp.Key] = comboBox.SelectedItem?.ToString() ?? "";
                        break;
                }
            }

            return result;
        }
    }
}
