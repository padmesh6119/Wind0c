"""
WinSlim - Process Intelligence Engine v2
Fixed: no per-process DB calls, thread-safe, fast scan.
"""

import os
import sys
import time
import sqlite3
import psutil
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional


PROCESS_DB = {
    "diagtrack.exe":         ("telemetry", True,  "Microsoft spy telemetry. Sends usage data. Kill it.", 40),
    "compattelrunner.exe":   ("telemetry", True,  "Compatibility telemetry runner. Background spy.", 35),
    "dmwappushsvc.exe":      ("telemetry", True,  "WAP push routing. Telemetry relay.", 20),
    "wermgr.exe":            ("telemetry", True,  "Windows Error Reporting. Sends crash data to MS.", 25),
    "wsappx.exe":            ("telemetry", True,  "Windows Store background tasks.", 30),
    "cortana.exe":           ("telemetry", True,  "Cortana. RAM hog + telemetry. Kill.", 45),
    "searchapp.exe":         ("telemetry", True,  "Search/Cortana UI process.", 35),
    "onedrive.exe":          ("bloat", True,  "OneDrive sync. RAM drain. Kill if unused.", 55),
    "msteams.exe":           ("bloat", True,  "Microsoft Teams. Massive RAM hog.", 80),
    "teams.exe":             ("bloat", True,  "Microsoft Teams (new). Background drain.", 80),
    "yourphone.exe":         ("bloat", True,  "Phone Link. Unnecessary for most.", 30),
    "skypeapp.exe":          ("bloat", True,  "Skype (preinstalled). Nobody asked for this.", 35),
    "xboxgamebarsvc.exe":    ("bloat", True,  "Xbox Game Bar service. Kill if not gaming.", 30),
    "gamingservices.exe":    ("bloat", True,  "Xbox Gaming Services. Background drain.", 35),
    "xboxpcapplication.exe": ("bloat", True,  "Xbox app. Kill if not gaming.", 40),
    "wmpnscfg.exe":          ("bloat", True,  "Windows Media Player Network Sharing.", 20),
    "officeclicktorun.exe":  ("bloat", True,  "Office auto-update service. High CPU bursts.", 45),
    "msedgewebview2.exe":    ("bloat", True,  "Edge WebView2. Powers Teams/widgets bloat.", 60),
    "widgetsservice.exe":    ("bloat", True,  "Windows 11 Widgets. Pure RAM waste.", 40),
    "searchhost.exe":        ("bloat", True,  "Search indexing host. High disk use.", 35),
    "discord.exe":           ("caution", True,  "Discord. ~300MB RAM. Kill if not chatting.", 50),
    "spotify.exe":           ("caution", True,  "Spotify. Background audio drain.", 45),
    "steam.exe":             ("caution", True,  "Steam client. Launch when gaming.", 40),
    "epicgameslauncher.exe": ("caution", True,  "Epic Games Launcher. Slow + RAM heavy.", 50),
    "googledrivefs.exe":     ("caution", True,  "Google Drive sync. Disable if not syncing.", 40),
    "dropbox.exe":           ("caution", True,  "Dropbox sync daemon.", 40),
    "slack.exe":             ("caution", True,  "Slack. ~400MB RAM. Kill if not working.", 55),
    "zoom.exe":              ("caution", True,  "Zoom autostart. Kill when not in a call.", 45),
    "adobeupdateservice.exe":("caution", True,  "Adobe updater. Runs silently. Kill.", 30),
    "icloud.exe":            ("caution", True,  "iCloud for Windows. Kill if unused.", 45),
    "lsass.exe":             ("system", False, "Local Security Authority. Critical.", 0),
    "csrss.exe":             ("system", False, "Client Server Runtime. Critical.", 0),
    "winlogon.exe":          ("system", False, "Windows Logon. Critical.", 0),
    "wininit.exe":           ("system", False, "Windows Init. Critical.", 0),
    "services.exe":          ("system", False, "Services Control Manager. Critical.", 0),
    "smss.exe":              ("system", False, "Session Manager. Critical.", 0),
    "explorer.exe":          ("system", False, "Windows Shell. Restart, do not kill.", 0),
    "dwm.exe":               ("system", False, "Desktop Window Manager. Required.", 0),
    "audiodg.exe":           ("system", False, "Audio Device Graph. Required for sound.", 0),
    "svchost.exe":           ("system", False, "Service Host. Multiple instances normal.", 0),
    "ntoskrnl.exe":          ("system", False, "Windows Kernel.", 0),
    "system":                ("system", False, "Windows Kernel threads.", 0),
    "registry":              ("system", False, "Windows Registry process.", 0),
    "fontdrvhost.exe":       ("system", False, "Font Driver Host.", 0),
    "sihost.exe":            ("system", False, "Shell Infrastructure Host.", 0),
    "taskhostw.exe":         ("system", False, "Task Host Window.", 0),
    "runtimebroker.exe":     ("system", False, "Runtime Broker.", 0),
    "msmpeng.exe":           ("system", False, "Windows Defender Antimalware.", 0),
}


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    status: str
    exe_path: str
    username: str
    create_time: float
    threads: int
    handles: int
    safety_rating: str
    kill_safe: bool
    description: str
    base_priority: int
    impact_score: int
    running_since_str: str
    avg_cpu_24h: float = 0.0
    avg_mem_24h: float = 0.0


