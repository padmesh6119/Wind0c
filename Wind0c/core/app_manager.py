"""
WinSlim - Application Uninstaller
Lists installed apps with size/usage data and can trigger uninstall.
"""

import sys
import subprocess
import os
from dataclasses import dataclass
from typing import Optional

if sys.platform == "win32":
    import winreg


@dataclass
class InstalledApp:
    name: str
    version: str
    publisher: str
    install_date: str
    install_location: str
    size_mb: float
    uninstall_cmd: str
    source: str          # "registry", "appx", "winget"
    category: str        # "bloat", "game", "utility", "system", "unknown"
    removable: bool


KNOWN_BLOAT_APPS = {
    "candy crush", "solitaire", "minecraft", "netflix",
    "disney+", "spotify", "tiktok", "facebook",
    "twitter", "instagram", "amazon", "booking.com",
    "mcafee", "norton", "avg", "avast",
    "adobe acrobat reader", "vlc media player",
    "zoom", "skype", "teams", "onedrive",
    "xbox", "cortana", "bing", "phone link",
}

SYSTEM_APPS = {
    "windows", "microsoft visual c++", "microsoft .net",
    "directx", "windows sdk", "intel driver",
    "amd driver", "nvidia driver", "realtek",
}


def _categorize(name: str) -> tuple[str, bool]:
    nl = name.lower()
    for s in SYSTEM_APPS:
        if s in nl:
            return "system", False
    for b in KNOWN_BLOAT_APPS:
        if b in nl:
            return "bloat", True
    if any(x in nl for x in ["game", "steam", "epic", "ubisoft", "ea ", "battle"]):
        return "game", True
    if any(x in nl for x in ["driver", "firmware", "bios", "chipset"]):
        return "driver", False
    return "unknown", True


def scan_installed_apps() -> list[InstalledApp]:
    """Scan Windows registry for installed applications."""
    if sys.platform != "win32":
        return _mock_apps()

    apps = []
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    sub_key_name = winreg.EnumKey(key, i)
                    sub_key = winreg.OpenKey(key, sub_key_name)

                    def get_val(k, name, default=""):
                        try:
                            return winreg.QueryValueEx(k, name)[0]
                        except Exception:
                            return default

                    name = get_val(sub_key, "DisplayName")
                    if not name or name.startswith("{"):
                        continue

                    uninstall = get_val(sub_key, "UninstallString")
                    if not uninstall:
                        continue

                    size_kb = get_val(sub_key, "EstimatedSize", 0)
                    category, removable = _categorize(name)

                    apps.append(InstalledApp(
                        name=name,
                        version=get_val(sub_key, "DisplayVersion", "—"),
                        publisher=get_val(sub_key, "Publisher", "Unknown"),
                        install_date=get_val(sub_key, "InstallDate", "—"),
                        install_location=get_val(sub_key, "InstallLocation", "—"),
                        size_mb=round(size_kb / 1024, 1) if size_kb else 0,
                        uninstall_cmd=uninstall,
                        source="registry",
                        category=category,
                        removable=removable,
                    ))
                except Exception:
                    continue
        except Exception:
            continue

    # Deduplicate by name
    seen = set()
    unique = []
    for app in apps:
        if app.name not in seen:
            seen.add(app.name)
            unique.append(app)

    return sorted(unique, key=lambda a: a.size_mb, reverse=True)


def uninstall_app(app: InstalledApp) -> dict:
    """Launch the uninstaller for an application."""
    if sys.platform != "win32":
        return {"ok": True, "msg": f"[Mock] Would uninstall: {app.name}"}

    if not app.removable:
        return {"ok": False, "msg": f"{app.name} is a system component and cannot be removed safely."}

    try:
        cmd = app.uninstall_cmd
        # Handle MSI uninstallers
        if "msiexec" in cmd.lower():
            if "/x" not in cmd.lower() and "/uninstall" not in cmd.lower():
                product_code = cmd.split()[-1] if cmd.split() else ""
                cmd = f"msiexec /x {product_code} /qb"
        subprocess.Popen(cmd, shell=True)
        return {"ok": True, "msg": f"Uninstaller launched for {app.name}. Follow the prompts."}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def get_winget_list() -> list[dict]:
    """Get apps via winget if available."""
    if sys.platform != "win32":
        return []
    try:
        result = subprocess.run(
            ["winget", "list", "--accept-source-agreements"],
            capture_output=True, text=True, timeout=30
        )
        apps = []
        lines = result.stdout.splitlines()
        for line in lines[2:]:
            parts = line.split()
            if len(parts) >= 2:
                apps.append({"name": parts[0], "id": parts[1] if len(parts) > 1 else ""})
        return apps
    except Exception:
        return []


def _mock_apps() -> list[InstalledApp]:
    mock_data = [
        ("Microsoft Teams", "23.2.0", "Microsoft Corporation", "20230901", 512),
        ("OneDrive", "23.196.0", "Microsoft Corporation", "20230101", 230),
        ("Candy Crush Saga", "1.234.0", "King", "20230601", 180),
        ("Spotify", "1.2.13", "Spotify AB", "20230801", 320),
        ("Discord", "1.0.9025", "Discord Inc.", "20230701", 280),
        ("Epic Games Launcher", "15.17.0", "Epic Games", "20230501", 890),
        ("Steam", "2.10.91.91", "Valve Corporation", "20230201", 1240),
        ("Zoom", "5.16.2", "Zoom Video Communications", "20230901", 210),
        ("Adobe Acrobat Reader DC", "23.006.20360", "Adobe Inc.", "20230401", 650),
        ("McAfee LiveSafe", "16.0.23", "McAfee LLC", "20220101", 420),
        ("Xbox", "2311.1001.8.0", "Microsoft Corporation", "20230101", 340),
        ("Skype", "8.104.0.3", "Skype Technologies", "20230301", 190),
        ("Norton 360", "22.23.2.13", "NortonLifeLock", "20220601", 510),
        ("Netflix", "6.97.1635.0", "Netflix Inc.", "20230101", 120),
        ("Google Chrome", "118.0.5993.88", "Google LLC", "20230901", 580),
        ("VLC media player", "3.0.18", "VideoLAN", "20230601", 95),
        ("WinRAR", "6.23.0", "win.rar GmbH", "20230401", 12),
        ("Notepad++", "8.5.8", "Notepad++ Team", "20230801", 8),
        ("7-Zip", "23.01", "Igor Pavlov", "20230601", 6),
        ("Python 3.11.5", "3.11.5150.0", "Python Software Foundation", "20230901", 95),
    ]
    result = []
    for name, ver, pub, date, size in mock_data:
        cat, removable = _categorize(name)
        result.append(InstalledApp(
            name=name, version=ver, publisher=pub,
            install_date=date, install_location="C:\\Program Files\\" + name,
            size_mb=size, uninstall_cmd=f"msiexec /x {{{name}}}",
            source="registry", category=cat, removable=removable
        ))
    return sorted(result, key=lambda a: a.size_mb, reverse=True)
