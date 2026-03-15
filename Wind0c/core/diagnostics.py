"""
WinSlim - Extended System Diagnostics
Battery, Network, Temperature, Disk Health, System Info
Created by P. S. Padmesh
"""

import sys
import os
import subprocess
import platform
import time
import socket
import psutil
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


# ── Battery ────────────────────────────────────────────────────────────────
@dataclass
class BatteryInfo:
    percent: float
    plugged: bool
    time_left_min: int
    status: str          # "Charging", "Discharging", "Full", "Unknown"
    health_estimate: str # "Good", "Fair", "Poor", "Unknown"
    charge_color: str    # for UI


def get_battery() -> Optional[BatteryInfo]:
    try:
        b = psutil.sensors_battery()
        if b is None:
            return None
        plugged = b.power_plugged
        pct = round(b.percent, 1)
        secs = b.secsleft

        if plugged and pct >= 99:
            status = "Full"
        elif plugged:
            status = "Charging"
        else:
            status = "Discharging"

        time_left = 0
        if secs and secs != psutil.POWER_TIME_UNLIMITED and secs > 0:
            time_left = secs // 60

        if pct >= 80:
            health = "Good"
        elif pct >= 40:
            health = "Fair"
        else:
            health = "Poor"

        color = "#00E87A" if pct > 50 else "#FFB300" if pct > 20 else "#FF3355"

        return BatteryInfo(
            percent=pct,
            plugged=plugged,
            time_left_min=time_left,
            status=status,
            health_estimate=health,
            charge_color=color,
        )
    except Exception:
        return None


def generate_battery_report_html(out_path: str = "battery_report.html") -> dict:
    """Generate a detailed HTML battery report (Windows only)."""
    if sys.platform != "win32":
        return _mock_battery_report(out_path)
    try:
        result = subprocess.run(
            ["powercfg", "/batteryreport", f"/output", out_path],
            capture_output=True, text=True, timeout=30
        )
        if os.path.exists(out_path):
            return {"ok": True, "path": out_path,
                    "msg": f"Battery report saved to:\n{out_path}"}
        return {"ok": False, "msg": result.stderr or "Report not generated."}
    except FileNotFoundError:
        return {"ok": False, "msg": "powercfg not found. Run as Administrator."}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def _mock_battery_report(path):
    html = """<!DOCTYPE html><html><body style="background:#0A0C10;color:#E4EAF4;font-family:Consolas">
<h1 style="color:#00C8F0">WINSLIM BATTERY REPORT</h1>
<p>Created by P. S. Padmesh</p>
<p>Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
<h2 style="color:#FFB300">Note</h2>
<p>Full battery report requires Windows with powercfg utility.<br>
Run WinSlim as Administrator on Windows for complete battery diagnostics.</p>
</body></html>"""
    with open(path, "w") as f:
        f.write(html)
    return {"ok": True, "path": path, "msg": f"Mock report saved to:\n{path}"}


# ── Network ────────────────────────────────────────────────────────────────
@dataclass
class NetworkInfo:
    hostname: str
    local_ip: str
    interfaces: list
    connections_count: int
    bytes_sent_mb: float
    bytes_recv_mb: float
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int


def get_network_info() -> NetworkInfo:
    try:
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "Unknown"

        net = psutil.net_io_counters()
        conns = psutil.net_connections()

        interfaces = []
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    stats = psutil.net_if_stats().get(name)
                    interfaces.append({
                        "name": name,
                        "ip": addr.address,
                        "netmask": addr.netmask or "—",
                        "speed_mbps": stats.speed if stats else 0,
                        "is_up": stats.isup if stats else False,
                    })

        return NetworkInfo(
            hostname=hostname,
            local_ip=local_ip,
            interfaces=interfaces,
            connections_count=len(conns),
            bytes_sent_mb=round(net.bytes_sent / 1024**2, 1),
            bytes_recv_mb=round(net.bytes_recv / 1024**2, 1),
            packets_sent=net.packets_sent,
            packets_recv=net.packets_recv,
            errors_in=net.errin,
            errors_out=net.errout,
        )
    except Exception as e:
        return NetworkInfo("Unknown","Unknown",[],0,0,0,0,0,0,0)


