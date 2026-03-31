using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

namespace EasyClaudeCodeInstaller
{
    internal static class Program
    {
        [STAThread]
        private static int Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            using (var form = new InstallerForm())
            {
                return form.ShowDialog() == DialogResult.OK ? 0 : 1;
            }
        }
    }

    internal sealed class InstallerForm : Form
    {
        private readonly TextBox _installPathBox;
        private readonly CheckBox _desktopShortcutCheckBox;
        private readonly CheckBox _ccLauncherCheckBox;
        private readonly CheckBox _everythingClaudeCodeCheckBox;
        private readonly CheckBox _launchAfterInstallCheckBox;
        private readonly Button _browseButton;
        private readonly Button _installButton;
        private readonly Button _cancelButton;
        private readonly Label _statusLabel;

        internal InstallerForm()
        {
            Text = "Install Claude Code.app";
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ClientSize = new Size(640, 360);

            var titleLabel = new Label
            {
                Text = "Install easy-claudecode.app-win",
                Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 16F, FontStyle.Bold),
                AutoSize = true,
                Location = new Point(24, 20),
            };

            var noteLabel = new Label
            {
                Text = "This installer extracts the bundled Windows app, creates the optional launcher entries, and can install Everything Claude Code after setup.",
                AutoSize = false,
                Size = new Size(592, 42),
                Location = new Point(24, 56),
            };

            var pathLabel = new Label
            {
                Text = "Install location",
                AutoSize = true,
                Location = new Point(24, 112),
            };

            _installPathBox = new TextBox
            {
                Location = new Point(24, 136),
                Size = new Size(490, 26),
                Text = DefaultInstallDirectory(),
            };

            _browseButton = new Button
            {
                Text = "Browse",
                Location = new Point(524, 134),
                Size = new Size(92, 30),
            };
            _browseButton.Click += OnBrowseClick;

            _desktopShortcutCheckBox = new CheckBox
            {
                Text = "Create desktop shortcut",
                Checked = true,
                AutoSize = true,
                Location = new Point(28, 186),
            };

            _ccLauncherCheckBox = new CheckBox
            {
                Text = "Install global cc.cmd launcher",
                Checked = true,
                AutoSize = true,
                Location = new Point(28, 214),
            };

            _everythingClaudeCodeCheckBox = new CheckBox
            {
                Text = "Install Everything Claude Code (optional full profile)",
                Checked = false,
                AutoSize = true,
                Location = new Point(28, 242),
            };

            _launchAfterInstallCheckBox = new CheckBox
            {
                Text = "Launch Claude Code.app after install",
                Checked = true,
                AutoSize = true,
                Location = new Point(28, 270),
            };

            _statusLabel = new Label
            {
                AutoSize = false,
                Size = new Size(592, 36),
                Location = new Point(24, 298),
                ForeColor = Color.FromArgb(90, 90, 90),
            };

            _installButton = new Button
            {
                Text = "Install",
                Location = new Point(432, 326),
                Size = new Size(88, 28),
            };
            _installButton.Click += OnInstallClick;

            _cancelButton = new Button
            {
                Text = "Cancel",
                DialogResult = DialogResult.Cancel,
                Location = new Point(528, 326),
                Size = new Size(88, 28),
            };

            Controls.Add(titleLabel);
            Controls.Add(noteLabel);
            Controls.Add(pathLabel);
            Controls.Add(_installPathBox);
            Controls.Add(_browseButton);
            Controls.Add(_desktopShortcutCheckBox);
            Controls.Add(_ccLauncherCheckBox);
            Controls.Add(_everythingClaudeCodeCheckBox);
            Controls.Add(_launchAfterInstallCheckBox);
            Controls.Add(_statusLabel);
            Controls.Add(_installButton);
            Controls.Add(_cancelButton);

            AcceptButton = _installButton;
            CancelButton = _cancelButton;
        }

        private static string DefaultInstallDirectory()
        {
            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Programs",
                "easy-claudecode.app-win"
            );
        }

        private void OnBrowseClick(object sender, EventArgs e)
        {
            using (var dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Choose where to install Claude Code.app";
                dialog.SelectedPath = _installPathBox.Text.Trim();
                dialog.ShowNewFolderButton = true;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    _installPathBox.Text = dialog.SelectedPath;
                }
            }
        }

        private void OnInstallClick(object sender, EventArgs e)
        {
            try
            {
                ToggleBusy(true, "Installing Claude Code.app...");
                var result = InstallBundle(_installPathBox.Text.Trim());
                if (_launchAfterInstallCheckBox.Checked)
                {
                    LaunchInstalledApp(result.InstallDirectory);
                }

                var message = new StringBuilder();
                message.AppendLine("Claude Code.app is ready.");
                message.AppendLine();
                message.AppendLine("Install location:");
                message.AppendLine(result.InstallDirectory);

                if (result.Warnings.Count > 0)
                {
                    message.AppendLine();
                    message.AppendLine("Warnings:");
                    foreach (var warning in result.Warnings)
                    {
                        message.AppendLine("- " + warning);
                    }
                }

                MessageBox.Show(
                    this,
                    message.ToString(),
                    "Install Complete",
                    MessageBoxButtons.OK,
                    result.Warnings.Count > 0 ? MessageBoxIcon.Warning : MessageBoxIcon.Information
                );
                DialogResult = DialogResult.OK;
                Close();
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, true);
                MessageBox.Show(
                    this,
                    "Failed to install Claude Code.app.\n\n" + ex.Message,
                    "Install Failed",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
            finally
            {
                ToggleBusy(false, string.Empty);
            }
        }

        private InstallResult InstallBundle(string installDirectory)
        {
            if (string.IsNullOrWhiteSpace(installDirectory))
            {
                throw new InvalidOperationException("Choose an install location before continuing.");
            }

            var normalizedInstallDirectory = Path.GetFullPath(installDirectory);
            Directory.CreateDirectory(normalizedInstallDirectory);

            var tempRoot = Path.Combine(Path.GetTempPath(), "easy-claudecode-installer-" + Guid.NewGuid().ToString("N"));
            var tempZip = Path.Combine(tempRoot, "bundle.zip");
            var tempExtractDirectory = Path.Combine(tempRoot, "extract");
            Directory.CreateDirectory(tempRoot);

            try
            {
                ExtractEmbeddedBundle(tempZip);
                ZipFile.ExtractToDirectory(tempZip, tempExtractDirectory);
                CopyDirectory(tempExtractDirectory, normalizedInstallDirectory);

                var warnings = new List<string>();
                if (_desktopShortcutCheckBox.Checked)
                {
                    RunPowerShellScript(
                        Path.Combine(normalizedInstallDirectory, "scripts", "install-desktop-shortcut.ps1"),
                        normalizedInstallDirectory
                    );
                }
                if (_ccLauncherCheckBox.Checked)
                {
                    RunPowerShellScript(
                        Path.Combine(normalizedInstallDirectory, "scripts", "install-cc-launcher.ps1"),
                        normalizedInstallDirectory
                    );
                }
                if (_everythingClaudeCodeCheckBox.Checked)
                {
                    try
                    {
                        RunPowerShellScript(
                            Path.Combine(normalizedInstallDirectory, "scripts", "install-everything-claude-code.ps1"),
                            normalizedInstallDirectory,
                            "-Target claude -Profile full"
                        );
                    }
                    catch (Exception ex)
                    {
                        warnings.Add("Everything Claude Code install did not complete: " + ex.Message);
                    }
                }

                return new InstallResult
                {
                    InstallDirectory = normalizedInstallDirectory,
                    Warnings = warnings,
                };
            }
            finally
            {
                TryDeleteDirectory(tempRoot);
            }
        }

        private static void ExtractEmbeddedBundle(string targetZipPath)
        {
            var assembly = Assembly.GetExecutingAssembly();
            var resourceName = assembly.GetManifestResourceNames()
                .FirstOrDefault(name => name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase));
            if (string.IsNullOrWhiteSpace(resourceName))
            {
                throw new InvalidOperationException("Installer bundle resource is missing.");
            }

            var targetParent = Path.GetDirectoryName(targetZipPath);
            if (!string.IsNullOrWhiteSpace(targetParent))
            {
                Directory.CreateDirectory(targetParent);
            }

            using (var stream = assembly.GetManifestResourceStream(resourceName))
            {
                if (stream == null)
                {
                    throw new InvalidOperationException("Unable to open installer bundle resource.");
                }

                using (var file = File.Create(targetZipPath))
                {
                    stream.CopyTo(file);
                }
            }
        }

        private static void CopyDirectory(string sourceDirectory, string targetDirectory)
        {
            Directory.CreateDirectory(targetDirectory);
            foreach (var directory in Directory.GetDirectories(sourceDirectory, "*", SearchOption.AllDirectories))
            {
                var relativeDirectory = directory.Substring(sourceDirectory.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                Directory.CreateDirectory(Path.Combine(targetDirectory, relativeDirectory));
            }

            foreach (var file in Directory.GetFiles(sourceDirectory, "*", SearchOption.AllDirectories))
            {
                var relativeFile = file.Substring(sourceDirectory.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                var destination = Path.Combine(targetDirectory, relativeFile);
                var destinationParent = Path.GetDirectoryName(destination);
                if (!string.IsNullOrWhiteSpace(destinationParent))
                {
                    Directory.CreateDirectory(destinationParent);
                }
                File.Copy(file, destination, true);
            }
        }

        private static void RunPowerShellScript(string scriptPath, string workingDirectory, string extraArguments = "")
        {
            if (!File.Exists(scriptPath))
            {
                throw new FileNotFoundException("Required install script not found.", scriptPath);
            }

            var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = "-NoProfile -ExecutionPolicy Bypass -File " + QuoteArg(scriptPath) + (string.IsNullOrWhiteSpace(extraArguments) ? string.Empty : " " + extraArguments),
                    WorkingDirectory = workingDirectory,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                }
            };

            process.Start();
            var stdout = process.StandardOutput.ReadToEnd();
            var stderr = process.StandardError.ReadToEnd();
            process.WaitForExit();
            if (process.ExitCode != 0)
            {
                throw new InvalidOperationException(
                    (string.IsNullOrWhiteSpace(stderr) ? stdout : stderr).Trim()
                );
            }
        }

        private static void LaunchInstalledApp(string installDirectory)
        {
            var launcherPath = Path.Combine(installDirectory, "apps", "desktop-windows", "bin", "Claude Code.app.exe");
            if (!File.Exists(launcherPath))
            {
                throw new FileNotFoundException("Installed launcher exe was not found.", launcherPath);
            }

            Process.Start(new ProcessStartInfo
            {
                FileName = launcherPath,
                WorkingDirectory = installDirectory,
                UseShellExecute = true,
            });
        }

        private void ToggleBusy(bool busy, string statusText)
        {
            UseWaitCursor = busy;
            _installButton.Enabled = !busy;
            _cancelButton.Enabled = !busy;
            _browseButton.Enabled = !busy;
            _installPathBox.Enabled = !busy;
            _desktopShortcutCheckBox.Enabled = !busy;
            _ccLauncherCheckBox.Enabled = !busy;
            _everythingClaudeCodeCheckBox.Enabled = !busy;
            _launchAfterInstallCheckBox.Enabled = !busy;
            SetStatus(statusText, false);
            Application.DoEvents();
        }

        private void SetStatus(string message, bool isError)
        {
            _statusLabel.Text = message ?? string.Empty;
            _statusLabel.ForeColor = isError ? Color.Firebrick : Color.FromArgb(90, 90, 90);
        }

        private static void TryDeleteDirectory(string path)
        {
            try
            {
                if (Directory.Exists(path))
                {
                    Directory.Delete(path, true);
                }
            }
            catch
            {
            }
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

    internal sealed class InstallResult
    {
        internal string InstallDirectory { get; set; }
        internal List<string> Warnings { get; set; }
    }
}
