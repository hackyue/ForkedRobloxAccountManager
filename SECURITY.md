<div align="center">

# 🛡️ Security Policy

<p align="center">
  <b>Forked Roblox Account Manager (FRAM)</b>
  <br>
  Committed to user privacy.
</p>

<p align="center">
  <a href="https://github.com/hackyue/ForkedRobloxAccountManager/releases/latest">
    <img src="https://img.shields.io/github/v/release/hackyue/ForkedRobloxAccountManager?style=for-the-badge&color=7289da&logo=github" alt="Latest Release">
  </a>
  <a href="https://discord.gg/SpMTxg8YjJ">
    <img src="https://img.shields.io/discord/1449551915464790170?style=for-the-badge&logo=discord&color=5865F2" alt="Discord Community">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-GPL_v3-f59e0b?style=for-the-badge" alt="License">
  </a>
</p>

</div>

---

## 📦 Supported Versions

Security updates, vulnerability patches, and cryptographic fixes are prioritized for active releases. We strongly advise all users to remain on the latest release build.

| Version Branch | Supported | Notes |
| :--- | :---: | :--- |
| **v3.0.x** (Current) | :white_check_mark: | Actively supported with bug fixes, security patches, and platform updates. |
| **v3.0.0-pr# / Beta** | :white_check_mark: | Actively maintained pre-releases; security issues are resolved in subsequent builds. |
| **v2.x.x** (Legacy) | :x: | End of Life (EOL). Unsupported; please upgrade to v3.0.x. |
| **< v2.0.0** | :x: | End of Life (EOL). Unsupported. |

---

## 🔒 Security Architecture & Guarantees

FRAM is designed with local-first security principles:

1. **Local-Only Execution:** The application and its backend run entirely on your local machine. No account credentials, `.ROBLOSECURITY` cookies, or passwords are ever transmitted to third-party servers.
2. **Direct Official Communication:** All network traffic involving your accounts is conducted exclusively between your computer and official Roblox endpoints (`*.roblox.com`, `*.rbxcdn.com`).
3. **AES-256-GCM Encryption:** Account data is encrypted locally using authenticated AES-256-GCM (via Master Password or device-locked Hardware Encryption). There are no backdoors, telemetry keys, or developer bypasses.
4. **Local Port & Origin Protection:** The backend service enforces tokenized authorization (`X-FRAM-Token`) and loopback CORS controls to prevent unauthorized browser access.

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability or sensitive flaw, please report it so we can resolve it.

> [!CAUTION]
> **Never open public GitHub issues for sensitive security vulnerabilities, zero-days, or exploit code.** Also, never post actual `.ROBLOSECURITY` cookies, passwords, or personal credentials in any communication.

### How to Report

Please report vulnerabilities through one of the following private channels:

1. **GitHub Private Security Advisory (Preferred):**
   - Navigate to the [Security Advisories](https://github.com/hackyue/ForkedRobloxAccountManager/security/advisories) tab of this repository.
   - Click **"Report a vulnerability"** to submit an advisory report privately.

2. **Private Direct Contact (Discord):**
   - Join our official community on [Discord](https://discord.gg/SpMTxg8YjJ) and contact **hackyue** directly for urgent security matters.

### What to Include in Your Report

To help us investigate and patch the issue quickly, please provide:
- A clear description of the vulnerability.
- Step-by-step reproduction steps or a minimal proof-of-concept (PoC).
- The affected FRAM version(s) and operating system (Windows 10/11 or macOS).
- Any potential impact or attack vector (e.g., local token extraction, encryption bypass).

---

## ⏱️ Response & Disclosure Process

* **Initial Response:** You can expect an initial acknowledgement within **48 hours** of submission.
* **Status Updates:** We will keep you informed of our progress as we triage, replicate, and develop a patch.
* **Resolution & Timeline:** Once a fix is verified, a patch will be released in an update as soon as possible (typically within 7–14 days depending on severity).
* **Credit & Attribution:** If you wish to be credited, we will happily acknowledge your responsible disclosure in the release notes and security advisory.