def get_active_connections() -> list:
    """Return list of active network connections with process names."""
    conns = []
    try:
        for c in psutil.net_connections(kind="inet"):
            try:
                name = "System"
                if c.pid:
                    try:
                        name = psutil.Process(c.pid).name()
                    except Exception:
                        name = f"PID {c.pid}"
                laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "—"
                raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "—"
                conns.append({
                    "process": name,
                    "pid": c.pid or 0,
                    "local": laddr,
                    "remote": raddr,
                    "status": c.status,
                    "type": "TCP" if c.type == socket.SOCK_STREAM else "UDP",
                })
            except Exception:
                continue
    except Exception:
        pass
    return sorted(conns, key=lambda x: x["process"])


# ── Temperature ────────────────────────────────────────────────────────────
def get_temperatures() -> list:
    """Get CPU/GPU temperatures if available."""
    temps = []
    try:
        if hasattr(psutil, "sensors_temperatures"):
            raw = psutil.sensors_temperatures()
            for sensor_name, entries in raw.items():
                for entry in entries:
                    if entry.current > 0:
                        color = ("#00E87A" if entry.current < 60
                                 else "#FFB300" if entry.current < 80
                                 else "#FF3355")
                        temps.append({
                            "sensor": sensor_name,
                            "label": entry.label or sensor_name,
                            "current": round(entry.current, 1),
                            "high": round(entry.high, 1) if entry.high else 0,
                            "critical": round(entry.critical, 1) if entry.critical else 0,
                            "color": color,
                            "status": ("Critical" if entry.current > 85
                                       else "Hot" if entry.current > 70
                                       else "Warm" if entry.current > 55
                                       else "Normal"),
                        })
    except Exception:
        pass

    if not temps:
        # Windows fallback via WMI
        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    ["wmic", "temperature", "get", "currentreading"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.splitlines()[1:]:
                    line = line.strip()
                    if line.isdigit():
                        c = (int(line) - 2732) / 10
                        temps.append({
                            "sensor": "CPU",
                            "label": "CPU Package",
                            "current": round(c, 1),
                            "high": 90, "critical": 100,
                            "color": "#00E87A" if c < 60 else "#FFB300" if c < 80 else "#FF3355",
                            "status": "Normal" if c < 60 else "Warm",
                        })
            except Exception:
                pass

    return temps


# ── Disk Health ────────────────────────────────────────────────────────────
@dataclass
class DiskInfo:
    device: str
    mountpoint: str
    fstype: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float
    read_mb: float
    write_mb: float
    status: str
    color: str


def get_disk_info() -> list[DiskInfo]:
    disks = []
    io = {}
    try:
        io_counters = psutil.disk_io_counters(perdisk=True)
        io = {k: v for k, v in io_counters.items()} if io_counters else {}
    except Exception:
        pass

    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            pct = usage.percent
            dev_key = part.device.replace("\\\\.\\","").replace(":","")
            ioc = io.get(dev_key) or io.get(part.device, None)

            status = ("Critical" if pct > 90 else
                      "Warning"  if pct > 75 else
                      "Good")
            color  = ("#FF3355" if pct > 90 else
                      "#FFB300" if pct > 75 else
                      "#00E87A")

            disks.append(DiskInfo(
                device=part.device,
                mountpoint=part.mountpoint,
                fstype=part.fstype,
                total_gb=round(usage.total / 1024**3, 2),
                used_gb=round(usage.used / 1024**3, 2),
                free_gb=round(usage.free / 1024**3, 2),
                percent=pct,
                read_mb=round(ioc.read_bytes / 1024**2, 1) if ioc else 0,
                write_mb=round(ioc.write_bytes / 1024**2, 1) if ioc else 0,
                status=status,
                color=color,
            ))
        except Exception:
            continue
    return disks


# ── System Info ────────────────────────────────────────────────────────────
def get_full_system_info() -> dict:
    uname = platform.uname()
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time

    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    mins, secs  = divmod(rem, 60)

    mem = psutil.virtual_memory()
    cpu_freq = psutil.cpu_freq()

    users = []
    try:
        for u in psutil.users():
            users.append({
                "name": u.name,
                "terminal": u.terminal or "—",
                "started": datetime.fromtimestamp(u.started).strftime("%H:%M %d/%m"),
            })
    except Exception:
        pass

    return {
        "os":            f"{uname.system} {uname.release}",
        "os_version":    uname.version[:60] if uname.version else "—",
        "machine":       uname.machine,
        "processor":     uname.processor or platform.processor() or "Unknown",
        "hostname":      uname.node,
        "python":        platform.python_version(),
        "cpu_physical":  psutil.cpu_count(logical=False),
        "cpu_logical":   psutil.cpu_count(logical=True),
        "cpu_freq_mhz":  round(cpu_freq.current, 0) if cpu_freq else 0,
        "cpu_freq_max":  round(cpu_freq.max, 0) if cpu_freq else 0,
        "ram_total_gb":  round(mem.total / 1024**3, 2),
        "ram_used_gb":   round(mem.used / 1024**3, 2),
        "boot_time":     boot_time.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime":        f"{hours}h {mins}m {secs}s",
        "logged_users":  users,
        "winslim_ver":   "2.0",
        "created_by":    "P. S. Padmesh",
    }


# ── Temp File Cleaner ──────────────────────────────────────────────────────
def scan_temp_files() -> dict:
    """Scan Windows temp folders for junk files."""
    locations = []
    if sys.platform == "win32":
        locations = [
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
            r"C:\Windows\Temp",
            os.path.join(os.environ.get("LOCALAPPDATA",""), "Temp"),
        ]
    else:
        locations = ["/tmp"]

    total_size = 0
    total_files = 0
    file_list = []

    for loc in locations:
        if not loc or not os.path.exists(loc):
            continue
        try:
            for root, dirs, files in os.walk(loc):
                for fname in files:
                    try:
                        fpath = os.path.join(root, fname)
                        size = os.path.getsize(fpath)
                        total_size += size
                        total_files += 1
                        file_list.append({
                            "path": fpath,
                            "size_kb": round(size / 1024, 1),
                            "folder": loc,
                        })
                    except Exception:
                        continue
        except Exception:
            continue

    return {
        "total_files": total_files,
        "total_size_mb": round(total_size / 1024**2, 1),
        "total_size_gb": round(total_size / 1024**3, 2),
        "locations": locations,
        "files": file_list[:200],
    }


def clean_temp_files() -> dict:
    """Delete temp files. Returns count and size freed."""
    if sys.platform != "win32":
        return {"ok": True, "deleted": 0, "freed_mb": 0,
                "msg": "Temp cleaning only available on Windows."}

    locations = [
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        r"C:\Windows\Temp",
        os.path.join(os.environ.get("LOCALAPPDATA",""), "Temp"),
    ]

    deleted, failed, freed = 0, 0, 0.0
    for loc in locations:
        if not loc or not os.path.exists(loc):
            continue
        for root, dirs, files in os.walk(loc):
            for fname in files:
                try:
                    fpath = os.path.join(root, fname)
                    size = os.path.getsize(fpath)
                    os.remove(fpath)
                    deleted += 1
                    freed += size
                except Exception:
                    failed += 1

    return {
        "ok": True,
        "deleted": deleted,
        "failed": failed,
        "freed_mb": round(freed / 1024**2, 1),
        "msg": f"Deleted {deleted} temp files.\nFreed {freed/1024**2:.1f} MB.\n{failed} files skipped (in use).",
    }


# ── Power Plan ─────────────────────────────────────────────────────────────
def get_power_plan() -> str:
    if sys.platform != "win32":
        return "Unknown (Windows only)"
    try:
        r = subprocess.run(["powercfg", "/getactivescheme"],
                           capture_output=True, text=True, timeout=5)
        line = r.stdout.strip()
        if "Power Scheme GUID" in line:
            parts = line.split("(")
            if len(parts) > 1:
                return parts[-1].replace(")", "").strip()
        return line or "Unknown"
    except Exception:
        return "Unknown"


def set_power_plan(plan: str) -> dict:
    """Set Windows power plan: 'balanced', 'performance', 'saver'"""
    if sys.platform != "win32":
        return {"ok": False, "msg": "Windows only."}
    plans = {
        "balanced":    "381b4222-f694-41f0-9685-ff5bb260df2e",
        "performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
        "saver":       "a1841308-3541-4fab-bc81-f71556f20b4a",
    }
    guid = plans.get(plan.lower())
    if not guid:
        return {"ok": False, "msg": f"Unknown plan: {plan}"}
    try:
        subprocess.run(["powercfg", "/setactive", guid],
                       capture_output=True, timeout=5)
        return {"ok": True, "msg": f"Power plan set to: {plan.title()}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}
