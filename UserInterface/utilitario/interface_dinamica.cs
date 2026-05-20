using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;

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
                if (control.type != "checkbox")
                    continue;

                var checkbox = new CheckBox
                {
                    Name = control.id,
                    Content = control.text,
                    IsEnabled = control.enabled ?? true,
                    IsChecked = control.@checked ?? false,
                    ToolTip = control.screenTip,
                    Margin = new Thickness(0, 0, 15, 5)
                };

                int row = control.position?.row ?? 0;
                int column = control.position?.column ?? 0;

                Grid.SetRow(checkbox, row);
                Grid.SetColumn(checkbox, column);

                renderedControls[control.id] = checkbox;
                dynamicPanel.Children.Add(checkbox);
            }
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
                }
            }

            return result;
        }
    }
}
