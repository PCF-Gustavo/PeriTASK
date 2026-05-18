using System.ComponentModel;
using System.Windows;

namespace UserInterface
{
    public partial class ProgressWindow : Window
    {
        public bool FechamentoProgramatico { get; set; } = false;
        public ProgressWindow()
        {
            InitializeComponent();
        }


        protected override void OnClosing(CancelEventArgs e)
        {
            base.OnClosing(e);

            if (FechamentoProgramatico)
                return;

            if (DataContext is ProgressViewModel vm)
            {
                vm.MainButtonCommand.Execute(null);
            }
        }

    }
}
