using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace EasyClaudeCodeLauncher
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            var repoRoot = FindRepoRoot();
            if (string.IsNullOrWhiteSpace(repoRoot))
            {
                MessageBox.Show(
                    "Unable to locate scripts/open-claude-code.ps1. Keep Claude Code.app.exe inside the easy-claudecode.app-win folder.",
                    "Claude Code.app",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }

            var scriptPath = Path.Combine(repoRoot, "scripts", "open-claude-code.ps1");
            var forwardedArgs = args != null && args.Length > 0
                ? " " + string.Join(" ", args.Select(QuoteArg))
                : string.Empty;

            var processInfo = new ProcessStartInfo();
            processInfo.FileName = "powershell.exe";
            processInfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -File " + QuoteArg(scriptPath) + forwardedArgs;
            processInfo.WorkingDirectory = repoRoot;
            processInfo.UseShellExecute = false;
            processInfo.CreateNoWindow = true;
            processInfo.WindowStyle = ProcessWindowStyle.Hidden;

            try
            {
                var process = Process.Start(processInfo);
                if (process == null)
                {
                    throw new InvalidOperationException("launcher process returned null");
                }
                return 0;
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Failed to start Claude Code.app.\n\n" + ex.Message,
                    "Claude Code.app",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }
        }

        private static string FindRepoRoot()
        {
            var current = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
            while (current != null)
            {
                var scriptPath = Path.Combine(current.FullName, "scripts", "open-claude-code.ps1");
                if (File.Exists(scriptPath))
                {
                    return current.FullName;
                }
                current = current.Parent;
            }
            return null;
        }

        private static string QuoteArg(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return "\"\"";
            }

            var builder = new StringBuilder("\"");
            foreach (var ch in value)
            {
                if (ch == '"' || ch == '\\')
                {
                    builder.Append('\\');
                }
                builder.Append(ch);
            }
            builder.Append('"');
            return builder.ToString();
        }
    }
}
