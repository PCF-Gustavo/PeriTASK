using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;

namespace UserInterface
{
    public class ProgressViewModel : INotifyPropertyChanged
    {
        private double _progress;

        public double Progress
        {
            get => _progress;
            set
            {
                if (_progress != value)
                {
                    _progress = value;
                    OnPropertyChanged();
                }
            }
        }

        public ICommand CancelCommand { get; set; }

        public event PropertyChangedEventHandler PropertyChanged;

        protected void OnPropertyChanged([CallerMemberName] string name = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
        }
    }
}
