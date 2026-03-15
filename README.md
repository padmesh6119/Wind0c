# Wind0c — Windows System Optimizer

> **Built by [P. S. Padmesh](https://github.com/padmesh6119)**
> 🔗 [GitHub](https://github.com/padmesh6119) · [LinkedIn](https://www.linkedin.com/in/padmesh1101)

---

Wind0c is an intelligent, real-time Windows system optimizer built entirely in Python. It gives you complete visibility and control over everything running on your PC — telling you not just *what* is running, but *why it exists*, *whether you need it*, and *what it's costing your system*. One tool. Every performance lever. No bloat.

---

## Features

### ⚡ Dashboard
Live system overview with real-time CPU load, RAM usage, bloat process count, wasted RAM, uptime, and battery level. Top resource wasters displayed with one-click kill. Quick action buttons for the most common tasks.

### 🔬 Process Manager
Every running process listed with CPU %, RAM usage, thread count, safety rating, and impact score. Filter by category (Bloat / Telemetry / Caution / Unknown). Search by name. Kill individual processes or nuke all bloat at once.

### 🚀 Startup Manager
Scans Windows registry startup entries and estimates the real boot delay caused by each item. Shows total bloat-caused boot delay in milliseconds. Disable individual items or wipe all bloat startups in one click.

### ⚙️ Service Manager
Lists all non-essential Windows services with safety ratings. Identifies telemetry services (DiagTrack, WerSvc), Xbox junk, Fax, Maps, and more. Disable individually or all at once. Requires Administrator.

### 🗑️ App Manager / Uninstaller
Full list of installed applications with version, publisher, install size, and category. Filter by bloat, game, unknown, or system. Search by name. Double-click any app to launch its system uninstaller.

### ⚡ Boost Mode
Select any running application and click Boost. Wind0c sets it to HIGH CPU priority and simultaneously kills all safe-to-kill bloat and telemetry processes — freeing maximum CPU cycles and RAM for your chosen app. Best for gaming, video editing, compiling, and rendering. Includes a built-in power plan switcher (Balanced / Performance / Power Saver).

### 🔋 Battery Diagnostics
Live battery percentage with visual charge bar, time remaining, charging status, and health estimate. One-click HTML battery report generation saved to Desktop. Power plan management. Built-in battery care tips to extend long-term battery health.

### 🌐 Network Monitor
Hostname, local IP, all network interfaces with speed and status. Full live connections table showing every active TCP/UDP connection with the process name behind it. Sent/received bytes and error counts.

### 💽 Disk Health
Visual cards per drive showing used/free space with color-coded health bars. Read/write stats per drive. Detailed table with filesystem type, total/used/free GB, and health status.

### 🌡️ Temperature Monitor
CPU and GPU temperature readings with color-coded status cards (Normal → Warm → Hot → Critical). High temperature warnings. Requires compatible drivers or OpenHardwareMonitor on Windows.

### 🧹 Junk File Cleaner
Scans all Windows temp folders (`%TEMP%`, `%TMP%`, `C:\Windows\Temp`, `%LOCALAPPDATA%\Temp`). Shows total junk file count and size. One-click deletion — files in use are automatically skipped.

### 🖥️ System Information
Full system snapshot: OS version, hostname, processor, core count, CPU frequency, RAM, boot time, and uptime. Creator info and clickable GitHub/LinkedIn links.

### 📋 Action History
Every kill, boost, disable, and clean logged to a local SQLite database with timestamps. Full audit trail of everything Wind0c has done.

---

## Process Safety Ratings

| Rating | Meaning |
|---|---|
| `TELEMETRY` | Microsoft/OEM spy processes that send data to remote servers. Safe to kill. |
| `BLOAT` | Preinstalled junk with zero value for most users. Safe to kill. |
| `CAUTION` | Third-party apps you may or may not need right now. Kill with awareness. |
| `SYSTEM` | Windows core processes. Never kill. Permanently locked. |
| `UNKNOWN` | Not in the safety database. Research before acting. |

---

## Installation

### Requirements
- Windows 10 / 11
- Python 3.10 or higher
- psutil

### Setup

```bash
git clone https://github.com/padmesh6119/Wind0c.git
cd Wind0c
pip install -r requirements.txt
python run.py
```

> Right-click your terminal and select **Run as Administrator** for full kill, service disable, and priority boost capabilities.

---

## Building the Executable

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --uac-admin --name Wind0c --hidden-import psutil --hidden-import psutil._pswindows --collect-all psutil --add-data "core;core" --add-data "ui;ui" run.py
```

Output: `dist\Wind0c.exe`

The exe auto-requests Administrator privileges on launch via `--uac-admin`.

---

## Project Structure

```
Wind0c/
├── run.py                      Entry point
├── requirements.txt            Dependencies (psutil only)
├── README.md
├── core/
│   ├── process_engine.py       Process scanning, scoring, kill, boost, history DB
│   ├── diagnostics.py          Battery, network, temps, disk, sysinfo, temp cleaner
│   ├── startup_services.py     Startup items + Windows services
│   └── app_manager.py          Installed app scanner + uninstaller launcher
└── ui/
    └── main_window.py          Full tkinter dark UI — 13 tabs
```

---

## Safety Philosophy

Wind0c never takes action without your confirmation. Every kill, disable, and clean requires an explicit yes/no dialog. Protected system processes (lsass, csrss, winlogon, etc.) are permanently locked — Wind0c will not offer to touch them under any circumstance. All actions are logged to `winslim_history.db` and are reversible — processes restart on reboot, services can be re-enabled through Windows Services.

---

## Dependencies

| Package | Purpose |
|---|---|
| `psutil` | Process monitoring, system stats, battery, network, disk |
| `tkinter` | UI (built into Python — no install needed) |
| `sqlite3` | Action history logging (built into Python) |

No external UI frameworks. No bloat. Ironic for a de-bloating tool.

---

## Roadmap

- [ ] Community-maintained process safety database (GitHub-synced JSON)
- [ ] Before/after boot time measurement
- [ ] Scheduled auto-cleanup mode
- [ ] System tray icon with live RAM widget
- [ ] Per-process 24hr CPU/RAM sparkline charts
- [ ] Export report as PDF

---

## Author

**P. S. Padmesh**
🔗 [GitHub](https://github.com/padmesh6119) · [LinkedIn](https://www.linkedin.com/in/padmesh1101)

---

## License

MIT License — free to use, modify, and distribute with attribution.
