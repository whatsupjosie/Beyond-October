using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class PubCastLauncher
{
    [STAThread]
    private static int Main()
    {
        try
        {
            var exeDir = AppDomain.CurrentDomain.BaseDirectory;
            var script = Path.Combine(exeDir, "launcher", "start_pubcast.ps1");
            if (!File.Exists(script))
            {
                MessageBox.Show("Could not find launcher\\start_pubcast.ps1 next to the launcher executable.", "PubCast Launcher");
                return 1;
            }

            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-ExecutionPolicy Bypass -NoProfile -File \"" + script + "\"",
                UseShellExecute = true,
                WindowStyle = ProcessWindowStyle.Hidden,
            };

            Process.Start(psi);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "PubCast Launcher");
            return 1;
        }
    }
}
