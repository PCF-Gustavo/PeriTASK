using System.Collections.Generic;
using System.Diagnostics;
using System.Windows;

namespace UserInterface
{
    public static class janela_principal
    {
        public static bool ValidarItensSelecionados(List<string> itensSelecionados)
        {
            // Executa apenas se não estiver no debug
            if (!Debugger.IsAttached)
            {
                if (itensSelecionados == null || itensSelecionados.Count == 0)
                {
                    EncerrarPorNenhumArquivoRecebido();
                    return false;
                }
            }

            return true;
        }

        private static void EncerrarPorNenhumArquivoRecebido()
        {
            MessageBox.Show("Nenhum arquivo recebido.", "PeriTASK",
                MessageBoxButton.OK, MessageBoxImage.Error);

            Application.Current.Shutdown();
        }
    }
}