using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json;

namespace UserInterface
{
    public static class payload_ui
    {
        public static string CriarArgumentoUiBase64(
            string comboBoxOptionsId,
            Dictionary<string, object> controls
        )
        {
            var payload = new
            {
                combo_box_options_id = comboBoxOptionsId,
                controls = controls
            };

            string argumentoUi = JsonSerializer.Serialize(payload);

            return Convert.ToBase64String(
                Encoding.UTF8.GetBytes(argumentoUi)
            );
        }

        public static string CriarArgumentoUiBase64Benchmark(string rota)
        {
            var payload = new
            {
                combo_box_options_id = rota,
                controls = new { }
            };

            string argumentoUiJson = JsonSerializer.Serialize(payload);

            return Convert.ToBase64String(
                Encoding.UTF8.GetBytes(argumentoUiJson)
            );
        }
    }
}
