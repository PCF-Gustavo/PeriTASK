namespace UserInterface
{
    public static class saida_python
    {
        public static void ProcessarLinha(
            string linha,
            ProgressViewModel progressViewModel
        )
        {
            // Atualiza barra de progresso
            if (linha.StartsWith("PROGRESS:"))
            {
                if (int.TryParse(linha.Replace("PROGRESS:", ""), out int _progresso))
                    progressViewModel.Progress = _progresso;
            }
            // Atualiza Status
            else if (linha.StartsWith("STATUS:"))
            {
                progressViewModel.Status_Python = linha.Replace("STATUS:", "");

                // Limpa screentip antigo ao iniciar novo status
                progressViewModel.Status_Python_ScreenTip = null;
            }
            // Atualiza ScreenTip do Status
            else if (linha.StartsWith("STATUS_SCREENTIP:"))
            {
                progressViewModel.Status_Python_ScreenTip = linha
                    .Replace("STATUS_SCREENTIP:", "")
                    .Replace("\\n", Environment.NewLine);
            }
            else if (linha.StartsWith("PAUSE:"))
            {
                progressViewModel.Status_Python = linha.Replace("PAUSE:", "");
                progressViewModel.Status_Python_ScreenTip = null;
                progressViewModel.AguardandoContinuar = true;
            }
            else
            {
                progressViewModel.Status_Python = linha;
                progressViewModel.Status_Python_ScreenTip = null;
            }
        }

        public static void ProcessarErro(
            string linha,
            ProgressViewModel progressViewModel
        )
        {
            progressViewModel.Status_Python = linha;
            progressViewModel.Status_Python_ScreenTip = null;
        }
    }
}