class HistoryDB:
    _lock = threading.Lock()

    def __init__(self, path="winslim_history.db"):
        self.path = path
        self._init()

    def _init(self):
        with sqlite3.connect(self.path) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS actions (
                name TEXT, pid INT, action TEXT, detail TEXT, ts TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS snapshots (
                cpu REAL, ram REAL, proc_count INT, ts TEXT)""")
            c.commit()

    def log_action(self, name, pid, action, detail=""):
        with self._lock:
            with sqlite3.connect(self.path) as c:
                c.execute("INSERT INTO actions VALUES (?,?,?,?,?)",
                          (name, pid, action, detail, datetime.now().isoformat()))
                c.commit()

    def log_snapshot(self, cpu, ram, count):
        with self._lock:
            with sqlite3.connect(self.path) as c:
                c.execute("INSERT INTO snapshots VALUES (?,?,?,?)",
                          (cpu, ram, count, datetime.now().isoformat()))
                c.commit()

    def get_actions(self, limit=50):
        with sqlite3.connect(self.path) as c:
            rows = c.execute(
                "SELECT name, pid, action, detail, ts FROM actions ORDER BY ts DESC LIMIT ?",
                (limit,)).fetchall()
        return rows


class ProcessEngine:
    def __init__(self):
        self.db = HistoryDB()
        self._cache: list[ProcessInfo] = []
        self._cache_time = 0

    def _lookup(self, name: str) -> tuple:
        key = name.lower()
        if key in PROCESS_DB:
            rating, kill_safe, desc, base_impact = PROCESS_DB[key]
            return rating, kill_safe, desc, base_impact
        return "unknown", False, "Unknown process. Research before acting.", 10

    def scan(self, force=False) -> list[ProcessInfo]:
        now = time.time()
        if not force and self._cache and (now - self._cache_time) < 5:
            return self._cache

        results = []
        for proc in psutil.process_iter([
            'pid', 'name', 'status', 'exe',
            'username', 'create_time', 'num_threads'
        ]):
            try:
                info = proc.info
                name = info['name'] or 'unknown'
                cpu = proc.cpu_percent(interval=0)

                try:
                    mem = proc.memory_info()
                    mem_mb = round(mem.rss / (1024 * 1024), 1)
                    mem_pct = round(proc.memory_percent(), 2)
                except Exception:
                    mem_mb, mem_pct = 0.0, 0.0

                handles = 0
                try:
                    handles = proc.num_handles() if sys.platform == 'win32' else proc.num_fds()
                except Exception:
                    pass

                rating, kill_safe, desc, base_impact = self._lookup(name)

                create_time = info.get('create_time', 0)
                try:
                    running_since = datetime.fromtimestamp(create_time).strftime('%d/%m %H:%M')
                except Exception:
                    running_since = "unknown"

                impact = min(100, int(
                    base_impact +
                    min(cpu * 1.5, 25) +
                    min(mem_mb / 20, 25) +
                    (15 if rating == 'telemetry' else 0) +
                    (10 if rating == 'bloat' else 0)
                ))

                try:
                    priority = proc.nice()
                except Exception:
                    priority = 0

                exe = info.get('exe') or ''
                username = info.get('username') or ''

                results.append(ProcessInfo(
                    pid=info['pid'],
                    name=name,
                    cpu_percent=round(cpu, 1),
                    memory_mb=mem_mb,
                    memory_percent=mem_pct,
                    status=info.get('status', 'unknown'),
                    exe_path=exe,
                    username=username,
                    create_time=create_time,
                    threads=info.get('num_threads', 0),
                    handles=handles,
                    safety_rating=rating,
                    kill_safe=kill_safe,
                    description=desc,
                    base_priority=priority,
                    impact_score=impact,
                    running_since_str=running_since,
                ))

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        results.sort(key=lambda p: p.impact_score, reverse=True)
        self._cache = results
        self._cache_time = time.time()

        try:
            cpu_total = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.db.log_snapshot(cpu_total, ram, len(results))
        except Exception:
            pass

        return results

    def kill(self, pid: int, name: str) -> dict:
        try:
            p = psutil.Process(pid)
            p.kill()  # SIGKILL not SIGTERM — actually kills it
            time.sleep(0.2)
            self.db.log_action(name, pid, "KILL", "User terminated")
            # Verify it's gone
            try:
                psutil.Process(pid)
                return {"ok": False, "msg": f"{name} is still running. Try running as Administrator."}
            except psutil.NoSuchProcess:
                # Remove from cache immediately
                self._cache = [p for p in self._cache if p.pid != pid]
                return {"ok": True, "msg": f"{name} successfully terminated."}
        except psutil.NoSuchProcess:
            self._cache = [p for p in self._cache if p.pid != pid]
            return {"ok": True, "msg": f"{name} is already gone."}
        except psutil.AccessDenied:
            return {"ok": False, "msg": f"Access denied killing {name}.\nRight-click terminal → Run as Administrator."}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def kill_all_bloat(self) -> dict:
        # Use existing cache — don't re-scan (causes double freeze)
        procs = self._cache if self._cache else self.scan()
        targets = [p for p in procs if p.kill_safe and p.safety_rating in ('bloat', 'telemetry')]
        killed, failed, ram_freed = 0, 0, 0.0
        for p in targets:
            try:
                proc = psutil.Process(p.pid)
                proc.kill()
                killed += 1
                ram_freed += p.memory_mb
                self.db.log_action(p.name, p.pid, "KILL", "Nuke all bloat")
            except psutil.NoSuchProcess:
                killed += 1  # already gone, count as success
            except psutil.AccessDenied:
                failed += 1
            except Exception:
                failed += 1
        # Purge killed from cache
        self._cache = [p for p in self._cache
                       if not (p.kill_safe and p.safety_rating in ('bloat', 'telemetry'))]
        self.db.log_action("SYSTEM", 0, "NUKE_BLOAT", f"Killed {killed}, freed {ram_freed:.0f}MB")
        return {"killed": killed, "failed": failed, "ram_freed_mb": round(ram_freed, 1)}

    def boost_process(self, pid: int, name: str) -> dict:
        try:
            p = psutil.Process(pid)
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.kernel32.SetPriorityClass(
                    p._handle, 0x00000080)  # HIGH_PRIORITY_CLASS
            else:
                p.nice(-10)
        except Exception:
            pass

        # Kill competing bloat from cache
        procs = self._cache if self._cache else self.scan()
        killed, ram_freed = 0, 0.0
        for proc in procs:
            if proc.pid != pid and proc.kill_safe and proc.safety_rating in ('bloat', 'telemetry'):
                try:
                    psutil.Process(proc.pid).kill()
                    killed += 1
                    ram_freed += proc.memory_mb
                except Exception:
                    pass

        self._cache = [p for p in self._cache
                       if p.pid == pid or not (p.kill_safe and p.safety_rating in ('bloat', 'telemetry'))]
        self.db.log_action(name, pid, "BOOST", f"Priority raised, killed {killed} competitors")
        return {
            "ok": True,
            "msg": f"{name} boosted to HIGH priority.\n{killed} competing processes killed.\n{ram_freed:.0f} MB freed.",
            "killed": killed,
            "ram_freed": ram_freed
        }

    def get_system_stats(self) -> dict:
        try:
            cpu_per_core = psutil.cpu_percent(percpu=True)
            cpu_freq = psutil.cpu_freq()
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
        except Exception as e:
            return {"error": str(e)}

        try:
            disk = psutil.disk_usage('C:\\' if sys.platform == 'win32' else '/')
        except Exception:
            disk = None
        try:
            net = psutil.net_io_counters()
        except Exception:
            net = None

        procs = self._cache or self.scan()
        bloat = [p for p in procs if p.kill_safe and p.safety_rating in ('bloat', 'telemetry')]
        telemetry = [p for p in procs if p.safety_rating == 'telemetry']

        return {
            "cpu_percent":      round(sum(cpu_per_core) / max(len(cpu_per_core), 1), 1),
            "cpu_per_core":     [round(c, 1) for c in cpu_per_core],
            "cpu_freq_mhz":     round(cpu_freq.current, 0) if cpu_freq else 0,
            "cpu_cores":        psutil.cpu_count(logical=False) or 1,
            "cpu_threads":      psutil.cpu_count(logical=True) or 1,
            "ram_used_gb":      round(mem.used / 1024**3, 2),
            "ram_total_gb":     round(mem.total / 1024**3, 2),
            "ram_percent":      mem.percent,
            "ram_available_gb": round(mem.available / 1024**3, 2),
            "swap_used_gb":     round(swap.used / 1024**3, 2),
            "swap_total_gb":    round(swap.total / 1024**3, 2),
            "disk_free_gb":     round(disk.free / 1024**3, 1) if disk else 0,
            "disk_total_gb":    round(disk.total / 1024**3, 1) if disk else 0,
            "disk_percent":     disk.percent if disk else 0,
            "net_sent_mb":      round(net.bytes_sent / 1024**2, 1) if net else 0,
            "net_recv_mb":      round(net.bytes_recv / 1024**2, 1) if net else 0,
            "total_processes":  len(procs),
            "bloat_count":      len(bloat),
            "telemetry_count":  len(telemetry),
            "wasted_ram_mb":    round(sum(p.memory_mb for p in bloat), 1),
            "top_bloat":        bloat[:8],
            "uptime_hours":     round((time.time() - psutil.boot_time()) / 3600, 1),
        }
