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

        public ProgressViewModel(Action cancelar)
        {
            CancelCommand = new RelayCommand(cancelar);
            _ultimoUpdate = DateTime.Now;
            _temposIteracao = new Queue<double>();
            Status_Python = "Aguardando início...";
            Progress = 0;
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

        public ICommand CancelCommand { get; set; }

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
