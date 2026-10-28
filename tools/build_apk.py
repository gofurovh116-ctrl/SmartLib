import os
import sys
import shutil
import subprocess
import zipfile
from PIL import Image

SDK_DIR = r"C:\Users\xgofu\AppData\Local\Android\Sdk"
BUILD_TOOLS_DIR = os.path.join(SDK_DIR, "build-tools", "35.0.0")
PLATFORM_DIR = os.path.join(SDK_DIR, "platforms", "android-36")
ANDROID_JAR = os.path.join(PLATFORM_DIR, "android.jar")
JDK_BIN = r"C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot\bin"

AAPT2 = os.path.join(BUILD_TOOLS_DIR, "aapt2.exe")
D8 = os.path.join(BUILD_TOOLS_DIR, "d8.bat")
ZIPALIGN = os.path.join(BUILD_TOOLS_DIR, "zipalign.exe")
APKSIGNER = os.path.join(BUILD_TOOLS_DIR, "apksigner.bat")
JAVAC = os.path.join(JDK_BIN, "javac.exe")
KEYTOOL = os.path.join(JDK_BIN, "keytool.exe")

PROJECT_DIR = r"D:\SmartLib\android_build"
DIST_DIR = r"D:\SmartLib\dist"
FINAL_APK = os.path.join(DIST_DIR, "SmartLib.apk")
MEDIA_APK = r"D:\SmartLib\media\SmartLib.apk"

def read_public_url():
    url_file = r"D:\SmartLib\backups\public_url.txt"
    if os.path.exists(url_file):
        with open(url_file, "r", encoding="utf-8") as f:
            u = f.read().strip()
            if u.startswith("http"):
                return u
    return "https://take-franchise-products-cigarette.trycloudflare.com"

def setup_directories():
    if os.path.exists(PROJECT_DIR):
        shutil.rmtree(PROJECT_DIR, ignore_errors=True)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    os.makedirs(os.path.join(PROJECT_DIR, "res", "values"), exist_ok=True)
    os.makedirs(os.path.join(PROJECT_DIR, "res", "layout"), exist_ok=True)
    os.makedirs(os.path.join(PROJECT_DIR, "src", "uz", "smartlib", "app"), exist_ok=True)
    os.makedirs(os.path.join(PROJECT_DIR, "bin"), exist_ok=True)
    os.makedirs(os.path.join(PROJECT_DIR, "bin", "classes"), exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(r"D:\SmartLib\media", exist_ok=True)

def generate_icons():
    source_icon = r"D:\SmartLib\dist\smartlib_icon.png"
    if not os.path.exists(source_icon):
        raise FileNotFoundError(f"Source icon not found: {source_icon}")

    src_img = Image.open(source_icon)
    densities = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    for folder, size in densities.items():
        folder_path = os.path.join(PROJECT_DIR, "res", folder)
        os.makedirs(folder_path, exist_ok=True)
        resized = src_img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(folder_path, "ic_launcher.png"), "PNG")
        # Also round icon
        resized.save(os.path.join(folder_path, "ic_launcher_round.png"), "PNG")
    print("[+] App icons generated for all densities.")

def write_manifest():
    manifest_content = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="uz.smartlib.app"
    android:versionCode="1"
    android:versionName="1.0.0">

    <uses-sdk
        android:minSdkVersion="24"
        android:targetSdkVersion="34" />

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-feature android:name="android.hardware.camera" android:required="false" />
    <uses-feature android:name="android.hardware.camera.autofocus" android:required="false" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.SmartLib"
        android:usesCleartextTraffic="true"
        android:hardwareAccelerated="true">
        <activity
            android:name="uz.smartlib.app.MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""
    with open(os.path.join(PROJECT_DIR, "AndroidManifest.xml"), "w", encoding="utf-8") as f:
        f.write(manifest_content.strip())
    print("[+] AndroidManifest.xml created.")

