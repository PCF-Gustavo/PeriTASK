using System.Collections.Generic;
using System.Windows.Controls;

namespace UserInterface
{
    public static class interface_dinamica
    {
        public static void Renderizar(
            ComboBoxOption option,
            StackPanel dynamicPanel,
            Dictionary<string, Control> renderedControls
        )
        {
            renderedControls.Clear();
            dynamicPanel.Children.Clear();

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
