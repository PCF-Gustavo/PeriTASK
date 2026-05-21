using System.IO;

namespace UserInterface
{
    public static class caminhos
    {
        public static string EncontrarRaizSolucao(string inicio)
        {
            var dir = new DirectoryInfo(inicio);

            while (dir != null)
            {
                if (File.Exists(Path.Combine(dir.FullName, "PeriTASK.sln")))
                    return dir.FullName;

                dir = dir.Parent;
            }

            throw new DirectoryNotFoundException(
                "Não foi possível encontrar a raiz da solução PeriTASK.sln"
            );
        }
    }
}
