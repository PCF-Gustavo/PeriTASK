using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Windows.Input;

namespace UserInterface
{
    public class ProgressViewModel : INotifyPropertyChanged
    {
        private double _progress;
        private string _tempoRestante;
        private string _status_Python;

        private DateTime _ultimoUpdate;
        private Queue<double> _temposIteracao;
        private const int TAMANHO_MEDIA = 10;

        private readonly Action _cancelar;
        private readonly Action _continuar;

        private bool _aguardandoContinuar;


        public ProgressViewModel(Action cancelar, Action continuar)
        {
            _cancelar = cancelar;
            _continuar = continuar;

            MainButtonCommand = new RelayCommand(ExecutarBotaoPrincipal);

            _ultimoUpdate = DateTime.Now;
            _temposIteracao = new Queue<double>();

            Status_Python = "Fazendo configurações iniciais...";
            Progress = 0;
            AguardandoContinuar = false;
        }


        public double Progress
        {
            get => _progress;
            set
            {
                if (_progress != value)
                {
                    var agora = DateTime.Now;
                    double delta = (agora - _ultimoUpdate).TotalSeconds;
                    _ultimoUpdate = agora;

                    _temposIteracao.Enqueue(delta);
                    if (_temposIteracao.Count > TAMANHO_MEDIA)
                        _temposIteracao.Dequeue();

                    _progress = value;
                    AtualizarTempoRestante();
                    OnPropertyChanged();
                }
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
                _status_Python = value;
                OnPropertyChanged();
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
            double frac = _progress / 100.0;
            double mediaIteracao = _temposIteracao.Any() ? _temposIteracao.Average() : 0;

            if (frac > 0 && mediaIteracao > 0)
            {
                double totalIteracoesEstimadas = 100.0 / frac;
                double restantes = totalIteracoesEstimadas - 1;
                double segundosRestantes = mediaIteracao * restantes;

                TempoRestante = TimeSpan.FromSeconds(segundosRestantes).ToString(@"mm\:ss");
            }
            else
            {
                TempoRestante = "--:--";
            }
        }

        public event PropertyChangedEventHandler PropertyChanged;
        private void OnPropertyChanged([CallerMemberName] string name = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
        }
    }

    public class RelayCommand : ICommand
    {
        private readonly Action _execute;

        public RelayCommand(Action execute) => _execute = execute;

        public bool CanExecute(object parameter) => true;

        public void Execute(object parameter) => _execute();

        public event EventHandler CanExecuteChanged;
    }
}
