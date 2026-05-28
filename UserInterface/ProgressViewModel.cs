using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;

namespace UserInterface
{
    public class ProgressViewModel : INotifyPropertyChanged
    {
        private double _progress;
        private string _tempoRestante;
        private string _status_Python;

        private DateTime _inicioProcessamento;
        private DateTime _ultimoUpdate;
        private double _ultimoProgress;

        private Queue<AmostraProgresso> _amostrasProgresso;

        private const int TAMANHO_MEDIA = 10;
        private const double PROGRESSO_MINIMO_PARA_ESTIMAR = 1.0;
        private const double SEGUNDOS_MINIMOS_PARA_ESTIMAR = 0.3;

        private readonly Action _cancelar;
        private readonly Action _continuar;

        private bool _aguardandoContinuar;

        public ProgressViewModel(Action cancelar, Action continuar)
        {
            _cancelar = cancelar;
            _continuar = continuar;

            MainButtonCommand = new RelayCommand(ExecutarBotaoPrincipal);

            _inicioProcessamento = DateTime.Now;
            _ultimoUpdate = _inicioProcessamento;
            _ultimoProgress = 0;

            _amostrasProgresso = new Queue<AmostraProgresso>();

            Status_Python = "Fazendo configurações iniciais...";
            _progress = 0;
            TempoRestante = "--:--";
            AguardandoContinuar = false;
        }

        public double Progress
        {
            get => _progress;
            set
            {
                double novoProgress = NormalizarProgresso(value);

                if (Math.Abs(_progress - novoProgress) < 0.0001)
                    return;

                var agora = DateTime.Now;

                double deltaTempo = (agora - _ultimoUpdate).TotalSeconds;
                double deltaProgresso = novoProgress - _ultimoProgress;

                /*
                 * Só registra amostra se houve avanço real.
                 * Isso evita distorcer o ETA com:
                 * - updates repetidos;
                 * - progresso regressivo;
                 * - progresso 0;
                 * - mudanças instantâneas demais.
                 */
                if (deltaProgresso > 0 && deltaTempo >= SEGUNDOS_MINIMOS_PARA_ESTIMAR)
                {
                    _amostrasProgresso.Enqueue(
                        new AmostraProgresso(deltaProgresso, deltaTempo)
                    );

                    if (_amostrasProgresso.Count > TAMANHO_MEDIA)
                        _amostrasProgresso.Dequeue();
                }

                _progress = novoProgress;
                _ultimoProgress = novoProgress;
                _ultimoUpdate = agora;

                AtualizarTempoRestante();
                OnPropertyChanged();
            }
        }

        public string TempoRestante
        {
            get => _tempoRestante;
            private set
            {
                if (_tempoRestante != value)
                {
                    _tempoRestante = value;
                    OnPropertyChanged();
                }
            }
        }

        public string Status_Python
        {
            get => _status_Python;
            set
            {
                if (_status_Python != value)
                {
                    _status_Python = value;
                    OnPropertyChanged();
                }
            }
        }

        private string _status_Python_ScreenTip;

        public string Status_Python_ScreenTip
        {
            get => _status_Python_ScreenTip;
            set
            {
                if (_status_Python_ScreenTip != value)
                {
                    _status_Python_ScreenTip = value;
                    OnPropertyChanged();
                }
            }
        }


        public bool AguardandoContinuar
        {
            get => _aguardandoContinuar;
            set
            {
                if (_aguardandoContinuar != value)
                {
                    _aguardandoContinuar = value;
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(MainButtonText));
                }
            }
        }

        public string MainButtonText
        {
            get => AguardandoContinuar ? "Continuar" : "Cancelar";
        }

        public ICommand MainButtonCommand { get; }

        private void ExecutarBotaoPrincipal()
        {
            if (AguardandoContinuar)
                _continuar();
            else
                _cancelar();
        }

        private void AtualizarTempoRestante()
        {
            if (_progress >= 100)
            {
                TempoRestante = "00:00";
                return;
            }

            if (_progress < PROGRESSO_MINIMO_PARA_ESTIMAR)
            {
                TempoRestante = "--:--";
                return;
            }

            double segundosRestantes = CalcularSegundosRestantes();

            if (double.IsNaN(segundosRestantes) ||
                double.IsInfinity(segundosRestantes) ||
                segundosRestantes < 0)
            {
                TempoRestante = "--:--";
                return;
            }

            TempoRestante = FormatarTempoRestante(segundosRestantes);
        }

        private double CalcularSegundosRestantes()
        {
            double progressoRestante = 100.0 - _progress;

            /*
             * 1) Preferência: velocidade recente, usando janela móvel.
             * velocidade = pontos percentuais por segundo.
             */
            if (_amostrasProgresso.Any())
            {
                double somaDeltaProgresso = _amostrasProgresso.Sum(a => a.DeltaProgresso);
                double somaDeltaTempo = _amostrasProgresso.Sum(a => a.DeltaTempoSegundos);

                if (somaDeltaProgresso > 0 && somaDeltaTempo > 0)
                {
                    double velocidadeRecente = somaDeltaProgresso / somaDeltaTempo;

                    if (velocidadeRecente > 0)
                        return progressoRestante / velocidadeRecente;
                }
            }

            /*
             * 2) Fallback: estimativa global desde o início.
             * tempo_restante = tempo_decorrido * (100 - progresso) / progresso
             */
            double segundosDecorridos = (DateTime.Now - _inicioProcessamento).TotalSeconds;

            if (_progress > 0 && segundosDecorridos > 0)
            {
                return segundosDecorridos * progressoRestante / _progress;
            }

            return double.NaN;
        }

        private static double NormalizarProgresso(double valor)
        {
            if (double.IsNaN(valor) || double.IsInfinity(valor))
                return 0;

            if (valor < 0)
                return 0;

            if (valor > 100)
                return 100;

            return valor;
        }

        private static string FormatarTempoRestante(double segundos)
        {
            var tempo = TimeSpan.FromSeconds(Math.Ceiling(segundos));

            if (tempo.TotalHours >= 1)
                return tempo.ToString(@"hh\:mm\:ss");

            return tempo.ToString(@"mm\:ss");
        }

        public event PropertyChangedEventHandler? PropertyChanged;

        private void OnPropertyChanged([CallerMemberName] string name = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
        }

        private readonly struct AmostraProgresso
        {
            public double DeltaProgresso { get; }
            public double DeltaTempoSegundos { get; }

            public AmostraProgresso(double deltaProgresso, double deltaTempoSegundos)
            {
                DeltaProgresso = deltaProgresso;
                DeltaTempoSegundos = deltaTempoSegundos;
            }
        }
    }

    public class RelayCommand : ICommand
    {
        private readonly Action _execute;

        public RelayCommand(Action execute) => _execute = execute;

        public bool CanExecute(object? parameter) => true;

        public void Execute(object? parameter) => _execute();

        public event EventHandler? CanExecuteChanged;
    }
}