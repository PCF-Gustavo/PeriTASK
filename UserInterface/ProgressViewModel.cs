using System;
using System.Collections.Generic;
using System.ComponentModel.Design;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Input;

namespace UserInterface
{
    public class ProgressViewModel
    {
        public double Progress;
        public ICommand CancelCommand = null;
    }
}