def write_resources():
    strings_xml = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">SmartLib</string>
    <string name="retry">Qayta urinish</string>
    <string name="change_server">Server manzilini sozlash</string>
    <string name="connecting">SmartLib tizimiga ulanmoqda...</string>
    <string name="offline_msg">Serverga ulanib bo‘lmadi. Internet yoki Wi-Fi tarmog‘ini tekshiring.</string>
</resources>
"""
    with open(os.path.join(PROJECT_DIR, "res", "values", "strings.xml"), "w", encoding="utf-8") as f:
        f.write(strings_xml.strip())

    colors_xml = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="primary">#2563EB</color>
    <color name="primary_dark">#1D4ED8</color>
    <color name="accent">#F59E0B</color>
    <color name="background">#F4F7FE</color>
    <color name="text_color">#1E293B</color>
</resources>
"""
    with open(os.path.join(PROJECT_DIR, "res", "values", "colors.xml"), "w", encoding="utf-8") as f:
        f.write(colors_xml.strip())

    styles_xml = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.SmartLib" parent="@android:style/Theme.Material.Light.NoActionBar">
        <item name="android:statusBarColor">#2563EB</item>
        <item name="android:navigationBarColor">#1E293B</item>
        <item name="android:windowBackground">@color/background</item>
    </style>
</resources>
"""
    with open(os.path.join(PROJECT_DIR, "res", "values", "styles.xml"), "w", encoding="utf-8") as f:
        f.write(styles_xml.strip())

    layout_xml = """<?xml version="1.0" encoding="utf-8"?>
<RelativeLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@color/background">

    <ProgressBar
        android:id="@+id/progressBar"
        style="?android:attr/progressBarStyleHorizontal"
        android:layout_width="match_parent"
        android:layout_height="4dp"
        android:layout_alignParentTop="true"
        android:max="100"
        android:visibility="gone" />

    <WebView
        android:id="@+id/webView"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:layout_below="@id/progressBar" />

    <LinearLayout
        android:id="@+id/errorLayout"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:orientation="vertical"
        android:gravity="center"
        android:padding="32dp"
        android:visibility="gone"
        android:background="#FFFFFF">

        <ImageView
            android:layout_width="96dp"
            android:layout_height="96dp"
            android:src="@mipmap/ic_launcher"
            android:contentDescription="SmartLib" />

        <TextView
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_marginTop="20dp"
            android:text="SmartLib Kutubxona"
            android:textSize="22sp"
            android:textStyle="bold"
            android:textColor="#1E293B" />

        <TextView
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_marginTop="10dp"
            android:gravity="center"
            android:text="@string/offline_msg"
            android:textSize="14sp"
            android:textColor="#64748B" />

        <Button
            android:id="@+id/btnRetry"
            android:layout_width="220dp"
            android:layout_height="50dp"
            android:layout_marginTop="24dp"
            android:background="#2563EB"
            android:textColor="#FFFFFF"
            android:text="@string/retry" />

        <Button
            android:id="@+id/btnChangeServer"
            android:layout_width="220dp"
            android:layout_height="45dp"
            android:layout_marginTop="12dp"
            android:background="#E2E8F0"
            android:textColor="#1E293B"
            android:text="@string/change_server" />
    </LinearLayout>
</RelativeLayout>
"""
    with open(os.path.join(PROJECT_DIR, "res", "layout", "activity_main.xml"), "w", encoding="utf-8") as f:
        f.write(layout_xml.strip())
    print("[+] Resources (values, colors, styles, layout) created.")

def write_main_activity(default_url):
    java_code = f"""package uz.smartlib.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

public class MainActivity extends Activity {{
    private static final String PREFS_NAME = "SmartLibPrefs";
    private static final String KEY_SERVER_URL = "server_url";
    private static final String DEFAULT_URL = "{default_url}";
    private static final int PERMISSION_REQUEST_CAMERA = 101;
    private static final int FILECHOOSER_RESULTCODE = 102;

    private WebView webView;
    private ProgressBar progressBar;
    private LinearLayout errorLayout;
    private Button btnRetry;
    private Button btnChangeServer;
    private SharedPreferences prefs;
    private ValueCallback<Uri[]> uploadMessage;

    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        webView = findViewById(R.id.webView);
        progressBar = findViewById(R.id.progressBar);
        errorLayout = findViewById(R.id.errorLayout);
        btnRetry = findViewById(R.id.btnRetry);
        btnChangeServer = findViewById(R.id.btnChangeServer);

