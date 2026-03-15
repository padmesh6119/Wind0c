"""
WinSlim - Startup & Services Manager
"""

import sys
import subprocess
from dataclasses import dataclass

if sys.platform == "win32":
    import winreg


@dataclass
class StartupItem:
    name: str
    command: str
    location: str
    publisher: str
    delay_ms: int
    safety_rating: str
    kill_safe: bool
    recommendation: str
    enabled: bool
    impact: str   # "Critical" / "High" / "Medium" / "Low"


@dataclass
class ServiceInfo:
    name: str
    display_name: str
    status: str
    start_type: str
    safety_rating: str
    kill_safe: bool
    recommendation: str
    category: str


STARTUP_DB = {
    "onedrive":       ("bloat",     True,  "OneDrive. Massive startup drain. Disable.",          1800, "Critical"),
    "teams":          ("bloat",     True,  "Microsoft Teams autostart. ~2s boot delay.",          2000, "Critical"),
    "msteams":        ("bloat",     True,  "Microsoft Teams (new). Disable.",                     1800, "Critical"),
    "discord":        ("caution",   True,  "Discord autostart. Launch manually.",                  900, "High"),
    "spotify":        ("caution",   True,  "Spotify autostart. Launch when needed.",               700, "High"),
    "steam":          ("caution",   True,  "Steam autostart. Launch when gaming.",                1200, "High"),
    "epicgames":      ("caution",   True,  "Epic Games autostart. Launch when gaming.",           1100, "High"),
    "skype":          ("bloat",     True,  "Skype autostart. Nobody uses this.",                   800, "High"),
    "zoom":           ("caution",   True,  "Zoom autostart. Launch when needed.",                  700, "Medium"),
    "slack":          ("caution",   True,  "Slack autostart. Launch when working.",                900, "High"),
    "cortana":        ("telemetry", True,  "Cortana. Telemetry + RAM drain.",                      600, "High"),
    "yourphone":      ("bloat",     True,  "Phone Link. Unnecessary for most.",                    400, "Medium"),
    "gamingservices": ("bloat",     True,  "Xbox Gaming Services. Disable if not gaming.",         500, "Medium"),
    "xboxgamebar":    ("bloat",     True,  "Xbox Game Bar. Disable if not gaming.",                400, "Medium"),
    "dropbox":        ("caution",   True,  "Dropbox sync. Disable if not actively syncing.",       900, "Medium"),
    "googledrivefs":  ("caution",   True,  "Google Drive sync. Disable if not syncing.",           900, "Medium"),
    "icloud":         ("caution",   True,  "iCloud for Windows. Disable if unused.",               700, "Medium"),
    "adobearm":       ("caution",   True,  "Adobe Updater. Disable and update manually.",          350, "Low"),
    "nvidia":         ("caution",   False, "NVIDIA tray. Optional.",                               400, "Low"),
    "realtek":        ("caution",   False, "Realtek Audio. Disable if audio works fine.",          350, "Low"),
    "securityhealth": ("system",    False, "Windows Security. Required.",                          200, "Low"),
    "windowsdefender":("system",    False, "Windows Defender. Required for security.",             300, "Low"),
}

