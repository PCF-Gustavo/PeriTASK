using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;

namespace UserInterface
{
    public class ProgressViewModel : INotifyPropertyChanged
    {
        private double _progress;
        private string _titulo;
        private string _tempoRestante;

        private DateTime _ultimoUpdate;
        private Queue<double> _temposIteracao;
        private const int TAMANHO_MEDIA = 10;

        public ProgressViewModel(Action cancelar)
        {
            CancelCommand = new RelayCommand(cancelar);
            _ultimoUpdate = DateTime.Now;
            _temposIteracao = new Queue<double>();
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

                    // Adiciona o delta e mantém o tamanho máximo da fila
                    _temposIteracao.Enqueue(delta);
                    if (_temposIteracao.Count > TAMANHO_MEDIA)
                        _temposIteracao.Dequeue();

                    _progress = value;
                    AtualizarTempoRestante();
                    OnPropertyChanged();
                }
            }
        }

        public string Titulo
        {
            get => _titulo;
            set
            {
                if (_titulo != value)
                {
                    _titulo = value;
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

        public ICommand CancelCommand { get; set; }

        private void AtualizarTempoRestante()
        {
            double frac = _progress / 100.0;

            // Calcula a média móvel das iterações
            double mediaIteracao = 0;
            foreach (var t in _temposIteracao)
                mediaIteracao += t;
            if (_temposIteracao.Count > 0)
                mediaIteracao /= _temposIteracao.Count;

            if (frac > 0 && mediaIteracao > 0)
            {
                // Estima o número total de "passos" e calcula o restante
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
        protected void OnPropertyChanged([CallerMemberName] string name = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
        }
    }

    public class RelayCommand : ICommand
    {
        private readonly Action _execute;

        public RelayCommand(Action execute)
        {
            _execute = execute;
        }

        public bool CanExecute(object parameter) => true;

        public void Execute(object parameter) => _execute();

        public event EventHandler CanExecuteChanged;
    }
}
