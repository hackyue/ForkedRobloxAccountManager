<div align="center">

# 🚀 Forked Roblox Account Manager

<p align="center">
  <b>The Roblox account manager built with Tauri, Rust, Vite, and Python.</b>
  <br>
  Manage unlimited accounts, multiple instances, account creation, roblox settings, all in one place.
</p>

<p align="center">
  <a href="https://github.com/hackyue/ForkedRobloxAccountManager/releases/latest">
    <img src="https://img.shields.io/github/v/release/hackyue/ForkedRobloxAccountManager?style=for-the-badge&color=7289da&logo=github" alt="Latest Release">
  </a>
  <a href="https://github.com/hackyue/ForkedRobloxAccountManager/releases">
    <img src="https://img.shields.io/github/downloads/hackyue/ForkedRobloxAccountManager/total.svg?style=for-the-badge&color=34d399&logo=github" alt="Downloads">
  </a>
  <img src="https://komarev.com/ghpvc/?username=hackyue-ForkedRobloxAccountManager&label=Visitors&color=6366f1&style=for-the-badge" alt="Visitor Count">
  <a href="https://www.youtube.com/@hackyue">
    <img src="https://img.shields.io/badge/YouTube-@hackyue-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube Channel">
  </a>
  <a href="https://discord.gg/SpMTxg8YjJ">
    <img src="https://img.shields.io/discord/1449551915464790170?style=for-the-badge&logo=discord&color=5865F2" alt="Discord Community">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-GPL_v3-f59e0b?style=for-the-badge" alt="License">
  </a>
</p>

<p align="center">
  Forked & Maintained by <b>hackyue</b> · Contact: <a href="https://discord.gg/SpMTxg8YjJ">Discord Server</a>
  <br>
  ⭐ <i>If you find this project useful, please consider starring the repository!</i> ⭐
</p>

</div>

---

## 📷 Interface

### Account List

<p align="center">
  <img src="https://i.ibb.co/x8Fv0z6c/image.png" alt="Account List" />
</p>

### Instance Manager

<p align="center">
  <img src="https://i.ibb.co/6J0c812M/image.png" alt="Instance Manager" />
</p>

### VIP Server Manager

<p align="center">
  <img src="https://i.ibb.co/VY8vcKR8/image.png" alt="VIP Server Manager" />
</p>

---

## 🛠️ Installation & Getting Started

### 🚀 Option 1: Release Installer (Recommended for Users)

> [!TIP]
> **No Python or Node.js setup required!** Download the installer bundle and install.