SERVICE_DB = {
    "DiagTrack":           ("telemetry", True,  "Connected User Experiences & Telemetry. Microsoft spy. Disable.", "telemetry"),
    "dmwappushservice":    ("telemetry", True,  "WAP Push routing. Telemetry relay. Disable.", "telemetry"),
    "WerSvc":              ("telemetry", True,  "Windows Error Reporting. Sends data to MS.", "telemetry"),
    "lfsvc":               ("telemetry", True,  "Geolocation Service. Tracks your location.", "privacy"),
    "WSearch":             ("caution",   True,  "Windows Search Indexer. High disk I/O. Disable if unused.", "performance"),
    "SysMain":             ("caution",   False, "Superfetch. Disable on SSDs to reduce writes.", "performance"),
    "TabletInputService":  ("bloat",     True,  "Touch Keyboard. Unnecessary on non-touchscreen PCs.", "bloat"),
    "Fax":                 ("bloat",     True,  "Fax Service. Nobody uses this.", "bloat"),
    "WMPNetworkSvc":       ("bloat",     True,  "Windows Media Player Network. Disable.", "bloat"),
    "XboxGipSvc":          ("bloat",     True,  "Xbox Accessory Management. Disable if no Xbox controller.", "bloat"),
    "XblAuthManager":      ("bloat",     True,  "Xbox Live Auth. Disable if not gaming.", "bloat"),
    "XblGameSave":         ("bloat",     True,  "Xbox Live Game Save. Disable if not gaming.", "bloat"),
    "XboxNetApiSvc":       ("bloat",     True,  "Xbox Live Networking. Disable if not gaming.", "bloat"),
    "MapsBroker":          ("bloat",     True,  "Downloaded Maps. Disable if not using Windows Maps.", "bloat"),
    "RetailDemo":          ("bloat",     True,  "Retail Demo Service. Only for store displays.", "bloat"),
    "PrintNotify":         ("bloat",     True,  "Printer Notifications. Disable if no printer.", "bloat"),
    "Spooler":             ("caution",   True,  "Print Spooler. Disable if no printer.", "performance"),
    "BITS":                ("caution",   False, "Background Intelligent Transfer. Used by Windows Update.", "system"),
    "wuauserv":            ("caution",   False, "Windows Update. Disable only if managing updates manually.", "system"),
    "EventLog":            ("system",    False, "Windows Event Log. Required.", "system"),
    "Themes":              ("system",    False, "Themes Service. Required for UI.", "system"),
    "AudioSrv":            ("system",    False, "Windows Audio. Required for sound.", "system"),
    "Winmgmt":             ("system",    False, "WMI. Critical — never disable.", "system"),
    "RpcSs":               ("system",    False, "Remote Procedure Call. Critical.", "system"),
}


def scan_startup() -> list[StartupItem]:
    if sys.platform != "win32":
        return _mock_startup()

    items = []
    reg_keys = [
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ]
    for hive, path in reg_keys:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            i = 0
            while True:
                try:
                    name, cmd, _ = winreg.EnumValue(key, i)
                    info = _lookup_startup(name, cmd)
                    items.append(StartupItem(
                        name=name, command=cmd, location=path,
                        publisher=_guess_publisher(cmd),
                        delay_ms=info[3], safety_rating=info[0],
                        kill_safe=info[1], recommendation=info[2],
                        enabled=True, impact=info[4]
                    ))
                    i += 1
                except OSError:
                    break
        except Exception:
            continue
    return sorted(items, key=lambda x: x.delay_ms, reverse=True)


