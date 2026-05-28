using System.IO;
using System.Text.Json;

namespace UserInterface
{
    public static class ComboBoxOptions
    {
        public static ComandosConfig Carregar()
        {
            string path = Path.Combine(
                System.AppDomain.CurrentDomain.BaseDirectory,
                "Compartilhado",
                "catalogo_de_comandos.json"
            );

            var json = File.ReadAllText(path);

            return JsonSerializer.Deserialize<ComandosConfig>(json);
        }
    }

    public class ComboBoxOption
    {
        public string? id { get; set; }
        public string? label { get; set; }
        public UiConfig ui { get; set; } = new();
    }

    public class UiConfig
    {
        public List<ControlConfig> controls { get; set; } = new();
    }

    public class ControlConfig
    {
        public string? type { get; set; }
        public string? id { get; set; }
        public string? text { get; set; }
        public bool? enabled { get; set; }
        public bool? @checked { get; set; }
        public string? @default { get; set; }
        public List<string> items { get; set; } = new();
        public string? regex { get; set; }
        public int? stringsize { get; set; }
        public string? screenTip { get; set; }
        public PositionConfig position { get; set; } = new();


    }

    public class PositionConfig
    {
        public int? row { get; set; }
        public int? column { get; set; }
    }


    public class ComandosConfig
    {
        public List<ComboBoxOption> comandos { get; set; } = new();
    }
}