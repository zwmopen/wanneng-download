using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace UniversalCollectorShell
{
    internal static class NativeMethods
    {
        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll")]
        public static extern bool SetProcessDPIAware();

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        public static extern int SetCurrentProcessExplicitAppUserModelID(string appID);

        [DllImport("user32.dll")]
        public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

        [DllImport("user32.dll")]
        public static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        public static extern bool SetForegroundWindow(IntPtr hWnd);

        public const int SW_RESTORE = 9;
    }

    internal static class Program
    {
        private const string AppId = "UniversalCollector.Workbench.Desktop";
        private const string MutexName = "UniversalCollectorWorkbench_SingleInstance_v1";

        [STAThread]
        private static void Main()
        {
            try { NativeMethods.SetProcessDPIAware(); } catch { }
            try { NativeMethods.SetCurrentProcessExplicitAppUserModelID(AppId); } catch { }

            bool createdNew;
            using (Mutex mutex = new Mutex(true, MutexName, out createdNew))
            {
                if (!createdNew)
                {
                    ActivateExistingWindow();
                    return;
                }

                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new MainForm());
            }
        }

        private static void ActivateExistingWindow()
        {
            NativeMethods.EnumWindows(delegate(IntPtr hWnd, IntPtr lParam)
            {
                if (!NativeMethods.IsWindowVisible(hWnd)) return true;
                StringBuilder sb = new StringBuilder(512);
                if (NativeMethods.GetWindowText(hWnd, sb, 512) > 0)
                {
                    string title = sb.ToString();
                    if (title.Contains("万能采集器"))
                    {
                        NativeMethods.ShowWindow(hWnd, NativeMethods.SW_RESTORE);
                        NativeMethods.SetForegroundWindow(hWnd);
                        return false;
                    }
                }
                return true;
            }, IntPtr.Zero);
        }
    }

    internal sealed class MainForm : Form
    {
        private const string BaseUrl = "http://127.0.0.1:5678/";
        private const string HealthUrl = "http://127.0.0.1:5678/api/v1/health";

        private readonly WebView2 _webView;
        private readonly Panel _splashPanel;
        private readonly Label _splashLabel;
        private readonly Button _retryButton;
        private readonly string _projectRoot;
        private bool _navigatedToApp = false;
        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromMilliseconds(900) };

        public MainForm()
        {
            _projectRoot = ResolveProjectRoot();
            Text = "万能采集器 · 统一智能采集工作台";
            Width = 1480;
            Height = 920;
            MinimumSize = new Size(1024, 680);
            StartPosition = FormStartPosition.CenterScreen;
            ShowInTaskbar = true;
            BackColor = Color.FromArgb(232, 237, 243);

            try
            {
                Icon exeIcon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
                if (exeIcon != null) Icon = exeIcon;
            }
            catch { }

            _webView = new WebView2();
            _webView.Dock = DockStyle.Fill;
            Controls.Add(_webView);

            _splashPanel = new Panel();
            _splashPanel.Dock = DockStyle.Fill;
            _splashPanel.BackColor = Color.FromArgb(232, 237, 243);

            _splashLabel = new Label();
            _splashLabel.Dock = DockStyle.Fill;
            _splashLabel.TextAlign = ContentAlignment.MiddleCenter;
            _splashLabel.Font = new Font("Microsoft YaHei UI", 13F, FontStyle.Bold);
            _splashLabel.ForeColor = Color.FromArgb(31, 41, 55);
            _splashLabel.Text = "∞  万能采集器启动中，正在连接本地工作台…";
            _splashPanel.Controls.Add(_splashLabel);

            _retryButton = new Button();
            _retryButton.Text = "重新连接并刷新页面";
            _retryButton.Size = new Size(188, 40);
            _retryButton.Font = new Font("Microsoft YaHei UI", 10F, FontStyle.Bold);
            _retryButton.BackColor = Color.FromArgb(38, 105, 155);
            _retryButton.ForeColor = Color.White;
            _retryButton.FlatStyle = FlatStyle.Flat;
            _retryButton.FlatAppearance.BorderSize = 0;
            _retryButton.Cursor = Cursors.Hand;
            _retryButton.Visible = false;
            _retryButton.Anchor = AnchorStyles.Bottom;
            _retryButton.Location = new Point((_splashPanel.Width - _retryButton.Width) / 2, _splashPanel.Height - 130);
            _splashPanel.SizeChanged += delegate
            {
                _retryButton.Location = new Point((_splashPanel.Width - _retryButton.Width) / 2, Math.Max(40, _splashPanel.Height / 2 + 48));
            };
            _retryButton.Click += async delegate
            {
                _retryButton.Visible = false;
                _splashLabel.Text = "∞  正在重新连接本地服务并加载工作台…";
                await ConnectAndNavigateAsync();
            };
            _splashPanel.Controls.Add(_retryButton);
            _retryButton.BringToFront();

            Controls.Add(_splashPanel);
            _splashPanel.BringToFront();

            Load += MainForm_Load;
        }

        private async void MainForm_Load(object sender, EventArgs e)
        {
            Task<bool> backendTask = EnsureBackendRunningAsync();

            try
            {
                string userData = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                    ".xhs-dl",
                    "webview2-shell"
                );
                Directory.CreateDirectory(userData);
                CoreWebView2Environment env = await CoreWebView2Environment.CreateAsync(null, userData, null);
                await _webView.EnsureCoreWebView2Async(env);

                _webView.CoreWebView2.Settings.AreDefaultScriptDialogsEnabled = true;
                _webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
                _webView.CoreWebView2.Settings.AreDevToolsEnabled = true;

                _webView.CoreWebView2.NewWindowRequested += delegate(object s, CoreWebView2NewWindowRequestedEventArgs args)
                {
                    if (!string.IsNullOrEmpty(args.Uri) && !args.Uri.StartsWith(BaseUrl, StringComparison.OrdinalIgnoreCase))
                    {
                        args.Handled = true;
                        try { Process.Start(new ProcessStartInfo(args.Uri) { UseShellExecute = true }); } catch { }
                    }
                };

                _webView.CoreWebView2.NavigationCompleted += delegate(object s, CoreWebView2NavigationCompletedEventArgs args)
                {
                    if (!_navigatedToApp)
                    {
                        return;
                    }
                    string currentUri = _webView.Source != null ? _webView.Source.ToString() : "";
                    if (args.IsSuccess && currentUri.StartsWith(BaseUrl, StringComparison.OrdinalIgnoreCase))
                    {
                        _retryButton.Visible = false;
                        _splashPanel.Visible = false;
                    }
                    else
                    {
                        _splashLabel.Text = "工作台页面加载失败（" + args.WebErrorStatus + "），请点击下方按钮重试。";
                        _retryButton.Visible = true;
                        _splashPanel.Visible = true;
                        _splashPanel.BringToFront();
                    }
                };
            }
            catch (Exception ex)
            {
                _splashLabel.Text = "WebView2 桌面内核初始化失败：" + ex.Message;
                return;
            }

            await FinishConnectAndNavigateAsync(backendTask);
        }

        private async Task ConnectAndNavigateAsync()
        {
            await FinishConnectAndNavigateAsync(EnsureBackendRunningAsync());
        }

        private async Task FinishConnectAndNavigateAsync(Task<bool> backendTask)
        {
            bool ready = await backendTask;
            if (!ready)
            {
                _navigatedToApp = false;
                _splashLabel.Text = "未能连接本地服务 http://127.0.0.1:5678 ，请检查 Python 环境或点击下方按钮重试。";
                _retryButton.Visible = true;
                _splashPanel.Visible = true;
                _splashPanel.BringToFront();
                return;
            }

            _navigatedToApp = true;
            _webView.CoreWebView2.Navigate(BaseUrl);
        }

        private async Task<bool> EnsureBackendRunningAsync()
        {
            long localStamp = GetLatestWebCodeStamp();
            Tuple<bool, long> health = await CheckBackendHealthAsync();
            if (health.Item1)
            {
                if (health.Item2 >= localStamp && health.Item2 > 0)
                {
                    return true;
                }
                if (_splashLabel != null && !_splashLabel.IsDisposed)
                {
                    _splashLabel.Text = "∞  检测到新版界面/核心，正在自动刷新本地服务…";
                }
                try
                {
                    await Http.PostAsync(BaseUrl + "api/v1/server/shutdown", new StringContent("{}", Encoding.UTF8, "application/json"));
                }
                catch { }
                for (int i = 0; i < 12; i++)
                {
                    await Task.Delay(220);
                    if (!await IsHealthyAsync()) break;
                }
                if (await IsHealthyAsync())
                {
                    StopStaleWorkbenchPythonProcesses();
                    await Task.Delay(400);
                }
            }

            LaunchBackendProcess();

            DateTime deadline = DateTime.UtcNow.AddSeconds(14);
            while (DateTime.UtcNow < deadline)
            {
                await Task.Delay(150);
                if (await IsHealthyAsync()) return true;
            }
            return false;
        }

        private long GetLatestWebCodeStamp()
        {
            long latest = 0;
            try
            {
                string[] dirs = new[]
                {
                    Path.Combine(_projectRoot, "xhs_dl", "web"),
                    Path.Combine(_projectRoot, "xhs_dl", "core"),
                };
                foreach (string dir in dirs)
                {
                    if (Directory.Exists(dir))
                    {
                        foreach (string file in Directory.GetFiles(dir, "*.py"))
                        {
                            DateTime utc = File.GetLastWriteTimeUtc(file);
                            long unix = new DateTimeOffset(DateTime.SpecifyKind(utc, DateTimeKind.Utc)).ToUnixTimeSeconds();
                            if (unix > latest) latest = unix;
                        }
                    }
                }
            }
            catch { }
            return latest;
        }

        private static async Task<Tuple<bool, long>> CheckBackendHealthAsync()
        {
            try
            {
                using (HttpResponseMessage resp = await Http.GetAsync(HealthUrl))
                {
                    if ((int)resp.StatusCode != 200) return Tuple.Create(false, 0L);
                    string body = await resp.Content.ReadAsStringAsync();
                    System.Text.RegularExpressions.Match m = System.Text.RegularExpressions.Regex.Match(
                        body ?? "", "\"code_stamp\"\\s*:\\s*(\\d+)"
                    );
                    long stamp = 0;
                    if (m.Success) long.TryParse(m.Groups[1].Value, out stamp);
                    return Tuple.Create(true, stamp);
                }
            }
            catch
            {
                return Tuple.Create(false, 0L);
            }
        }

        private static void StopStaleWorkbenchPythonProcesses()
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = "powershell.exe";
                psi.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command \"Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\\.exe$' -and $_.CommandLine -match 'xhs_dl\\.web\\.app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\"";
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                Process p = Process.Start(psi);
                if (p != null) p.WaitForExit(3000);
            }
            catch { }
        }

        private static async Task<bool> IsHealthyAsync()
        {
            Tuple<bool, long> h = await CheckBackendHealthAsync();
            return h.Item1;
        }

        private void LaunchBackendProcess()
        {
            string pythonw = FindPythonwExecutable();
            if (string.IsNullOrEmpty(pythonw)) return;

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = pythonw;
            psi.Arguments = "-m xhs_dl.web.app --no-open";
            psi.WorkingDirectory = _projectRoot;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.WindowStyle = ProcessWindowStyle.Hidden;

            string cfgPath = Path.Combine(_projectRoot, "config", "config.json");
            if (File.Exists(cfgPath)) psi.EnvironmentVariables["MATERIAL_HUB_CONFIG"] = cfgPath;
            string runtimeDir = @"D:\AICode\运行数据\江湖工具箱\repair-smoke-v4-20261112";
            if (Directory.Exists(runtimeDir))
            {
                psi.EnvironmentVariables["JIANGHU_RUNTIME_DIR"] = runtimeDir;
                psi.EnvironmentVariables["JIANGHU_BRIDGE_DIR"] = Path.Combine(runtimeDir, "runtime", "bridge");
                psi.EnvironmentVariables["JIANGHU_HEADLESS_MODE"] = "1";
            }

            try { Process.Start(psi); } catch { }
        }

        private static string FindPythonwExecutable()
        {
            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            List<string> candidates = new List<string>
            {
                Path.Combine(localApp, @"Programs\Python\Python311\pythonw.exe"),
                Path.Combine(localApp, @"Programs\Python\Python312\pythonw.exe"),
                @"C:\Windows\pyw.exe",
                "pythonw.exe"
            };
            foreach (string path in candidates)
            {
                if (path == "pythonw.exe" || File.Exists(path)) return path;
            }
            return null;
        }

        private static string ResolveProjectRoot()
        {
            string exeDir = Path.GetDirectoryName(Application.ExecutablePath) ?? ".";
            DirectoryInfo dir = new DirectoryInfo(exeDir);
            if (dir.Parent != null && File.Exists(Path.Combine(dir.Parent.FullName, "pyproject.toml")))
            {
                return dir.Parent.FullName;
            }
            if (File.Exists(Path.Combine(dir.FullName, "pyproject.toml")) || Directory.Exists(Path.Combine(dir.FullName, "xhs_dl")))
            {
                return dir.FullName;
            }
            return dir.Parent != null ? dir.Parent.FullName : dir.FullName;
        }
    }
}