        requestCameraPermission();
        configureWebView();

        btnRetry.setOnClickListener(new View.OnClickListener() {{
            @Override
            public void onClick(View v) {{
                errorLayout.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
                loadServer();
            }}
        }});

        btnChangeServer.setOnClickListener(new View.OnClickListener() {{
            @Override
            public void onClick(View v) {{
                showChangeServerDialog();
            }}
        }});

        loadServer();
    }}

    private void requestCameraPermission() {{
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {{
            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {{
                requestPermissions(new String[]{{Manifest.permission.CAMERA}}, PERMISSION_REQUEST_CAMERA);
            }}
        }}
    }}

    private void configureWebView() {{
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setUseWideViewPort(true);
        ws.setLoadWithOverviewMode(true);
        ws.setSupportZoom(true);
        ws.setBuiltInZoomControls(true);
        ws.setDisplayZoomControls(false);

        String userAgent = ws.getUserAgentString();
        ws.setUserAgentString(userAgent + " SmartLibApp/1.0 (Android)");

        webView.setWebViewClient(new WebViewClient() {{
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {{
                super.onPageStarted(view, url, favicon);
                progressBar.setVisibility(View.VISIBLE);
                errorLayout.setVisibility(View.GONE);
            }}

            @Override
            public void onPageFinished(WebView view, String url) {{
                super.onPageFinished(view, url);
                progressBar.setVisibility(View.GONE);
            }}

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {{
                if (request.isForMainFrame()) {{
                    progressBar.setVisibility(View.GONE);
                    webView.setVisibility(View.GONE);
                    errorLayout.setVisibility(View.VISIBLE);
                }}
            }}

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {{
                Uri uri = request.getUrl();
                String scheme = uri.getScheme();
                if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {{
                    return false;
                }}
                try {{
                    Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                    startActivity(intent);
                    return true;
                }} catch (Exception e) {{
                    return true;
                }}
            }}
        }});

        webView.setWebChromeClient(new WebChromeClient() {{
            @Override
            public void onProgressChanged(WebView view, int newProgress) {{
                progressBar.setProgress(newProgress);
                if (newProgress >= 100) {{
                    progressBar.setVisibility(View.GONE);
                }} else {{
                    progressBar.setVisibility(View.VISIBLE);
                }}
            }}

            @Override
            public void onPermissionRequest(final PermissionRequest request) {{
                // Grant camera access to the SmartLib Web QR scanner
                runOnUiThread(new Runnable() {{
                    @Override
                    public void run() {{
                        request.grant(request.getResources());
                    }}
                }});
            }}

            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {{
                if (uploadMessage != null) {{
                    uploadMessage.onReceiveValue(null);
                }}
                uploadMessage = filePathCallback;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("image/*");
                startActivityForResult(Intent.createChooser(intent, "Rasm tanlang"), FILECHOOSER_RESULTCODE);
                return true;
            }}
        }});
    }}

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {{
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILECHOOSER_RESULTCODE) {{
            if (uploadMessage == null) return;
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null) {{
                String dataString = data.getDataString();
                if (dataString != null) {{
                    results = new Uri[]{{Uri.parse(dataString)}};
                }}
            }}
            uploadMessage.onReceiveValue(results);
            uploadMessage = null;
        }}
    }}

    private void loadServer() {{
        String url = prefs.getString(KEY_SERVER_URL, DEFAULT_URL);
        webView.loadUrl(url);
    }}

    private void showChangeServerDialog() {{
        final EditText input = new EditText(this);
        String current = prefs.getString(KEY_SERVER_URL, DEFAULT_URL);
        input.setText(current);
        input.setSelection(current.length());

        new AlertDialog.Builder(this)
            .setTitle("Server manzilini kiritish")
            .setMessage("Online tunnel yoki lokal Wi-Fi IP manzilini kiriting (masalan: http://172.20.1.147:8000)")
            .setView(input)
            .setPositiveButton("Saqlash va Ulanish", new DialogInterface.OnClickListener() {{
                @Override
                public void onClick(DialogInterface dialog, int which) {{
                    String newUrl = input.getText().toString().trim();
                    if (!newUrl.startsWith("http://") && !newUrl.startsWith("https://")) {{
                        newUrl = "https://" + newUrl;
                    }}
                    prefs.edit().putString(KEY_SERVER_URL, newUrl).apply();
                    errorLayout.setVisibility(View.GONE);
                    webView.setVisibility(View.VISIBLE);
                    webView.loadUrl(newUrl);
                    Toast.makeText(MainActivity.this, "Manzil saqlandi: " + newUrl, Toast.LENGTH_SHORT).show();
                }}
            }})
            .setNeutralButton("Standartga qaytarish", new DialogInterface.OnClickListener() {{
                @Override
                public void onClick(DialogInterface dialog, int which) {{
                    prefs.edit().putString(KEY_SERVER_URL, DEFAULT_URL).apply();
                    errorLayout.setVisibility(View.GONE);
                    webView.setVisibility(View.VISIBLE);
                    webView.loadUrl(DEFAULT_URL);
                }}
            }})
            .setNegativeButton("Bekor qilish", null)
            .show();
    }}

    @Override
    public void onBackPressed() {{
        if (webView.canGoBack()) {{
            webView.goBack();
        }} else {{
            super.onBackPressed();
        }}
    }}
}}
"""
    java_path = os.path.join(PROJECT_DIR, "src", "uz", "smartlib", "app", "MainActivity.java")
    with open(java_path, "w", encoding="utf-8") as f:
        f.write(java_code)
    print(f"[+] MainActivity.java created with default URL: {default_url}")

def build_apk():
    print("[*] Starting SmartLib Android APK build...")
    url = read_public_url()
    print(f"[*] Target default server URL: {url}")
    
    setup_directories()
    generate_icons()
    write_manifest()
    write_resources()
    write_main_activity(url)

    # Step 1: AAPT2 compile resources
    print("[*] Step 1: Compiling resources with aapt2...")
    res_dir = os.path.join(PROJECT_DIR, "res")
    compiled_res_zip = os.path.join(PROJECT_DIR, "bin", "compiled_res.zip")
    cmd_compile = [AAPT2, "compile", "--dir", res_dir, "-o", compiled_res_zip]
    subprocess.check_call(cmd_compile)

    # Step 2: AAPT2 link
    print("[*] Step 2: Linking resources with aapt2...")
    manifest_xml = os.path.join(PROJECT_DIR, "AndroidManifest.xml")
    unaligned_apk = os.path.join(PROJECT_DIR, "bin", "base.apk")
    java_src_dir = os.path.join(PROJECT_DIR, "src")
    
    cmd_link = [
        AAPT2, "link",
        "-o", unaligned_apk,
        "-I", ANDROID_JAR,
        "--manifest", manifest_xml,
        compiled_res_zip,
        "--java", java_src_dir,
        "--auto-add-overlay"
    ]
    subprocess.check_call(cmd_link)
    print("[+] Resources linked. R.java generated.")

    # Step 3: Compile Java sources
    print("[*] Step 3: Compiling Java files with javac...")
    classes_dir = os.path.join(PROJECT_DIR, "bin", "classes")
    r_java = os.path.join(java_src_dir, "uz", "smartlib", "app", "R.java")
    main_java = os.path.join(java_src_dir, "uz", "smartlib", "app", "MainActivity.java")
    
    cmd_javac = [
        JAVAC,
        "-source", "8",
        "-target", "8",
        "-cp", ANDROID_JAR,
        "-d", classes_dir,
        r_java,
        main_java
    ]
    subprocess.check_call(cmd_javac)
    print("[+] Java classes compiled.")

    # Step 4: Convert classes to DEX with d8
    print("[*] Step 4: Compiling DEX with d8...")
    dex_output_dir = os.path.join(PROJECT_DIR, "bin", "dex")
    os.makedirs(dex_output_dir, exist_ok=True)
    
    # Collect all .class files
    class_files = []
    for root, _, files in os.walk(classes_dir):
        for file in files:
            if file.endswith(".class"):
                class_files.append(os.path.join(root, file))

    cmd_d8 = [
        D8,
        "--lib", ANDROID_JAR,
        "--output", dex_output_dir,
        "--min-api", "24"
    ] + class_files
    subprocess.check_call(cmd_d8, shell=True)
    dex_file = os.path.join(dex_output_dir, "classes.dex")
    if not os.path.exists(dex_file):
        raise FileNotFoundError(f"DEX file not found at {dex_file}")
    print("[+] DEX bytecode compiled successfully.")

    # Step 5: Add classes.dex into base.apk
    print("[*] Step 5: Injecting classes.dex into APK...")
    apk_with_dex = os.path.join(PROJECT_DIR, "bin", "app_with_dex.apk")
    shutil.copyfile(unaligned_apk, apk_with_dex)
    with zipfile.ZipFile(apk_with_dex, "a") as z:
        z.write(dex_file, "classes.dex")
    print("[+] classes.dex injected into APK.")

    # Step 6: Zipalign
    print("[*] Step 6: Aligning APK with zipalign...")
    aligned_apk = os.path.join(PROJECT_DIR, "bin", "app_aligned.apk")
    if os.path.exists(aligned_apk):
        os.remove(aligned_apk)
    cmd_zipalign = [
        ZIPALIGN,
        "-p", "-f", "-v", "4",
        apk_with_dex,
        aligned_apk
    ]
    subprocess.check_call(cmd_zipalign)
    print("[+] APK 4-byte aligned.")

    # Step 7: Create keystore if needed
    keystore_path = os.path.join(PROJECT_DIR, "smartlib.keystore")
    if not os.path.exists(keystore_path):
        print("[*] Generating release keystore...")
        cmd_keytool = [
            KEYTOOL,
            "-genkeypair",
            "-v",
            "-keystore", keystore_path,
            "-alias", "smartlib",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-storepass", "smartlib123",
            "-keypass", "smartlib123",
            "-dname", "CN=SmartLib, OU=App, O=SmartLib, L=Tashkent, C=UZ"
        ]
        subprocess.check_call(cmd_keytool)
        print("[+] Keystore generated.")

    # Step 8: Sign APK with apksigner
    print("[*] Step 8: Signing APK with apksigner...")
    if os.path.exists(FINAL_APK):
        os.remove(FINAL_APK)
    cmd_sign = [
        APKSIGNER,
        "sign",
        "--ks", keystore_path,
        "--ks-pass", "pass:smartlib123",
        "--ks-key-alias", "smartlib",
        "--key-pass", "pass:smartlib123",
        "--out", FINAL_APK,
        aligned_apk
    ]
    subprocess.check_call(cmd_sign, shell=True)
    print(f"[+] APK signed successfully: {FINAL_APK}")

    # Step 9: Verify APK signature
    print("[*] Step 9: Verifying APK signature...")
    cmd_verify = [APKSIGNER, "verify", "--verbose", FINAL_APK]
    subprocess.check_call(cmd_verify, shell=True)
    print("[+] APK signature verified.")

    # Step 10: Copy to media for web downloads
    shutil.copyfile(FINAL_APK, MEDIA_APK)
    print(f"[+] Downloadable copy placed at: {MEDIA_APK}")

    size_mb = os.path.getsize(FINAL_APK) / (1024 * 1024)
    print(f"\n=======================================================")
    print(f" SUCCESS! Android APK tayyor!")
    print(f" Fayl manzili: {FINAL_APK}")
    print(f" Hajmi: {size_mb:.2f} MB")
    print(f" Veb yuklab olish: http://127.0.0.1:8000/media/SmartLib.apk")
    print(f"=======================================================\n")

if __name__ == "__main__":
    try:
        build_apk()
    except Exception as e:
        print(f"[!] Error building APK: {e}", file=sys.stderr)
        sys.exit(1)
