[![Version](https://img.shields.io/github/v/release/evanovar/RobloxAccountManager)](https://github.com/hackyue/RobloxAccountManager/releases/latest)
![License](https://img.shields.io/github/license/evanovar/RobloxAccountManager)
[!![Discord](https://img.shields.io/discord/1449551915464790170)](https://discord.gg/SpMTxg8YjJ)<br>
[![Download Fork](https://img.shields.io/badge/Download-280ab?style=for-the-badge)](https://github.com/hackyue/RobloxAccountManager/releases/latest/download/FRAM.exe)

# 🚀 Roblox Account Manager

A powerful tool for managing multiple Roblox accounts with secure cookie extraction and modern UI interface. <br>
Forked by hackyue · Contact: [Discord Server](https://discord.gg/SpMTxg8YjJ) <br>
⭐ If you like this project, please consider starring the repository! ⭐<br>

<img width="446" height="528" alt="image" src="https://i.ibb.co/c4T89HR/Screenshot-2025-12-02-224949.png" />
<img width="298" height="347" alt="image" src="https://i.ibb.co/1Y8WxtTt/Screenshot-2025-12-02-225144.png" />


## ✨ Features

### 🎨 Modern UI Interface
- **Pre Made Themes**: Sleek, modern interface easy on the eyes
- **Visual Account Management**: See all your accounts at a glance

### 🖥️ Interface Features
- **Account Management**: List of all your accounts with encryption status
- **Roblox Installer**: List 5 previous versions of roblox available for download
- **Auto Arrange Clients**: Automatically fits as many roblox clients onto one monitor
- **Roblox Version Selector**: Use roblox versions from Bloxstrap and Fishstrap
- **Multi Roblox Support**: Run multiple Roblox instances on the same device
- **Import Cookie Feature**: Add accounts quickly using `.ROBLOSECURITY` cookie
- **Game List**: Save up to 50 recently played games with Place IDs (configurable)
- **Private Server Support**: Save and launch private servers with [P] indicator
- **Persistent Settings**: Automatically saves Place IDs, Private Server codes, game list, and preferences

## 🛠️ Installation
### Method 1: Direct EXE (Recommended for Users)

**Quick & Easy - No Python Required!**

1. Go to [Releases](https://github.com/hackyue/RobloxAccountManager/releases)
2. Download `main.exe` from the latest release
3. Put it in a folder
4. Double-click to run - that's it! yippie

**Requirements:**
- **Google Chrome browser**
- **Windows**

> ⚠️ Windows Defender may flag the EXE as untrusted since it's not signed. Click "More info" → "Run anyway" to proceed.





### Method 2 (devs)

**Full source code access and customization**

**Requirements:**
- **Python 3.7+**
- **Google Chrome browser**
- **Windows**

1. **Clone the repository**
   ```bash
   git clone https://github.com/hackyue/RobloxAccountManager
   cd RobloxAccountManagerManager
   ```

2. **Install dependencies**
   ```bash
   py -m pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   py main.py
   ```
   
## 📋 Requirements

The following Python packages are required:
- `selenium` - Browser automation
- `requests` - HTTP requests for account validation and game info
- `webdriver-manager` - Automatic ChromeDriver management
- `pycryptodome` - Encryption and cookie handling
- `pywin32` - Windows API access for Multi Roblox feature

## 🔐 Encryption & Security

**1. Hardware Encryption (Not Portable)**
- ✅ Automatic encryption using your computer's unique hardware ID
- ✅ No password needed, completely automatic
- ⚠️ **Data ONLY works on THIS computer**
  
**2. Password Encryption (Portable, Recommended)**
- ✅ Encrypt with a password you create
- ✅ **Works on any computer** with the password
- ⚠️ **MUST remember your password** - there is NO recovery method!

**3. No Encryption (Not Recommended)**
- ✅ Store accounts without any encryption
- ✅ Easy to transfer and backup
- ⚠️ **NOT SECURE** - Anyone with access to files can see your data

## ⚠️ Disclaimer

This tool is for educational purposes only. Users are responsible for complying with Roblox's Terms of Service. The developers are not responsible for any consequences resulting from the use of this tool.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source and available under the [GPL 3.0 License](LICENSE).

## 📚 Frequently Asked Questions (FAQ)

### General Questions

**Q: Is this tool safe to use?**  
A: Yes, the tool runs entirely locally on your computer. No data is sent to external servers. However, you're responsible for following Roblox's Terms of Service.

**Q: Can I use this on Mac or Linux?**  
A: Currently, this tool is optimized for Windows only.

**Q: What does [P] mean in the game list?**  
A: [P] indicates that the game was saved with a private server link code. Clicking it will load both the Place ID and Private Server ID.

**Q: What is Multi Roblox?**  
A: Multi Roblox allows you to run multiple Roblox instances simultaneously on the same machine. Enable it in Settings, and you can launch multiple games at once.

**Q: Where are my data files stored?**  
A: All configuration and account data are stored in the `AccountManagerData` folder in the same directory as the program.

**Q: Why does my version folder get deleted after launch?**  
A: idfk

### Encryption Questions

**Q: I forgot my password! How do I recover my accounts?**  
A: Unfortunately, there is **NO password recovery method**. This is by design for security. Lost password = permanent data loss. Always remember your password or use hardware-based encryption instead.

**Q: Can I change from hardware encryption to password encryption?**  
A: Currently, there is no safe method. I will add this soon probably

**Q: Which encryption method should I choose?**  
A:
- **Hardware Encryption**: You only use one computer, want zero hassle, don't need cloud backups
- **Password Encryption**: You use multiple computers, want cloud backups, need portability
- **No Encrpytion**: You don't care about security

**Q: Can I access my password-encrypted accounts on another computer?**  
A: Yes! Simply copy the entire `AccountManagerData` folder to the new computer, install the app, and enter your password. This folder contains `saved_accounts.json` and `encryption_config.json`.

### Account Management Questions

**Q: How many accounts can I save?**  
A: There's no hard limit. You can save as many accounts as you need.

**Q: Why is my token invalid?**  
A: Roblox cookies can expire after long periods of inactivity or if you change your account password. Use the "Validate account" feature to check if an account is still valid.

**Q: Can I transfer accounts between different instances of the tool?**  
A: 
- **Hardware encryption**: No, tied to one machine only
- **Password encryption**: Yes, copy the entire `AccountManagerData` folder, then use same password
- **No encryption**: Yes, copy the entire `AccountManagerData` folder
