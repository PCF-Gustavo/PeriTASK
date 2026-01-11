using System.ComponentModel;
using System.Windows;

namespace UserInterface
{
    public partial class ProgressWindow : Window
    {
        public ProgressWindow()
        {
            InitializeComponent();
        }

        protected override void OnClosing(CancelEventArgs e)
        {
            base.OnClosing(e);

            if (DataContext is ProgressViewModel vm)
            {
                vm.CancelCommand.Execute(null);
            }
        }
    }
}
