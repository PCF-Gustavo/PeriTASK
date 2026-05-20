using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace UserInterface
{
    public static class ComboBoxOptions
    {
        public static ComboBoxOptionsConfig Carregar()
        {
            string path = Path.Combine(
                System.AppDomain.CurrentDomain.BaseDirectory,
                "Compartilhado",
                "combo_box_options.json"
            );

            var json = File.ReadAllText(path);

            return JsonSerializer.Deserialize<ComboBoxOptionsConfig>(json);
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
        public string @default { get; set; }
        public string regex { get; set; }
        public int? displayWidth { get; set; }
        public int? stringsize { get; set; }
        public string screenTip { get; set; }
        public PositionConfig position { get; set; }


    }

    public class PositionConfig
    {
        public int? row { get; set; }
        public int? column { get; set; }
    }


    public class ComboBoxOptionsConfig
    {
        public List<ComboBoxOption> combo_box_options { get; set; }
    }
}