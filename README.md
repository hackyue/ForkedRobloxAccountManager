[![Version](https://img.shields.io/github/v/release/hackyue/ForkedRobloxAccountManager)](https://github.com/hackyue/ForkedRobloxAccountManager/releases/latest)
![License](https://img.shields.io/github/license/evanovar/RobloxAccountManager)
[!![Discord](https://img.shields.io/discord/1449551915464790170)](https://discord.gg/SpMTxg8YjJ)
[![Github All Releases](https://img.shields.io/github/downloads/hackyue/ForkedRobloxAccountManager/total.svg)]()<br>
[![Download Fork](https://img.shields.io/badge/Download-280ab?style=for-the-badge)](https://github.com/hackyue/ForkedRobloxAccountManager/releases/latest/download/FRAM.exe)


# 🚀 Roblox Account Manager

A powerful tool for managing multiple Roblox accounts with secure cookie extraction and modern UI interface. <br>
Forked by hackyue · Contact: [Discord Server](https://discord.gg/SpMTxg8YjJ) <br>
⭐ If you like this project, please consider starring the repository! ⭐<br>

<img width="446" height="528" alt="image" src="https://i.ibb.co/Z62D3LzQ/Screenshot-2026-01-14-224308.png" />
<img width="298" height="347" alt="image" src="https://i.ibb.co/1Y8WxtTt/Screenshot-2025-12-02-225144.png" />


## ✨ Features

### 🎨 Modern UI Interface
- **Pre-made Themes**: Sleek, modern interface that’s easy on the eyes
- **Visual Account Management**: See all your accounts at a glance

### 🖥️ Interface Features
- **Account Management**: View all accounts and their encryption status
- **Roblox Installer**: Browse up to 5 previous Roblox versions available for download
- **Auto Arrange Clients**: Automatically arrange as many Roblox clients as possible on one monitor
- **Roblox Version Selector**: Use Roblox versions from Bloxstrap and Fishstrap
- **Multi Roblox Support**: Run multiple Roblox instances on the same device
- **Import Cookie Feature**: Add accounts quickly using `.ROBLOSECURITY` cookie
- **Game List**: Save up to 50 recently played games with Place IDs (configurable)
- **Private Server Support**: Save and launch private servers with [P] indicator
- **Persistent Settings**: Automatically saves Place IDs, Private Server codes, game list, and preferences

### 🚀 Bootstrapper Support
###### Most bootstrappers force roblox updates, so **Roblox Version Selector** may not work.
- **Roblox**: https://www.roblox.com/home
- **Bloxstrap**: https://bloxstraplabs.com/
- **Fishstrap**: https://www.fishstrap.app/
- **Voidstrap**: https://voidstrapweb.netlify.app/ (Recommended, Made for VoidStrap)

## 🛠️ Installation
### Method 1: Direct EXE (Recommended for Users)

**Quick & Easy - No Python Required!**

1. Go to [Releases](https://github.com/hackyue/RobloxAccountManager/releases)
2. Download `fram.exe` from the latest release
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
   cd RobloxAccountManager
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
A: Yes, The app runs locally on your PC and only accesses the Roblox API and Github for updates.

**Q: What operating systems are supported?**  
A: Windows only.

**Q: Where is my data stored?**  
A: In an `AccountManagerData` folder next to the executable/script (same directory you run the app from).

**Q: What does `[P]` mean in the game list?**  
A: The entry includes a private server code. Selecting it loads both the Place ID and the private server code.

**Q: What is “Multi Roblox”?**  
A: It enables running multiple Roblox instances at the same time on one machine (Windows-only).

### Encryption Questions

**Q: I forgot my password. Can I recover it?**  
A: No. There is **no password recovery**. If you lose the password, password-encrypted data cannot be decrypted.

**Q: Which encryption mode should I use?**  
A:
- **Hardware encryption**: Convenient, but only works on the same PC
- **Password encryption**: Portable across PCs (you must remember the password)
- **No encryption**: Not recommended

**Q: How do I move my accounts to another PC?**  
A: Copy the whole `AccountManagerData` folder. If you used password encryption, you must enter the same password on the new PC.

### Account Management Questions

**Q: How many accounts can I save?**  
A: There’s no hard limit.

**Q: Why does an account show as invalid?**  
A: Cookies can expire or become invalid after password/security changes. Re-import the cookie or validate again.

**Q: Can I transfer accounts between installs?**  
A: Yes by copying `AccountManagerData`, with these limitations:
- **Hardware encryption**: not transferable (tied to one PC)
- **Password encryption**: transferable (requires the same password)
- **No encryption**: transferable (not recommended)
