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
            }
            else if (linha.StartsWith("PAUSE:"))
            {
                progressViewModel.Status_Python = linha.Replace("PAUSE:", "");
                progressViewModel.AguardandoContinuar = true;
            }
            else
            {
                progressViewModel.Status_Python = linha;
            }
        }

        public static void ProcessarErro(
            string linha,
            ProgressViewModel progressViewModel
        )
        {
            progressViewModel.Status_Python = linha;
        }
    }
}