def disable_startup(name: str, location: str) -> dict:
    if sys.platform != "win32":
        return {"ok": True, "msg": f"[Mock] {name} disabled from startup."}
    try:
        hive = winreg.HKEY_CURRENT_USER if "CURRENT_USER" in location else winreg.HKEY_LOCAL_MACHINE
        key = winreg.OpenKey(hive, location, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        return {"ok": True, "msg": f"{name} removed from startup."}
    except PermissionError:
        return {"ok": False, "msg": "Access denied. Run as Administrator."}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def scan_services() -> list[ServiceInfo]:
    if sys.platform != "win32":
        return _mock_services()
    svcs = []
    try:
        result = subprocess.run(["sc", "query", "type=", "all", "state=", "all"],
                                capture_output=True, text=True, timeout=20)
        current = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("SERVICE_NAME:"):
                current = {"name": line.split(":", 1)[1].strip()}
            elif line.startswith("DISPLAY_NAME:") and current:
                current["display"] = line.split(":", 1)[1].strip()
            elif "STATE" in line and current:
                current["status"] = "running" if "RUNNING" in line else "stopped"
            elif not line and current.get("name"):
                name = current["name"]
                data = SERVICE_DB.get(name, ("unknown", False, "Unknown service.", "unknown"))
                r, ks, rec, cat = data
                svcs.append(ServiceInfo(
                    name=name, display_name=current.get("display", name),
                    status=current.get("status", "unknown"), start_type="auto",
                    safety_rating=r, kill_safe=ks, recommendation=rec, category=cat
                ))
                current = {}
    except Exception:
        return _mock_services()
    return [s for s in svcs if s.safety_rating != "system"]


def disable_service(name: str) -> dict:
    if sys.platform != "win32":
        return {"ok": True, "msg": f"[Mock] {name} disabled."}
    try:
        r1 = subprocess.run(["sc", "config", name, "start=", "disabled"],
                            capture_output=True, text=True, timeout=10)
        if r1.returncode == 0:
            subprocess.run(["sc", "stop", name], capture_output=True, timeout=10)
            return {"ok": True, "msg": f"{name} disabled successfully."}
        return {"ok": False, "msg": "Failed. Try running as Administrator."}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def _lookup_startup(name, cmd):
    key = name.lower()
    cmd_l = cmd.lower()
    for k, data in STARTUP_DB.items():
        if k in key or k in cmd_l:
            return data
    return ("unknown", False, "Unknown startup item. Research before disabling.", 300, "Low")


def _guess_publisher(cmd):
    c = cmd.lower()
    if "microsoft" in c or "windows" in c: return "Microsoft"
    if "google" in c: return "Google"
    if "discord" in c: return "Discord"
    if "spotify" in c: return "Spotify"
    if "steam" in c: return "Valve"
    if "nvidia" in c: return "NVIDIA"
    return "Unknown"


def _mock_startup():
    mock = [
        ("Microsoft Teams", "C:\\...\\Teams.exe"),
        ("OneDrive", "C:\\...\\OneDrive.exe /background"),
        ("Discord", "C:\\...\\Discord\\Update.exe"),
        ("Spotify", "C:\\...\\Spotify.exe"),
        ("Steam", "C:\\...\\steam.exe -silent"),
        ("Zoom", "C:\\...\\Zoom.exe"),
        ("Epic Games Launcher", "C:\\...\\EpicGamesLauncher.exe"),
        ("Windows Security", "C:\\Windows\\System32\\SecurityHealthSystray.exe"),
        ("NVIDIA Backend", "C:\\...\\nvtray.exe"),
        ("Slack", "C:\\...\\slack.exe --startup"),
        ("Dropbox", "C:\\...\\Dropbox.exe /systemstartup"),
        ("iCloud", "C:\\...\\iCloudServices.exe"),
    ]
    items = []
    for name, cmd in mock:
        info = _lookup_startup(name, cmd)
        items.append(StartupItem(
            name=name, command=cmd, location="HKCU\\...\\Run",
            publisher=_guess_publisher(cmd),
            delay_ms=info[3], safety_rating=info[0],
            kill_safe=info[1], recommendation=info[2],
            enabled=True, impact=info[4]
        ))
    return sorted(items, key=lambda x: x.delay_ms, reverse=True)


def _mock_services():
    names = ["DiagTrack", "dmwappushservice", "WSearch", "SysMain", "Fax",
             "XboxGipSvc", "XblAuthManager", "XblGameSave", "XboxNetApiSvc",
             "MapsBroker", "WerSvc", "lfsvc", "RetailDemo", "WMPNetworkSvc",
             "TabletInputService", "PrintNotify"]
    result = []
    for name in names:
        data = SERVICE_DB.get(name, ("unknown", False, "Unknown.", "unknown"))
        r, ks, rec, cat = data
        result.append(ServiceInfo(
            name=name, display_name=name,
            status="running", start_type="auto",
            safety_rating=r, kill_safe=ks, recommendation=rec, category=cat
        ))
    return result
