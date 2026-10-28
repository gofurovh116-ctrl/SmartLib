using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace SmartLibDesktop
{
    public class Program
    {
        [STAThread]
        public static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }
    }

    public class MainForm : Form
    {
        private Label lblHeader;
        private Label lblSubHeader;
        private Label lblStatusLocal;
        private Label lblStatusTunnel;
        private Label lblStatusWifi;
        private TextBox txtTunnelUrl;
        private Button btnCopyTunnel;
        private Button btnLibrarian;
        private Button btnAdmin;
        private Button btnOpenApk;
        private Button btnShowQr;
        private Button btnRestartServer;
        private NotifyIcon trayIcon;
        private ContextMenuStrip trayMenu;
        private System.Windows.Forms.Timer statusTimer;

        private string localUrl = "http://127.0.0.1:8000";
        private string wifiUrl = "http://10.238.231.53:8000";
        private string tunnelUrl = "https://smartlib-1-olyc.onrender.com";
        private string baseDir = @"D:\SmartLib";
        private DateTime lastCloudPing = DateTime.MinValue;

        public MainForm()
        {
            InitializeComponent();
            LoadTunnelUrl();
            CheckAndEnsureServerRunning();
            StartTimer();
        }

        private void InitializeComponent()
        {
            this.Text = "SmartLib - Kutubxona Boshqaruv Markazi";
            this.Size = new Size(680, 560);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = Color.FromArgb(244, 247, 254);
            this.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);

            // Try loading window icon
            string iconPath = Path.Combine(baseDir, @"dist\smartlib_icon.ico");
            if (File.Exists(iconPath))
            {
                try { this.Icon = new Icon(iconPath); } catch { }
            }

            // Top Header Panel
            Panel pnlHeader = new Panel();
            pnlHeader.Dock = DockStyle.Top;
            pnlHeader.Height = 85;
            pnlHeader.BackColor = Color.FromArgb(37, 99, 235); // #2563eb

            lblHeader = new Label();
            lblHeader.Text = "SmartLib Kutubxona Tizimi";
            lblHeader.Font = new Font("Segoe UI", 16f, FontStyle.Bold);
            lblHeader.ForeColor = Color.White;
            lblHeader.Location = new Point(24, 16);
            lblHeader.AutoSize = true;

            lblSubHeader = new Label();
            lblSubHeader.Text = "Kutubxonachi va Admin boshqaruv dasturi | Telefonlar uchun online rejim";
            lblSubHeader.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            lblSubHeader.ForeColor = Color.FromArgb(219, 234, 254);
            lblSubHeader.Location = new Point(26, 48);
            lblSubHeader.AutoSize = true;

            pnlHeader.Controls.Add(lblHeader);
            pnlHeader.Controls.Add(lblSubHeader);
            this.Controls.Add(pnlHeader);

            // Main Content Panel
            Panel pnlContent = new Panel();
            pnlContent.Location = new Point(24, 100);
            pnlContent.Size = new Size(616, 400);

            // Group 1: Server Status
            GroupBox grpStatus = new GroupBox();
            grpStatus.Text = " Tizim Holati va Ulanish Manzillari ";
            grpStatus.Location = new Point(0, 0);
            grpStatus.Size = new Size(616, 155);
            grpStatus.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);

            lblStatusLocal = new Label();
            lblStatusLocal.Text = " Kompyuter (Lokal): http://127.0.0.1:8000";
            lblStatusLocal.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            lblStatusLocal.ForeColor = Color.FromArgb(16, 149, 193);
            lblStatusLocal.Location = new Point(16, 28);
            lblStatusLocal.AutoSize = true;

            lblStatusWifi = new Label();
            lblStatusWifi.Text = " Wi-Fi Tarmog'i: " + wifiUrl;
            lblStatusWifi.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            lblStatusWifi.ForeColor = Color.FromArgb(71, 85, 105);
            lblStatusWifi.Location = new Point(16, 56);
            lblStatusWifi.AutoSize = true;

            Label lblTunTitle = new Label();
            lblTunTitle.Text = " Render Cloud 24/7 Manzil (Telefonlar uchun uzluksiz):";
            lblTunTitle.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            lblTunTitle.ForeColor = Color.FromArgb(30, 41, 59);
            lblTunTitle.Location = new Point(16, 84);
            lblTunTitle.AutoSize = true;

            txtTunnelUrl = new TextBox();
            txtTunnelUrl.Location = new Point(18, 110);
            txtTunnelUrl.Size = new Size(460, 26);
            txtTunnelUrl.ReadOnly = true;
            txtTunnelUrl.BackColor = Color.White;
            txtTunnelUrl.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);

            btnCopyTunnel = new Button();
            btnCopyTunnel.Text = "Nusxa olish";
            btnCopyTunnel.Location = new Point(488, 108);
            btnCopyTunnel.Size = new Size(110, 28);
            btnCopyTunnel.BackColor = Color.FromArgb(226, 232, 240);
            btnCopyTunnel.FlatStyle = FlatStyle.Flat;
            btnCopyTunnel.FlatAppearance.BorderSize = 0;
            btnCopyTunnel.Font = new Font("Segoe UI", 9f, FontStyle.Regular);
            btnCopyTunnel.Click += (s, e) => {
                if (!string.IsNullOrEmpty(txtTunnelUrl.Text))
                {
                    Clipboard.SetText(txtTunnelUrl.Text);
                    MessageBox.Show("Telefonlar uchun havola xotiraga nusxalandi:\n" + txtTunnelUrl.Text, "Nusxalandi", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
            };

            grpStatus.Controls.Add(lblStatusLocal);
            grpStatus.Controls.Add(lblStatusWifi);
            grpStatus.Controls.Add(lblTunTitle);
            grpStatus.Controls.Add(txtTunnelUrl);
            grpStatus.Controls.Add(btnCopyTunnel);
            pnlContent.Controls.Add(grpStatus);

            // Group 2: Action Buttons
            GroupBox grpActions = new GroupBox();
            grpActions.Text = " Tezkor Boshqaruv Tugmalari ";
            grpActions.Location = new Point(0, 170);
            grpActions.Size = new Size(616, 215);
            grpActions.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);

            // 1. Librarian Desk
            btnLibrarian = new Button();
            btnLibrarian.Text = " Kutubxonachi Ish Stoli (Librarian Desk)";
            btnLibrarian.Location = new Point(18, 30);
            btnLibrarian.Size = new Size(280, 50);
            btnLibrarian.BackColor = Color.FromArgb(37, 99, 235); // #2563eb
            btnLibrarian.ForeColor = Color.White;
            btnLibrarian.FlatStyle = FlatStyle.Flat;
            btnLibrarian.FlatAppearance.BorderSize = 0;
            btnLibrarian.Font = new Font("Segoe UI", 10.5f, FontStyle.Bold);
            btnLibrarian.Click += (s, e) => OpenUrl(localUrl + "/librarian/");

            // 2. Admin Panel
            btnAdmin = new Button();
            btnAdmin.Text = " Admin Boshqaruv Paneli";
            btnAdmin.Location = new Point(318, 30);
            btnAdmin.Size = new Size(280, 50);
            btnAdmin.BackColor = Color.FromArgb(30, 41, 59); // dark slate
            btnAdmin.ForeColor = Color.White;
            btnAdmin.FlatStyle = FlatStyle.Flat;
            btnAdmin.FlatAppearance.BorderSize = 0;
            btnAdmin.Font = new Font("Segoe UI", 10.5f, FontStyle.Bold);
            btnAdmin.Click += (s, e) => OpenUrl(localUrl + "/admin/");

            // 3. QR Code & Readers Link
            btnShowQr = new Button();
            btnShowQr.Text = " Telefonlar Uchun QR Kod & Havola";
            btnShowQr.Location = new Point(18, 92);
            btnShowQr.Size = new Size(280, 46);
            btnShowQr.BackColor = Color.FromArgb(16, 185, 129); // emerald green
            btnShowQr.ForeColor = Color.White;
            btnShowQr.FlatStyle = FlatStyle.Flat;
            btnShowQr.FlatAppearance.BorderSize = 0;
            btnShowQr.Font = new Font("Segoe UI", 10f, FontStyle.Bold);
            btnShowQr.Click += (s, e) => OpenUrl(localUrl + "/");

            // 4. Open Mobile APK Folder
            btnOpenApk = new Button();
            btnOpenApk.Text = " Telefon APK Faylini Ochish (.apk)";
            btnOpenApk.Location = new Point(318, 92);
            btnOpenApk.Size = new Size(280, 46);
            btnOpenApk.BackColor = Color.FromArgb(245, 158, 11); // amber
            btnOpenApk.ForeColor = Color.White;
            btnOpenApk.FlatStyle = FlatStyle.Flat;
            btnOpenApk.FlatAppearance.BorderSize = 0;
            btnOpenApk.Font = new Font("Segoe UI", 10f, FontStyle.Bold);
            btnOpenApk.Click += (s, e) => OpenApkFolder();

            // 5. Restart Server / Tunnel
            btnRestartServer = new Button();
            btnRestartServer.Text = " Qayta ishga tushirish (Restart Server)";
            btnRestartServer.Location = new Point(18, 152);
            btnRestartServer.Size = new Size(580, 40);
            btnRestartServer.BackColor = Color.FromArgb(241, 245, 249);
            btnRestartServer.ForeColor = Color.FromArgb(51, 65, 85);
            btnRestartServer.FlatStyle = FlatStyle.Flat;
            btnRestartServer.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
            btnRestartServer.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            btnRestartServer.Click += (s, e) => RestartServices();

            grpActions.Controls.Add(btnLibrarian);
            grpActions.Controls.Add(btnAdmin);
            grpActions.Controls.Add(btnShowQr);
            grpActions.Controls.Add(btnOpenApk);
            grpActions.Controls.Add(btnRestartServer);
            pnlContent.Controls.Add(grpActions);

            this.Controls.Add(pnlContent);

            // System Tray Setup
            trayMenu = new ContextMenuStrip();
            trayMenu.Items.Add("Ochish (SmartLib)", null, (s, e) => RestoreFromTray());
            trayMenu.Items.Add("Kutubxonachi Ish Stoli", null, (s, e) => OpenUrl(localUrl + "/librarian/"));
            trayMenu.Items.Add("Admin Panel", null, (s, e) => OpenUrl(localUrl + "/admin/"));
            trayMenu.Items.Add("-");
            trayMenu.Items.Add("Chiqish (Exit)", null, (s, e) => Application.Exit());

            trayIcon = new NotifyIcon();
            trayIcon.Text = "SmartLib Kutubxona Tizimi";
            if (this.Icon != null) trayIcon.Icon = this.Icon;
            trayIcon.ContextMenuStrip = trayMenu;
            trayIcon.Visible = true;
            trayIcon.DoubleClick += (s, e) => RestoreFromTray();

            this.Resize += (s, e) => {
                if (this.WindowState == FormWindowState.Minimized)
                {
                    this.Hide();
                    trayIcon.ShowBalloonTip(1500, "SmartLib Tizimi", "Dastur orqa fonda ishlamoqda. Ochish uchun bosing.", ToolTipIcon.Info);
                }
            };
        }

        private void RestoreFromTray()
        {
            this.Show();
            this.WindowState = FormWindowState.Normal;
            this.BringToFront();
        }

        private void LoadTunnelUrl()
        {
            string urlFile = Path.Combine(baseDir, @"backups\public_url.txt");
            if (File.Exists(urlFile))
            {
                try
                {
                    string u = File.ReadAllText(urlFile).Trim();
                    if (u.StartsWith("http"))
                    {
                        tunnelUrl = u;
                    }
                }
                catch { }
            }
            txtTunnelUrl.Text = tunnelUrl;
        }

        private void StartTimer()
        {
            statusTimer = new System.Windows.Forms.Timer();
            statusTimer.Interval = 5000;
            statusTimer.Tick += (s, e) => {
                LoadTunnelUrl();
                CheckServerStatus();
                CheckAndPingCloud();
            };
            statusTimer.Start();
        }

        private void CheckAndPingCloud()
        {
            if ((DateTime.Now - lastCloudPing).TotalMinutes >= 8)
            {
                lastCloudPing = DateTime.Now;
                ThreadPool.QueueUserWorkItem(_ => PingCloudKeepAlive());
            }
        }

        private void PingCloudKeepAlive()
        {
            try
            {
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create("https://smartlib-1-olyc.onrender.com/health/");
                req.Timeout = 8000;
                req.UserAgent = "SmartLib-Desktop-KeepAlive/1.0";
                using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse()) { }
            }
            catch { }
        }

        private bool CheckServerStatus()
        {
            try
            {
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create(localUrl + "/books/");
                req.Timeout = 1500;
                req.Method = "HEAD";
                using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                {
                    if (resp.StatusCode == HttpStatusCode.OK)
                    {
                        lblStatusLocal.Text = " Kompyuter (Lokal): http://127.0.0.1:8000 [ISHLAMOQDA]";
                        lblStatusLocal.ForeColor = Color.FromArgb(16, 149, 193);
                        return true;
                    }
                }
            }
            catch
            {
                lblStatusLocal.Text = " Kompyuter (Lokal): http://127.0.0.1:8000 [SERVER TO'XTAGAN]";
                lblStatusLocal.ForeColor = Color.Red;
            }
            return false;
        }

        private void CheckAndEnsureServerRunning()
        {
            if (!CheckServerStatus())
            {
                // Start start_online.bat in background
                string startScript = Path.Combine(baseDir, "start_online.bat");
                if (File.Exists(startScript))
                {
                    try
                    {
                        ProcessStartInfo psi = new ProcessStartInfo();
                        psi.FileName = startScript;
                        psi.WorkingDirectory = baseDir;
                        psi.WindowStyle = ProcessWindowStyle.Hidden;
                        psi.CreateNoWindow = true;
                        Process.Start(psi);
                    }
                    catch { }
                }
            }
        }

        private void RestartServices()
        {
            string startScript = Path.Combine(baseDir, "start_online.bat");
            if (File.Exists(startScript))
            {
                try
                {
                    ProcessStartInfo psi = new ProcessStartInfo();
                    psi.FileName = startScript;
                    psi.WorkingDirectory = baseDir;
                    Process.Start(psi);
                    MessageBox.Show("Server va tunnel qayta ishga tushirildi!", "Muvaffaqiyatli", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Xatolik: " + ex.Message, "Xato", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        private void OpenUrl(string url)
        {
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show("Brauzerni ochib bo'lmadi: " + ex.Message, "Xato", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OpenApkFolder()
        {
            string apkPath = Path.Combine(baseDir, @"dist\SmartLib.apk");
            if (File.Exists(apkPath))
            {
                Process.Start("explorer.exe", string.Format("/select,\"{0}\"", apkPath));
            }
            else
            {
                string distFolder = Path.Combine(baseDir, "dist");
                if (Directory.Exists(distFolder))
                {
                    Process.Start("explorer.exe", distFolder);
                }
            }
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            if (e.CloseReason == CloseReason.UserClosing)
            {
                DialogResult res = MessageBox.Show(
                    "SmartLib dasturidan to'liq chiqmoqchimisiz?\n\n(Eslatma: Agar 'Yo'q' bossangiz, dastur orqa fonda soat yonidagi patnisda (tray) ishlashda davom etadi)",
                    "SmartLib Chiqish",
                    MessageBoxButtons.YesNoCancel,
                    MessageBoxIcon.Question
                );

                if (res == DialogResult.No)
                {
                    e.Cancel = true;
                    this.WindowState = FormWindowState.Minimized;
                    return;
                }
                else if (res == DialogResult.Cancel)
                {
                    e.Cancel = true;
                    return;
                }
            }
            if (trayIcon != null)
            {
                trayIcon.Visible = false;
                trayIcon.Dispose();
            }
            base.OnFormClosing(e);
        }
    }
}
