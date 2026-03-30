using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
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

            try
            {
                var consoleUrl = StartServices(repoRoot);
                if (string.IsNullOrWhiteSpace(consoleUrl))
                {
                    throw new InvalidOperationException("launcher did not receive a console URL");
                }

                if (!WaitForHealthy(consoleUrl + "/status", TimeSpan.FromSeconds(25)))
                {
                    throw new InvalidOperationException("local console did not become healthy in time");
                }

                var shellPath = FindAppShell();
                if (string.IsNullOrWhiteSpace(shellPath))
                {
                    throw new FileNotFoundException("Neither Microsoft Edge nor Google Chrome app mode is available.");
                }

                var profileDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "easy-claudecode.app-win",
                    "app-shell-profile"
                );
                Directory.CreateDirectory(profileDir);

                var appArgs = string.Join(" ", new[]
                {
                    "--app=" + QuoteArg(consoleUrl),
                    "--new-window",
                    "--window-size=1440,980",
                    "--user-data-dir=" + QuoteArg(profileDir),
                });

                var process = Process.Start(new ProcessStartInfo
                {
                    FileName = shellPath,
                    Arguments = appArgs,
                    WorkingDirectory = repoRoot,
                    UseShellExecute = false,
                });
                if (process == null)
                {
                    throw new InvalidOperationException("app shell process returned null");
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

        private static string StartServices(string repoRoot)
        {
            var scriptPath = Path.Combine(repoRoot, "scripts", "open-claude-code.ps1");
            var processInfo = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File " + QuoteArg(scriptPath) + " -NoBrowser",
                WorkingDirectory = repoRoot,
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            processInfo.EnvironmentVariables["EASY_CLAUDECODE_AUTO_INSTALL_SHORTCUT"] = "0";
            processInfo.EnvironmentVariables["EASY_CLAUDECODE_AUTO_INSTALL_CC"] = "0";

            using (var process = Process.Start(processInfo))
            {
                if (process == null)
                {
                    throw new InvalidOperationException("launcher bootstrap process returned null");
                }

                var stdout = process.StandardOutput.ReadToEnd();
                var stderr = process.StandardError.ReadToEnd();
                if (!process.WaitForExit(45000))
                {
                    try
                    {
                        process.Kill();
                    }
                    catch
                    {
                    }
                    throw new TimeoutException("service bootstrap timed out");
                }

                if (process.ExitCode != 0)
                {
                    throw new InvalidOperationException(
                        "service bootstrap failed" +
                        (string.IsNullOrWhiteSpace(stderr) ? string.Empty : "\n\n" + stderr.Trim()) +
                        (string.IsNullOrWhiteSpace(stdout) ? string.Empty : "\n\n" + stdout.Trim())
                    );
                }

                var outputLines = stdout
                    .Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
                    .Select(line => line.Trim())
                    .Where(line => line.StartsWith("http://", StringComparison.OrdinalIgnoreCase) || line.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
                    .ToArray();
                return outputLines.LastOrDefault() ?? "http://127.0.0.1:18882/claude-console";
            }
        }

        private static bool WaitForHealthy(string url, TimeSpan timeout)
        {
            var deadline = DateTime.UtcNow.Add(timeout);
            while (DateTime.UtcNow < deadline)
            {
                try
                {
                    var request = WebRequest.Create(url);
                    request.Timeout = 2000;
                    using (var response = (HttpWebResponse)request.GetResponse())
                    {
                        if ((int)response.StatusCode >= 200 && (int)response.StatusCode < 300)
                        {
                            return true;
                        }
                    }
                }
                catch
                {
                }

                System.Threading.Thread.Sleep(1000);
            }

            return false;
        }

        private static string FindAppShell()
        {
            var candidates = new[]
            {
                @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                @"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                @"C:\Program Files\Google\Chrome\Application\chrome.exe",
            };

            return candidates.FirstOrDefault(File.Exists);
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