1. Go to the [Releases Page](https://github.com/hackyue/ForkedRobloxAccountManager/releases).
2. Download the installer bundle from the latest release:
   - **`FRAM_<version>_x64-setup.exe`** (NSIS Installer - Recommended)
   - or **`FRAM_<version>_x64_en-US.msi`** (Windows MSI Package)
3. Run the installer and complete the setup.
4. Launch **Forked Roblox Account Manager** from your Start Menu or Desktop!

> [!NOTE]
> **System Requirements**: Windows 10/11 with Google Chrome, Edge, Firefox, Waterfox, or Chromium installed.
> If Windows Defender shows a SmartScreen warning, click **"More info" → "Run anyway"**.

---

### 💻 Option 2: Developer Setup (Build from Source)

> [!IMPORTANT]
> **Prerequisites**: Node.js (v18+), Python (v3.8+), Rust (Cargo/Tauri toolchain), Git.

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/hackyue/ForkedRobloxAccountManager.git
   cd ForkedRobloxAccountManager
   ```

2. **Install Frontend & Backend Dependencies**:
   ```bash
   npm install
   cd backend
   pip install -r requirements.txt
   cd ..
   ```

3. **Start Development Server**:

   **PowerShell**:
   ```powershell
   .\start-tauri-dev.ps1
   ```

   **Command Prompt**:
   ```cmd
   .\start-tauri-dev.bat
   ```

4. **Build Release Bundle**:
   ```cmd
   .\build-release.bat
   ```


---

## 🔐 Encryption 

Forked Roblox Account Manager v3 uses **AES-256-GCM** encryption to protect account credentials:

| Encryption Mode | Security | Portability | Password Required? | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Hardware Encryption** | 🟢 High | 🔴 No | ❌ No | Encrypts data using your PC's unique Hardware ID. Automatic, zero-configuration. Cannot be read on another PC. |
| **Password Encryption** | 🟢 High | 🟢 Yes | ✅ Yes | Encrypts data with a Master Password. Fully portable across PCs. **No password recovery exists if forgotten.** |
| **No Encryption** | 🔴 Low | 🟢 Yes | ❌ No | Plaintext storage. Convenient for testing, but not recommended for sensitive accounts. |

---

## 📚 Frequently Asked Questions (FAQ)

<details>
<summary><b>Q: Is Forked Roblox Account Manager safe to use?</b></summary>
<br>
<b>A:</b> Yes! The application runs completely locally on your computer. Web requests are communicated directly between your machine and official Roblox API endpoints (<code>roblox.com</code>). Your account credentials are never sent to external servers.
</details>

<details>
<summary><b>Q: How does Multi-Roblox work? Do I need third-party tools?</b></summary>
<br>
<b>A:</b> No additional software or injectors are required. FRAM has built-in multi-instance support by handling the Windows single-instance mutexes (<code>ROBLOX_singletonEvent</code> and <code>ROBLOX_singletonMutex</code>), allowing you to run multiple Roblox accounts simultaneously without conflicts.
</details>

<details>
<summary><b>Q: How can I add or import my accounts?</b></summary>
<br>
<b>A:</b> FRAM supports several convenient import and login methods:
<ul>
  <li><b>Browser Login:</b> Launch a browser window (Chrome, Edge, Firefox, Waterfox, or Chromium) to sign in directly.</li>
  <li><b>Cookie Import:</b> Paste a <code>.ROBLOSECURITY</code> cookie token or bulk import from text files.</li>
  <li><b>User:Pass Combo:</b> Mass import account credentials formatted as <code>username:password</code>.</li>
  <li><b>Quick Sign-In:</b> Connect instantly using Roblox 6-digit Quick Sign-In codes generated from an existing logged-in device.</li>
</ul>
</details>

<details>
<summary><b>Q: Which bootstrappers and Roblox versions are supported?</b></summary>
<br>
<b>A:</b> FRAM supports the standard Roblox Player alongside custom bootstrappers including <b>Voidstrap</b>, <b>Bloxstrap</b>, <b>Fishstrap</b>, <b>Froststrap</b>, and <b>ExploitStrap</b>. You can also use custom bootstrappers
</details>

<details>
<summary><b>Q: What is Streamer Mode?</b></summary>
<br>
<b>A:</b> Streamer Mode censors sensitive account details (usernames, account IDs, avatars, and notes) in the UI to protect your privacy while streaming or recording. 
</details>

<details>
<summary><b>Q: Where is my account data stored?</b></summary>
<br>
<b>A:</b> Application data (accounts, saved games, settings, VIP servers) is stored locally in <code>%LOCALAPPDATA%\Forked Account Manager\data\</code> (or in the directory configured via the <code>FRAM_APP_DIR</code> environment variable).
</details>

<details>
<summary><b>Q: How do I move my accounts to a new computer?</b></summary>
<br>
<b>A:</b> The easiest way is using the built-in <b>Backup & Import</b> feature:
<ol>
  <li>On your current PC, navigate to <b>Settings → Data</b> and click <b>Backup</b> under <i>Backup & Import</i> to save your <code>accounts.json</code> file.</li>
  <li>Transfer the exported JSON file to your new computer.</li>
  <li>Install FRAM on the new PC, go to <b>Settings → Data</b>, click <b>Import</b>, and select your backup file.</li>
</ol>
Alternatively, you can manually copy the application data folder at <code>%LOCALAPPDATA%\Forked Account Manager\data\</code> to the same path on your new PC.
<br><br>
<b>Important:</b> If you use <b>Hardware Encryption</b> and manually copy the folder, the data is tied to your original machine's hardware ID and cannot be unlocked on another PC. Using the <b>Backup & Import</b> feature (or switching to <b>Password Encryption</b>) ensures your accounts transfer smoothly.
</details>

<details>
<summary><b>Q: I forgot my Master Password. Can I recover my accounts?</b></summary>
<br>
<b>A:</b> No. AES-256-GCM encryption is cryptographically secure. There is no backdoor, developer key, or recovery method. If you lose your Master Password, password-encrypted data cannot be recovered.
</details>

<details>
<summary><b>Q: Why does Windows Defender or SmartScreen show a warning?</b></summary>
<br>
<b>A:</b> Windows SmartScreen often displays warnings for newly released, open-source executables that are not signed with a commercial certificate. This is a false positive. You can safely proceed by clicking <b>"More info" → "Run anyway"</b>. The complete source code is open-source and can be inspected or compiled from source.
</details>

---

## ⚠️ Disclaimer

This tool is created for educational and utility purposes only. Users are responsible for complying with Roblox's Terms of Service. Project maintainers and contributors are not responsible for any misuse or consequences resulting from the use of this tool.

---

## 🤝 Contributing & License

Contributions, bug reports, and feature suggestions are welcome! Feel free to open an issue or submit a Pull Request.

This project is licensed under the [GPL-3.0 License](LICENSE).