"""
Wind0c - System Optimizer v3
Created by P. S. Padmesh
"""

import sys, os, threading, tkinter as tk, webbrowser, queue as _q
from tkinter import ttk, messagebox
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.process_engine import ProcessEngine
from core.startup_services import scan_startup, disable_startup, scan_services, disable_service
from core.app_manager import scan_installed_apps, uninstall_app
from core.diagnostics import (
    get_battery, generate_battery_report_html,
    get_network_info, get_active_connections,
    get_temperatures, get_disk_info,
    get_full_system_info, scan_temp_files, clean_temp_files,
    get_power_plan, set_power_plan,
)

# ── Design Tokens ────────────────────────────────────────────────────────────
BG       = "#070A0E"
PANEL    = "#0D1117"
CARD     = "#111720"
CARD2    = "#161E2A"
BORDER   = "#1E2D40"
BORDER2  = "#243346"
ACCENT   = "#0EA5E9"   # sky blue
GREEN    = "#10B981"   # emerald
RED      = "#EF4444"   # red
AMBER    = "#F59E0B"   # amber
PINK     = "#EC4899"   # pink
CYAN     = "#06B6D4"   # cyan
PURPLE   = "#8B5CF6"   # purple
TEXT     = "#F1F5F9"   # near white
TEXT2    = "#94A3B8"   # muted
TEXT3    = "#475569"   # dimmer
SEL      = "#1D4ED8"   # selection blue

RATING_C = {
    "telemetry": PINK,
    "bloat":     RED,
    "caution":   AMBER,
    "system":    GREEN,
    "unknown":   TEXT3,
}

# ── Typography ───────────────────────────────────────────────────────────────
# Generous sizes — nothing cramped
F_TINY  = ("Consolas", 9)
F_SM    = ("Consolas", 10)
F_BODY  = ("Consolas", 11)
F_BOLD  = ("Consolas", 11, "bold")
F_HEAD  = ("Consolas", 15, "bold")
F_TITLE = ("Consolas", 22, "bold")
F_HUGE  = ("Consolas", 32, "bold")
F_MONO  = ("Consolas", 10)
F_MONO_B= ("Consolas", 10, "bold")
F_MONO_L= ("Consolas", 12)

CREATOR = "P. S. Padmesh"
VERSION = "3.0"
APP     = "Wind0c"

NAV = [
    ("DASHBOARD", "▣"), ("PROCESSES", "▤"), ("STARTUP",  "▦"),
    ("SERVICES",  "▥"), ("APPS",      "▣"), ("BOOST",    "▤"),
    ("BATTERY",   "▦"), ("NETWORK",   "▥"), ("DISK",     "▣"),
    ("TEMPS",     "▤"), ("CLEANER",   "▦"), ("SYSINFO",  "▥"),
    ("HISTORY",   "▣"),
]

# ── Thread-safe callback queue ───────────────────────────────────────────────
_cbq = _q.Queue()

def _bg(fn, *args, done=None):
    def _r():
        res = fn(*args)
        if done:
            _cbq.put(lambda: done(res))
    threading.Thread(target=_r, daemon=True).start()

def _drain(root):
    try:
        while True: _cbq.get_nowait()()
    except _q.Empty: pass
    root.after(50, lambda: _drain(root))

# ── Style setup ──────────────────────────────────────────────────────────────
def apply_styles():
    s = ttk.Style()
    s.theme_use("clam")

    # Treeview — roomy rows, clear heading contrast
    s.configure("W.Treeview",
        background=CARD, foreground=TEXT,
        fieldbackground=CARD,
        rowheight=32,           # tall enough for 11pt text
        borderwidth=0,
        font=F_BODY)
    s.configure("W.Treeview.Heading",
        background=CARD2, foreground=TEXT2,
        font=F_BOLD,
        borderwidth=0, relief="flat",
        padding=(8, 6))
    s.map("W.Treeview",
        background=[("selected", SEL)],
        foreground=[("selected", "#FFFFFF")])

    # Scrollbar
    s.configure("W.Vertical.TScrollbar",
        background=CARD2, troughcolor=CARD,
        borderwidth=0, arrowsize=14,
        gripcount=0)

# ── Reusable UI primitives ───────────────────────────────────────────────────
def mktree(parent, cols, widths, height=16):
    """Scrollable treeview with proper column sizing."""
    wrap = tk.Frame(parent, bg=BORDER, bd=1)
    tree = ttk.Treeview(wrap, columns=cols, show="headings",
                        style="W.Treeview", height=height)
    LEFT_COLS = ("Name","Application","App Name","Service",
                 "Display Name","Process","Interface","Path",
                 "Sensor","Startup Item","App")
    for col, w in zip(cols, widths):
        tree.heading(col, text=col)
        tree.column(col, width=w, minwidth=w,
                    anchor="w" if col in LEFT_COLS else "center",
                    stretch=col == cols[-1])
    vsb = ttk.Scrollbar(wrap, orient="vertical",
                        command=tree.yview, style="W.Vertical.TScrollbar")
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
    vsb.pack(side="right", fill="y", pady=1)
    for r, c in RATING_C.items():
        tree.tag_configure(r, foreground=c)
    tree.tag_configure("good", foreground=GREEN)
    tree.tag_configure("warn", foreground=AMBER)
    tree.tag_configure("crit", foreground=RED)
    tree.tag_configure("info", foreground=ACCENT)
    return wrap, tree


def mkbtn(parent, text, cmd, color=ACCENT, width=None,
          side="left", padx=6, pady=0, height=36):
    """Flat button with generous padding — text never gets clipped."""
    kw = dict(
        text=text, command=cmd,
        bg=CARD2, fg=color,
        activebackground=CARD, activeforeground=color,
        font=F_BOLD, relief="flat", bd=0, cursor="hand2",
        pady=0,
    )
    if width:
        kw["width"] = width
    b = tk.Button(parent, **kw)
    # Use ipadx/ipady so text has breathing room regardless of width
    b.pack(side=side, padx=padx, pady=pady, ipady=8, ipadx=10)
    return b


def divider(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=0, pady=0)


def section_label(parent, text):
    f = tk.Frame(parent, bg=BG)
    f.pack(fill="x", padx=20, pady=(14, 5))
    tk.Label(f, text=text.upper(), fg=ACCENT,
             font=("Consolas", 9, "bold"), bg=BG).pack(side="left")
    tk.Frame(f, bg=BORDER2, height=1).pack(
        side="left", fill="x", expand=True, padx=10, pady=5)


def page_header(parent, title, subtitle=None):
    f = tk.Frame(parent, bg=BG)
    f.pack(fill="x", padx=20, pady=(20, 6))
    tk.Label(f, text=title, fg=TEXT, font=F_HEAD, bg=BG).pack(side="left")
    if subtitle:
        tk.Label(f, text=subtitle, fg=TEXT3, font=F_SM, bg=BG).pack(
            side="left", padx=12, pady=3)
    return f


class StatCard(tk.Frame):
    """Metric tile — label + big value, properly sized."""
    def __init__(self, parent, label, color=ACCENT, unit=""):
        super().__init__(parent, bg=CARD,
                         highlightbackground=BORDER,
                         highlightthickness=1)
        self._color = color
        tk.Label(self, text=label, fg=TEXT2,
                 font=F_SM, bg=CARD).pack(anchor="w", padx=14, pady=(12, 0))
        val_row = tk.Frame(self, bg=CARD)
        val_row.pack(anchor="w", padx=14, pady=(2, 12))
        self._v = tk.StringVar(value="—")
        self._lbl = tk.Label(val_row, textvariable=self._v,
                              fg=color, font=("Consolas", 20, "bold"), bg=CARD)
        self._lbl.pack(side="left")
        if unit:
            tk.Label(val_row, text=f" {unit}", fg=TEXT2,
                     font=F_SM, bg=CARD).pack(side="left", pady=4)

    def set(self, v, c=None):
        self._v.set(str(v))
        if c: self._lbl.configure(fg=c)


class InfoRow(tk.Frame):
    """Label: Value row for system info panels."""
    def __init__(self, parent, label, value="—", val_color=TEXT):
        super().__init__(parent, bg=CARD)
        self.pack(fill="x", padx=0, pady=0)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        inner = tk.Frame(self, bg=CARD)
        inner.pack(fill="x", padx=16, pady=8)
        tk.Label(inner, text=label, fg=TEXT2,
                 font=F_SM, bg=CARD, width=24, anchor="w").pack(side="left")
        self._v = tk.StringVar(value=str(value))
        tk.Label(inner, textvariable=self._v,
                 fg=val_color, font=F_BOLD, bg=CARD, anchor="w").pack(side="left")

    def set(self, v):
        self._v.set(str(v))


# ────────────────────────────────────────────────────────────────────────────
class Wind0c(tk.Tk):
    def __init__(self):
        super().__init__()
        self.engine = ProcessEngine()
        _drain(self)

        self.title(f"{APP}  —  System Optimizer  |  by {CREATOR}")
        self.geometry("1200x780")
        self.minsize(1000, 640)
        self.configure(bg=BG)
        try: self.state("zoomed")
        except: pass

        apply_styles()

        self._procs  = []; self._apps   = []
        self._starts = []; self._svcs   = []
        self._tab    = None
        self._pages  = {}; self._navs   = {}
        self._busy   = False

        self._build_shell()
        self._switch("DASHBOARD")
        self.after(800, self._poll)

    # ── Shell ────────────────────────────────────────────────────────────────
    def _build_shell(self):
        # ── Sidebar ──────────────────────────────────────────────────────
        sb = tk.Frame(self, bg=PANEL, width=210)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        # Logo
        logo = tk.Frame(sb, bg=PANEL)
        logo.pack(fill="x", padx=0, pady=0)
        logo_inner = tk.Frame(logo, bg=CARD2)
        logo_inner.pack(fill="x", padx=12, pady=(16, 8))
        tk.Label(logo_inner, text=APP, fg=ACCENT,
                 font=("Consolas", 19, "bold"), bg=CARD2).pack(
                     anchor="w", padx=14, pady=(12, 0))
        tk.Label(logo_inner, text=f"System Optimizer  v{VERSION}",
                 fg=TEXT2, font=F_SM, bg=CARD2).pack(anchor="w", padx=14)
        tk.Label(logo_inner, text=f"by  {CREATOR}",
                 fg=CYAN, font=("Consolas", 10, "bold"), bg=CARD2).pack(
                     anchor="w", padx=14, pady=(0, 12))

        divider(sb)

        # Nav
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(side="right", fill="both", expand=True)

        for name, icon in NAV:
            b = tk.Button(sb,
                text=f"   {icon}   {name}",
                anchor="w",
                bg=PANEL, fg=TEXT2,
                activebackground=CARD2,
                activeforeground=TEXT,
                font=("Consolas", 10, "bold"),
                relief="flat", bd=0, cursor="hand2",
                pady=10,
                command=lambda n=name: self._switch(n))
            b.pack(fill="x", padx=8, pady=1)
            self._navs[name] = b

        # Footer
        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=8, pady=8, side="bottom")
        tk.Label(sb,
            text="⚡  Run as Administrator\nfor full capabilities",
            fg=TEXT3, font=F_TINY, bg=PANEL,
            justify="center").pack(side="bottom", pady=(0,8))

        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=8, pady=0, side="bottom")

        tk.Button(sb,
            text="  ⌘  LinkedIn",
            command=lambda: webbrowser.open("https://www.linkedin.com/in/padmesh1101"),
            bg=PANEL, fg=CYAN,
            activebackground=CARD2, activeforeground=CYAN,
            font=("Consolas", 9, "bold"),
            relief="flat", bd=0, cursor="hand2", anchor="w", pady=6
        ).pack(fill="x", padx=8, side="bottom", ipady=2)

        tk.Button(sb,
            text="  ⌥  GitHub",
            command=lambda: webbrowser.open("https://github.com/padmesh6119"),
            bg=PANEL, fg=ACCENT,
            activebackground=CARD2, activeforeground=ACCENT,
            font=("Consolas", 9, "bold"),
            relief="flat", bd=0, cursor="hand2", anchor="w", pady=6
        ).pack(fill="x", padx=8, side="bottom", ipady=2)

        tk.Label(sb, text="  Links",
            fg=TEXT3, font=("Consolas", 8), bg=PANEL, anchor="w"
        ).pack(fill="x", padx=10, side="bottom", pady=(8,2))

        # Build pages
        self._pages = {
            "DASHBOARD": self._pg_dash(),
            "PROCESSES": self._pg_procs(),
            "STARTUP":   self._pg_startup(),
            "SERVICES":  self._pg_svcs(),
            "APPS":      self._pg_apps(),
            "BOOST":     self._pg_boost(),
            "BATTERY":   self._pg_battery(),
            "NETWORK":   self._pg_network(),
            "DISK":      self._pg_disk(),
            "TEMPS":     self._pg_temps(),
            "CLEANER":   self._pg_cleaner(),
            "SYSINFO":   self._pg_sysinfo(),
            "HISTORY":   self._pg_hist(),
        }

    def _switch(self, name):
        if self._tab:
            self._pages[self._tab].pack_forget()
            self._navs[self._tab].configure(bg=PANEL, fg=TEXT2)
        self._tab = name
        self._pages[name].pack(fill="both", expand=True)
        self._navs[name].configure(bg=CARD2, fg=ACCENT)

    def _setstatus(self, msg, col=TEXT2):
        try: self._status_lbl.configure(text=msg, fg=col)
        except: pass

    # ── Dashboard ────────────────────────────────────────────────────────────
    def _pg_dash(self):
        p = tk.Frame(self._content, bg=BG)

        # Header row
        hrow = tk.Frame(p, bg=BG)
        hrow.pack(fill="x", padx=20, pady=(20, 6))
        tk.Label(hrow, text=f"{APP}", fg=ACCENT,
                 font=("Consolas", 18, "bold"), bg=BG).pack(side="left")
        tk.Label(hrow, text="System Overview", fg=TEXT2,
                 font=F_BODY, bg=BG).pack(side="left", padx=12, pady=3)
        self._status_lbl = tk.Label(hrow, text="Initializing...",
                                     fg=TEXT3, font=F_SM, bg=BG)
        self._status_lbl.pack(side="right")

        divider(p)

        # Stat cards
        cards_row = tk.Frame(p, bg=BG)
        cards_row.pack(fill="x", padx=20, pady=14)
        cards_row.columnconfigure((0,1,2,3,4,5), weight=1)
        self._tiles = {
            "cpu":    StatCard(cards_row, "CPU LOAD",     ACCENT),
            "ram":    StatCard(cards_row, "RAM USED",     AMBER),
            "bloat":  StatCard(cards_row, "BLOAT PROCS",  RED),
            "waste":  StatCard(cards_row, "WASTED RAM",   PINK),
            "uptime": StatCard(cards_row, "UPTIME",       GREEN),
            "bat":    StatCard(cards_row, "BATTERY",      CYAN),
        }
        for i, t in enumerate(self._tiles.values()):
            t.grid(row=0, column=i, padx=5, sticky="nsew", ipady=4)

        divider(p)

        # Action bar
        section_label(p, "Quick Actions")
        ab = tk.Frame(p, bg=BG)
        ab.pack(fill="x", padx=20, pady=(0, 8))
        mkbtn(ab, "💀  Nuke All Bloat",   self._nuke,                    RED,    padx=4)
        mkbtn(ab, "⚡  Boost Mode",       lambda: self._switch("BOOST"), GREEN,  padx=4)
        mkbtn(ab, "🔃  Deep Scan",        self._deep_scan,               ACCENT, padx=4)
        mkbtn(ab, "🧹  Clean Temp Files", self._quick_clean,             CYAN,   padx=4)
        mkbtn(ab, "🗑   Uninstall Apps",  lambda: self._switch("APPS"),  AMBER,  padx=4)
        mkbtn(ab, "📋  Full Report",      self._report,                  TEXT2,  padx=4)

        divider(p)
        section_label(p, "Top Resource Wasters")

        wf, self._dtree = mktree(p,
            ("Name", "CPU %", "RAM MB", "Rating", "Impact", "Action"),
            (240, 80, 100, 120, 90, 90))
        wf.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self._dtree.bind("<Double-1>", self._dash_kill)
        return p

    def _dash_kill(self, _=None):
        sel = self._dtree.selection()
        if not sel: return
        name = self._dtree.item(sel[0], "values")[0]
        proc = next((p for p in self._procs if p.name == name), None)
        if not proc: return
        if not proc.kill_safe:
            messagebox.showinfo("Protected", f"{proc.name} is a protected system process.")
            return
        if messagebox.askyesno("Kill Process",
                f"Kill  {proc.name} ?\n\n{proc.description}"):
            self._setstatus(f"Killing {proc.name}…", AMBER)
            _bg(self.engine.kill, proc.pid, proc.name,
                done=lambda r: (messagebox.showinfo("Result", r["msg"]),
                                self._setstatus("Done.", GREEN),
                                self._deep_scan()))

    # ── Processes ────────────────────────────────────────────────────────────
    def _pg_procs(self):
        p = tk.Frame(self._content, bg=BG)
        hrow = page_header(p, "Process Manager")
        divider(p)

        # Controls
        ctrl = tk.Frame(p, bg=BG)
        ctrl.pack(fill="x", padx=20, pady=10)

        tk.Label(ctrl, text="Filter:", fg=TEXT2, font=F_SM, bg=BG).pack(side="left", padx=(0,4))
        self._pf = tk.StringVar(value="ALL")
        om = tk.OptionMenu(ctrl, self._pf, "ALL","BLOAT","TELEMETRY","CAUTION","UNKNOWN",
                           command=lambda _: self._repop_procs())
        om.configure(bg=CARD2, fg=TEXT, activebackground=CARD,
                     font=F_BODY, relief="flat", bd=0,
                     padx=10, pady=6, indicatoron=True)
        om["menu"].configure(bg=CARD2, fg=TEXT, font=F_BODY,
                              activebackground=SEL, activeforeground=TEXT)
        om.pack(side="left", padx=(0,12))

        tk.Label(ctrl, text="Search:", fg=TEXT2, font=F_SM, bg=BG).pack(side="left", padx=(0,4))
        self._ps = tk.StringVar()
        self._ps.trace_add("write", lambda *_: self._repop_procs())
        ent = tk.Entry(ctrl, textvariable=self._ps,
                       bg=CARD2, fg=TEXT, insertbackground=TEXT,
                       font=F_BODY, relief="flat", bd=0)
        ent.pack(side="left", padx=(0,12), ipady=6, ipadx=10)

        mkbtn(ctrl, "⟳  Refresh", self._scan_procs, ACCENT, padx=4)

        self._pinfo = tk.Label(p, text="", fg=TEXT3, font=F_SM, bg=BG, anchor="w")
        self._pinfo.pack(fill="x", padx=20, pady=(0, 4))

        pf, self._ptree = mktree(p,
            ("Name","PID","CPU %","RAM MB","RAM %","Threads","Rating","Impact","Running Since"),
            (185, 65, 70, 88, 70, 68, 110, 75, 110))
        pf.pack(fill="both", expand=True, padx=20)

        bot = tk.Frame(p, bg=BG)
        bot.pack(fill="x", padx=20, pady=10)
        tk.Label(bot, text="Double-click a process to kill it",
                 fg=TEXT3, font=F_SM, bg=BG).pack(side="left")
        mkbtn(bot, "Kill All Bloat",  self._nuke,     RED,   side="right", padx=4)
        mkbtn(bot, "Kill Selected",   self._kill_sel, AMBER, side="right", padx=4)
        self._ptree.bind("<Double-1>", lambda e: self._kill_sel())
        return p

    def _scan_procs(self):
        self._setstatus("Scanning processes…", AMBER)
        def _done(procs):
            self._procs = procs
            self._repop_procs()
            self._setstatus(f"Scan complete  {datetime.now().strftime('%H:%M:%S')}", TEXT2)
        _bg(self.engine.scan, True, done=_done)

    def _repop_procs(self):
        self._ptree.delete(*self._ptree.get_children())
        filt = self._pf.get().lower()
        q = self._ps.get().lower()
        n = 0
        for p in self._procs:
            if filt != "all" and p.safety_rating != filt: continue
            if q and q not in p.name.lower(): continue
            self._ptree.insert("", "end",
                values=(p.name, p.pid, f"{p.cpu_percent}%",
                        f"{p.memory_mb} MB", f"{p.memory_percent}%",
                        p.threads, p.safety_rating.upper(),
                        p.impact_score, p.running_since_str),
                tags=(p.safety_rating,), iid=str(p.pid))
            n += 1
        self._pinfo.configure(text=f"  {n} processes shown  ·  {len(self._procs)} total running")

    def _kill_sel(self):
        sel = self._ptree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a process first."); return
        pid = int(sel[0])
        proc = next((p for p in self._procs if p.pid == pid), None)
        if not proc: return
        if not proc.kill_safe:
            messagebox.showinfo("Protected Process",
                f"{proc.name}  is a protected system process.\n\n{proc.description}")
            return
        if messagebox.askyesno("Kill Process",
                f"Kill  {proc.name}  (PID {pid}) ?\n\n{proc.description}"):
            self._setstatus(f"Killing {proc.name}…", AMBER)
            iid = sel[0]
            def _done(r):
                if r["ok"]:
                    try: self._ptree.delete(iid)
                    except: pass
                self._setstatus("Done.", GREEN if r["ok"] else RED)
                messagebox.showinfo("Result", r["msg"])
            _bg(self.engine.kill, pid, proc.name, done=_done)

    # ── Startup ──────────────────────────────────────────────────────────────
    def _pg_startup(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "Startup Manager")
        mkbtn(h, "⟳  Scan", self._scan_startup, ACCENT, side="right")
        divider(p)
        self._stbanner = tk.Label(p, text="", fg=AMBER, font=F_BOLD, bg=BG, anchor="w")
        self._stbanner.pack(fill="x", padx=20, pady=(8, 4))
        sf, self._sttree = mktree(p,
            ("Startup Item","Publisher","Boot Delay","Impact","Rating","Recommendation"),
            (195, 145, 110, 88, 110, 0))
        sf.pack(fill="both", expand=True, padx=20)
        bot = tk.Frame(p, bg=BG); bot.pack(fill="x", padx=20, pady=10)
        tk.Label(bot, text="Double-click an item to disable it",
                 fg=TEXT3, font=F_SM, bg=BG).pack(side="left")
        mkbtn(bot, "Disable All Bloat Startups", self._dis_all_starts, RED, side="right")
        self._sttree.bind("<Double-1>", self._dis_start_sel)
        self._scan_startup()
        return p

    def _scan_startup(self):
        self._setstatus("Scanning startup items…", AMBER)
        def _done(items):
            self._starts = items
            self._repop_startup()
            self._setstatus("Done.", TEXT2)
        _bg(scan_startup, done=_done)

    def _repop_startup(self):
        self._sttree.delete(*self._sttree.get_children())
        total = sum(i.delay_ms for i in self._starts if i.kill_safe)
        self._stbanner.configure(
            text=f"  Estimated bloat-caused boot delay:  {total} ms  ·  ~{total//1000}s saved if disabled")
        for i in self._starts:
            self._sttree.insert("", "end",
                values=(i.name, i.publisher, f"{i.delay_ms} ms",
                        i.impact, i.safety_rating.upper(), i.recommendation),
                tags=(i.safety_rating,))

    def _dis_start_sel(self, _=None):
        sel = self._sttree.selection()
        if not sel: return
        idx = self._sttree.index(sel[0])
        if idx >= len(self._starts): return
        item = self._starts[idx]
        if not item.kill_safe:
            messagebox.showinfo("Required", f"{item.name}  is required by Windows."); return
        if messagebox.askyesno("Disable Startup Item",
                f"Remove  {item.name}  from startup?\n\nBoot time saved:  ~{item.delay_ms} ms\n\n{item.recommendation}"):
            iid = sel[0]
            def _done(r):
                if r["ok"]:
                    try: self._sttree.delete(iid)
                    except: pass
                messagebox.showinfo("Result", r["msg"])
            _bg(disable_startup, item.name, item.location, done=_done)

    def _dis_all_starts(self):
        t = [i for i in self._starts if i.kill_safe and i.safety_rating in ("bloat","telemetry")]
        if not t: messagebox.showinfo("All Clear", "No bloat startup items found."); return
        names = "\n".join(f"    •  {i.name}   (~{i.delay_ms} ms)" for i in t)
        total = sum(i.delay_ms for i in t)
        if messagebox.askyesno("Disable All Bloat Startups",
                f"Disable  {len(t)}  startup items?\n\n{names}\n\n"
                f"Total boot time saved:  ~{total} ms"):
            self._setstatus("Disabling startup items…", AMBER)
            def _do(): return sum(1 for i in t if disable_startup(i.name, i.location)["ok"])
            def _done(ok):
                messagebox.showinfo("Done",
                    f"Disabled  {ok} / {len(t)}  startup items.\nBoot time saved:  ~{total} ms")
                self._scan_startup()
            _bg(_do, done=_done)

    # ── Services ─────────────────────────────────────────────────────────────
    def _pg_svcs(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "Service Manager")
        mkbtn(h, "⟳  Scan", self._scan_svcs, ACCENT, side="right")
        divider(p)
        vf, self._svctree = mktree(p,
            ("Service","Display Name","Status","Rating","Category","Recommendation"),
            (155, 195, 88, 110, 105, 0))
        vf.pack(fill="both", expand=True, padx=20, pady=10)
        bot = tk.Frame(p, bg=BG); bot.pack(fill="x", padx=20, pady=10)
        tk.Label(bot, text="Double-click to disable  ·  Requires Administrator",
                 fg=TEXT3, font=F_SM, bg=BG).pack(side="left")
        mkbtn(bot, "Disable All Bloat Services", self._dis_all_svcs, RED, side="right")
        self._svctree.bind("<Double-1>", self._dis_svc_sel)
        self._scan_svcs()
        return p

    def _scan_svcs(self):
        self._setstatus("Scanning services…", AMBER)
        def _done(svcs):
            self._svcs = svcs
            self._repop_svcs()
            self._setstatus("Done.", TEXT2)
        _bg(scan_services, done=_done)

    def _repop_svcs(self):
        self._svctree.delete(*self._svctree.get_children())
        for s in self._svcs:
            self._svctree.insert("", "end",
                values=(s.name, s.display_name, s.status.upper(),
                        s.safety_rating.upper(), s.category, s.recommendation),
                tags=(s.safety_rating,))

    def _dis_svc_sel(self, _=None):
        sel = self._svctree.selection()
        if not sel: return
        idx = self._svctree.index(sel[0])
        if idx >= len(self._svcs): return
        s = self._svcs[idx]
        if not s.kill_safe:
            messagebox.showinfo("Required", f"{s.name}  is required.\n\n{s.recommendation}"); return
        if messagebox.askyesno("Disable Service",
                f"Disable  {s.display_name} ?\n\n{s.recommendation}"):
            iid = sel[0]
            def _done(r):
                if r["ok"]:
                    try: self._svctree.delete(iid)
                    except: pass
                messagebox.showinfo("Result", r["msg"])
            _bg(disable_service, s.name, done=_done)

    def _dis_all_svcs(self):
        t = [s for s in self._svcs if s.kill_safe and s.safety_rating in ("bloat","telemetry")]
        if not t: messagebox.showinfo("All Clear", "No bloat services found."); return
        names = "\n".join(f"    •  {s.display_name}" for s in t)
        if messagebox.askyesno("Disable All Bloat Services",
                f"Disable  {len(t)}  services?\n\n{names}"):
            self._setstatus("Disabling services…", AMBER)
            def _do(): return sum(1 for s in t if disable_service(s.name)["ok"])
            def _done(ok):
                messagebox.showinfo("Done", f"Disabled  {ok} / {len(t)}  services.")
                self._scan_svcs()
            _bg(_do, done=_done)

    # ── Apps ─────────────────────────────────────────────────────────────────
    def _pg_apps(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "App Manager", "Uninstaller")
        mkbtn(h, "⟳  Scan Apps", self._scan_apps, ACCENT, side="right")
        divider(p)

        ctrl = tk.Frame(p, bg=BG)
        ctrl.pack(fill="x", padx=20, pady=10)
        tk.Label(ctrl, text="Category:", fg=TEXT2, font=F_SM, bg=BG).pack(side="left", padx=(0,4))
        self._af = tk.StringVar(value="ALL")
        om = tk.OptionMenu(ctrl, self._af, "ALL","bloat","game","unknown","system",
                           command=lambda _: self._repop_apps())
        om.configure(bg=CARD2, fg=TEXT, activebackground=CARD,
                     font=F_BODY, relief="flat", bd=0, padx=10, pady=6)
        om["menu"].configure(bg=CARD2, fg=TEXT, font=F_BODY,
                              activebackground=SEL, activeforeground=TEXT)
        om.pack(side="left", padx=(0,12))
        tk.Label(ctrl, text="Search:", fg=TEXT2, font=F_SM, bg=BG).pack(side="left", padx=(0,4))
        self._asrch = tk.StringVar()
        self._asrch.trace_add("write", lambda *_: self._repop_apps())
        tk.Entry(ctrl, textvariable=self._asrch,
                 bg=CARD2, fg=TEXT, insertbackground=TEXT,
                 font=F_BODY, relief="flat", bd=0).pack(
                     side="left", padx=(0,12), ipady=6, ipadx=10)
        self._acnt = tk.Label(ctrl, text="", fg=TEXT3, font=F_SM, bg=BG)
        self._acnt.pack(side="right")

        af, self._atree = mktree(p,
            ("App Name","Version","Publisher","Size MB","Category","Install Date"),
            (240, 105, 190, 96, 100, 110))
        af.pack(fill="both", expand=True, padx=20)

        bot = tk.Frame(p, bg=BG); bot.pack(fill="x", padx=20, pady=10)
        tk.Label(bot, text="Double-click an app to uninstall it",
                 fg=TEXT3, font=F_SM, bg=BG).pack(side="left")
        self._asz = tk.Label(bot, text="", fg=AMBER, font=F_SM, bg=BG)
        self._asz.pack(side="right")
        self._atree.bind("<Double-1>", self._uninstall_sel)
        self._scan_apps()
        return p

    def _scan_apps(self):
        self._setstatus("Scanning installed apps…", AMBER)
        def _done(apps):
            self._apps = apps
            self._repop_apps()
            self._setstatus("Done.", TEXT2)
        _bg(scan_installed_apps, done=_done)

    def _repop_apps(self):
        self._atree.delete(*self._atree.get_children())
        filt = self._af.get(); q = self._asrch.get().lower()
        n, total = 0, 0.0
        for app in self._apps:
            if filt != "ALL" and app.category != filt: continue
            if q and q not in app.name.lower(): continue
            tag = ("bloat" if app.category == "bloat"
                   else "caution" if app.category == "game" else "unknown")
            self._atree.insert("", "end",
                values=(app.name, app.version, app.publisher[:30],
                        f"{app.size_mb} MB", app.category, app.install_date),
                tags=(tag,))
            n += 1; total += app.size_mb
        self._acnt.configure(text=f"{n} apps")
        self._asz.configure(text=f"Total shown:  {total/1024:.1f} GB")

    def _uninstall_sel(self, _=None):
        sel = self._atree.selection()
        if not sel: return
        idx = self._atree.index(sel[0])
        if idx >= len(self._apps): return
        app = self._apps[idx]
        if not app.removable:
            messagebox.showinfo("System Component",
                f"{app.name}  is a system component and cannot be removed."); return
        if messagebox.askyesno("Uninstall App",
                f"Uninstall  {app.name} ?\n\nSize:   {app.size_mb} MB\n"
                f"Publisher:   {app.publisher}\n\nThe system uninstaller will launch."):
            _bg(uninstall_app, app, done=lambda r: messagebox.showinfo("Result", r["msg"]))

    # ── Boost ─────────────────────────────────────────────────────────────────
    def _pg_boost(self):
        p = tk.Frame(self._content, bg=BG)
        page_header(p, "Boost Mode",
                    "Give any app maximum CPU priority + kill all competing bloat")
        divider(p)

        # Power plan bar
        pp_bar = tk.Frame(p, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        pp_bar.pack(fill="x", padx=20, pady=12)
        tk.Label(pp_bar, text="  Power Plan:", fg=TEXT2,
                 font=F_BOLD, bg=CARD).pack(side="left", padx=(8,0), pady=12)
        self._pp_lbl = tk.Label(pp_bar, text="Detecting…",
                                 fg=CYAN, font=F_BOLD, bg=CARD)
        self._pp_lbl.pack(side="left", padx=10)
        for plan, col in [("Balanced", AMBER),("Performance", GREEN),("Power Saver", ACCENT)]:
            mkbtn(pp_bar, plan, lambda pl=plan.lower().replace(" ",""): self._set_power(pl),
                  col, side="right", padx=4)
        self.after(700, self._load_pp)

        # Search + list
        ctrl = tk.Frame(p, bg=BG); ctrl.pack(fill="x", padx=20, pady=(0,8))
        tk.Label(ctrl, text="Search:", fg=TEXT2, font=F_SM, bg=BG).pack(side="left", padx=(0,4))
        self._bsrch = tk.StringVar()
        self._bsrch.trace_add("write", lambda *_: self._repop_boost())
        tk.Entry(ctrl, textvariable=self._bsrch,
                 bg=CARD2, fg=TEXT, insertbackground=TEXT,
                 font=F_BODY, relief="flat", bd=0).pack(
                     side="left", padx=(0,12), ipady=6, ipadx=10)
        mkbtn(ctrl, "⟳  Refresh", self._scan_boost, ACCENT, padx=4)

        bf, self._btree = mktree(p,
            ("Application","PID","CPU %","RAM MB","Status"),
            (280, 75, 88, 100, 110))
        bf.pack(fill="both", expand=True, padx=20)

        bot = tk.Frame(p, bg=BG); bot.pack(fill="x", padx=20, pady=12)
        self._bres = tk.Label(bot, text="", fg=GREEN, font=F_BOLD,
                               bg=BG, wraplength=600, anchor="w")
        self._bres.pack(side="left", fill="x", expand=True)
        tk.Button(bot, text="  ⚡  BOOST SELECTED APP  ",
                  command=self._do_boost,
                  bg=GREEN, fg=BG,
                  activebackground="#059669", activeforeground=BG,
                  font=("Consolas", 12, "bold"),
                  relief="flat", bd=0, cursor="hand2",
                  pady=10, padx=16).pack(side="right")
        self._scan_boost()
        return p

    def _load_pp(self):
        _bg(get_power_plan, done=lambda r: self._pp_lbl.configure(text=r))

    def _set_power(self, plan):
        _bg(set_power_plan, plan, done=lambda r: (
            messagebox.showinfo("Power Plan", r["msg"]), self._load_pp()))

    def _scan_boost(self):
        _bg(self.engine.scan, True, done=lambda procs: (
            setattr(self, '_procs', procs), self._repop_boost()))

    def _repop_boost(self):
        self._btree.delete(*self._btree.get_children())
        q = self._bsrch.get().lower()
        for p in sorted([x for x in self._procs if x.safety_rating != "system"],
                        key=lambda x: x.memory_mb, reverse=True):
            if q and q not in p.name.lower(): continue
            self._btree.insert("", "end",
                values=(p.name, p.pid, f"{p.cpu_percent}%",
                        f"{p.memory_mb} MB", p.status),
                tags=(p.safety_rating,), iid=str(p.pid))

    def _do_boost(self):
        sel = self._btree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select an application to boost first."); return
        pid = int(sel[0])
        proc = next((p for p in self._procs if p.pid == pid), None)
        if not proc: return
        if messagebox.askyesno("⚡ Boost Mode",
                f"Boost  {proc.name} ?\n\n"
                f"  •  Set to HIGH CPU priority\n"
                f"  •  Kill all safe bloat & telemetry processes\n"
                f"  •  Free maximum RAM for your app\n\n"
                f"Best for:  Gaming · Video editing · Compiling · Rendering"):
            self._setstatus(f"Boosting {proc.name}…", GREEN)
            def _done(r):
                self._bres.configure(text=r["msg"], fg=GREEN if r["ok"] else RED)
                self._setstatus("Boost complete.", GREEN)
                self._scan_boost()
            _bg(self.engine.boost_process, pid, proc.name, done=_done)

    # ── Battery ───────────────────────────────────────────────────────────────
    def _pg_battery(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "Battery Diagnostics")
        mkbtn(h, "⟳  Refresh",       self._load_battery,    ACCENT, side="right", padx=4)
        mkbtn(h, "Generate HTML Report", self._gen_bat_report, CYAN,  side="right", padx=4)
        divider(p)

        # Big battery card
        bc = tk.Frame(p, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        bc.pack(fill="x", padx=20, pady=14)

        left = tk.Frame(bc, bg=CARD); left.pack(side="left", padx=24, pady=18)
        self._bat_pct = tk.Label(left, text="— %", fg=CYAN,
                                  font=("Consolas", 40, "bold"), bg=CARD)
        self._bat_pct.pack()
        self._bat_status = tk.Label(left, text="Unknown",
                                     fg=TEXT2, font=F_BOLD, bg=CARD)
        self._bat_status.pack(pady=(4,0))

        right = tk.Frame(bc, bg=CARD); right.pack(side="left", fill="x", expand=True, pady=18)
        self._bat_tiles = {}
        for lbl, key in [("Time Remaining","time"),("Power Source","power"),
                          ("Health Estimate","health"),("Plugged In","plugged")]:
            tf = tk.Frame(right, bg=CARD); tf.pack(side="left", fill="x", expand=True, padx=10)
            tk.Label(tf, text=lbl, fg=TEXT2, font=F_SM, bg=CARD).pack(anchor="w")
            v = tk.StringVar(value="—")
            l = tk.Label(tf, textvariable=v, fg=ACCENT,
                          font=("Consolas", 16, "bold"), bg=CARD)
            l.pack(anchor="w", pady=(4, 0))
            self._bat_tiles[key] = (v, l)

        # Charge bar
        bar_row = tk.Frame(p, bg=BG); bar_row.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(bar_row, text="Charge Level:", fg=TEXT2,
                 font=F_SM, bg=BG).pack(side="left", padx=(0,10))
        self._bat_canvas = tk.Canvas(bar_row, height=22, bg=CARD2,
                                      highlightthickness=1, highlightbackground=BORDER)
        self._bat_canvas.pack(side="left", fill="x", expand=True)

        # Power plan
        section_label(p, "Power Plan")
        pp2 = tk.Frame(p, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        pp2.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(pp2, text="  Current Plan:", fg=TEXT2,
                 font=F_BOLD, bg=CARD).pack(side="left", padx=8, pady=12)
        self._pp_lbl2 = tk.Label(pp2, text="Detecting…", fg=CYAN, font=F_BOLD, bg=CARD)
        self._pp_lbl2.pack(side="left", padx=10)
        for plan, col in [("Balanced", AMBER),("Performance", GREEN),("Power Saver", ACCENT)]:
            mkbtn(pp2, plan, lambda pl=plan.lower().replace(" ",""): self._set_power2(pl),
                  col, side="right", padx=4)

        # Tips
        section_label(p, "Battery Care Tips")
        tips_card = tk.Frame(p, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        tips_card.pack(fill="x", padx=20, pady=(0, 16))
        tips = [
            "Keep battery between 20 % – 80 % for maximum long-term health.",
            "Avoid full 0 %→100 % charge cycles daily — partial cycles are healthier.",
            "High temperatures degrade battery faster — avoid hot surfaces.",
            "Disable Wi-Fi, Bluetooth, and reduce brightness when on battery.",
            "Use Power Saver mode when battery drops below 30 %.",
        ]
        for tip in tips:
            row = tk.Frame(tips_card, bg=CARD)
            row.pack(fill="x", padx=16, pady=6)
            tk.Label(row, text="•", fg=ACCENT, font=F_BOLD, bg=CARD).pack(side="left", padx=(0,8))
            tk.Label(row, text=tip, fg=TEXT, font=F_BODY, bg=CARD, anchor="w").pack(side="left", fill="x")
        tk.Frame(tips_card, bg=CARD, height=8).pack()

        self._load_battery()
        _bg(get_power_plan, done=lambda r: self._pp_lbl2.configure(text=r))
        return p

    def _load_battery(self):
        def _done(b):
            if b is None:
                self._bat_pct.configure(text="N/A", fg=TEXT3)
                self._bat_status.configure(text="No battery detected")
                return
            self._bat_pct.configure(text=f"{b.percent}%", fg=b.charge_color)
            self._bat_status.configure(text=b.status, fg=b.charge_color)
            self._bat_tiles["time"][0].set(f"{b.time_left_min} min" if b.time_left_min else ("∞" if b.plugged else "—"))
            self._bat_tiles["power"][0].set("AC Power" if b.plugged else "Battery")
            self._bat_tiles["health"][0].set(b.health_estimate)
            self._bat_tiles["plugged"][0].set("Yes" if b.plugged else "No")
            for _, l in self._bat_tiles.values(): l.configure(fg=b.charge_color)
            self._tiles["bat"].set(f"{b.percent}%", b.charge_color)
            self._bat_canvas.update_idletasks()
            w = self._bat_canvas.winfo_width() or 500
            self._bat_canvas.delete("all")
            fw = int(w * b.percent / 100)
            self._bat_canvas.create_rectangle(0, 0, fw, 22, fill=b.charge_color, outline="")
            self._bat_canvas.create_text(w//2, 11, text=f"{b.percent}%",
                                          fill=TEXT, font=F_BOLD)
        _bg(get_battery, done=_done)

    def _gen_bat_report(self):
        path = os.path.join(os.path.expanduser("~"), "Desktop", "wind0c_battery_report.html")
        self._setstatus("Generating battery report…", AMBER)
        def _done(r):
            self._setstatus("Done.", GREEN)
            if r["ok"]:
                if messagebox.askyesno("Report Ready",
                        f"Battery report generated!\n\n{r['path']}\n\nOpen now?"):
                    webbrowser.open(f"file:///{r['path'].replace(chr(92),'/')}")
            else:
                messagebox.showerror("Error", r["msg"])
        _bg(generate_battery_report_html, path, done=_done)

    def _set_power2(self, plan):
        _bg(set_power_plan, plan, done=lambda r: (
            messagebox.showinfo("Power Plan", r["msg"]),
            _bg(get_power_plan, done=lambda pp: self._pp_lbl2.configure(text=pp))))

    # ── Network ───────────────────────────────────────────────────────────────
    def _pg_network(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "Network Monitor")
        mkbtn(h, "⟳  Refresh", self._load_network, ACCENT, side="right")
        divider(p)

        net_row = tk.Frame(p, bg=BG); net_row.pack(fill="x", padx=20, pady=12)
        net_row.columnconfigure((0,1,2,3,4,5), weight=1)
        self._net_tiles = {}
        for i, (lbl, key) in enumerate([
            ("Hostname","host"),("Local IP","ip"),
            ("Connections","conns"),("Sent MB","sent"),
            ("Received MB","recv"),("Errors","err")
        ]):
            tf = tk.Frame(net_row, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            tf.grid(row=0, column=i, padx=4, sticky="nsew", ipady=4)
            tk.Label(tf, text=lbl, fg=TEXT2, font=F_SM, bg=CARD).pack(anchor="w", padx=12, pady=(10,0))
            v = tk.StringVar(value="—")
            tk.Label(tf, textvariable=v, fg=ACCENT,
                     font=("Consolas", 14, "bold"), bg=CARD).pack(anchor="w", padx=12, pady=(2,10))
            self._net_tiles[key] = v

        section_label(p, "Network Interfaces")
        if2, self._if_tree = mktree(p,
            ("Interface","IP Address","Netmask","Speed","Status"),
            (170, 140, 140, 100, 90), height=5)
        if2.pack(fill="x", padx=20, pady=(0,8))

        section_label(p, "Active Connections")
        cf, self._conn_tree = mktree(p,
            ("Process","PID","Type","Local Address","Remote Address","Status"),
            (165, 65, 65, 175, 175, 100))
        cf.pack(fill="both", expand=True, padx=20, pady=(0,16))
        self._load_network()
        return p

    def _load_network(self):
        self._setstatus("Scanning network…", AMBER)
        def _do(): return get_network_info(), get_active_connections()
        def _done(res):
            info, conns = res
            self._net_tiles["host"].set(info.hostname)
            self._net_tiles["ip"].set(info.local_ip)
            self._net_tiles["conns"].set(info.connections_count)
            self._net_tiles["sent"].set(f"{info.bytes_sent_mb}")
            self._net_tiles["recv"].set(f"{info.bytes_recv_mb}")
            self._net_tiles["err"].set(info.errors_in + info.errors_out)
            self._if_tree.delete(*self._if_tree.get_children())
            for iface in info.interfaces:
                self._if_tree.insert("", "end",
                    values=(iface["name"], iface["ip"], iface["netmask"],
                            f"{iface['speed_mbps']} Mbps",
                            "UP" if iface["is_up"] else "DOWN"),
                    tags=("good" if iface["is_up"] else "crit",))
            self._conn_tree.delete(*self._conn_tree.get_children())
            for c in conns[:200]:
                tag = ("good" if c["status"]=="ESTABLISHED"
                       else "warn" if c["status"]=="LISTEN" else "unknown")
                self._conn_tree.insert("", "end",
                    values=(c["process"], c["pid"], c["type"],
                            c["local"], c["remote"], c["status"]),
                    tags=(tag,))
            self._setstatus("Done.", TEXT2)
        _bg(_do, done=_done)

    # ── Disk ──────────────────────────────────────────────────────────────────
    def _pg_disk(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "Disk Health", "Storage Overview")
        mkbtn(h, "⟳  Refresh", self._load_disk, ACCENT, side="right")
        divider(p)
        self._disk_cards_frame = tk.Frame(p, bg=BG)
        self._disk_cards_frame.pack(fill="x", padx=20, pady=12)
        section_label(p, "Drive Details")
        df, self._disk_tree = mktree(p,
            ("Drive","Mount","FS Type","Total GB","Used GB","Free GB","Used %","Read MB","Write MB","Status"),
            (80, 80, 70, 90, 90, 90, 75, 90, 90, 85))
        df.pack(fill="both", expand=True, padx=20, pady=(0,16))
        self._load_disk()
        return p

    def _load_disk(self):
        self._setstatus("Scanning disks…", AMBER)
        def _done(disks):
            for w in self._disk_cards_frame.winfo_children(): w.destroy()
            self._disk_tree.delete(*self._disk_tree.get_children())
            for d in disks:
                card = tk.Frame(self._disk_cards_frame, bg=CARD,
                                highlightbackground=d.color, highlightthickness=2)
                card.pack(side="left", fill="x", expand=True, padx=6, pady=4)
                tk.Label(card, text=d.device, fg=d.color,
                         font=F_BOLD, bg=CARD).pack(anchor="w", padx=14, pady=(12,0))
                tk.Label(card, text=f"{d.used_gb} / {d.total_gb} GB",
                         fg=TEXT, font=("Consolas", 15, "bold"), bg=CARD).pack(anchor="w", padx=14)
                bar = tk.Canvas(card, height=10, bg=CARD2, highlightthickness=0)
                bar.pack(fill="x", padx=14, pady=(6,2))
                bar.update_idletasks()
                bw = bar.winfo_width() or 180
                bar.create_rectangle(0, 0, int(bw*d.percent/100), 10, fill=d.color, outline="")
                tk.Label(card, text=f"{d.percent}%  used   ·   {d.status}",
                         fg=d.color, font=F_SM, bg=CARD).pack(anchor="w", padx=14, pady=(0,12))
                tag = "crit" if d.percent>90 else "warn" if d.percent>75 else "good"
                self._disk_tree.insert("","end",
                    values=(d.device, d.mountpoint, d.fstype,
                            d.total_gb, d.used_gb, d.free_gb,
                            f"{d.percent}%", d.read_mb, d.write_mb, d.status),
                    tags=(tag,))
            self._setstatus("Done.", TEXT2)
        _bg(get_disk_info, done=_done)

    # ── Temperatures ──────────────────────────────────────────────────────────
    def _pg_temps(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "Temperature Monitor")
        mkbtn(h, "⟳  Refresh", self._load_temps, ACCENT, side="right")
        divider(p)
        self._temp_cards_frame = tk.Frame(p, bg=BG)
        self._temp_cards_frame.pack(fill="x", padx=20, pady=12)
        section_label(p, "All Sensors")
        tf, self._temp_tree = mktree(p,
            ("Sensor","Label","Current °C","High °C","Critical °C","Status"),
            (150, 180, 120, 100, 115, 100))
        tf.pack(fill="both", expand=True, padx=20)
        self._temp_warn = tk.Label(p, text="", fg=RED, font=F_BOLD, bg=BG, anchor="w")
        self._temp_warn.pack(fill="x", padx=20, pady=(6,8))
        self._load_temps()
        return p

    def _load_temps(self):
        self._setstatus("Reading temperatures…", AMBER)
        def _done(temps):
            for w in self._temp_cards_frame.winfo_children(): w.destroy()
            self._temp_tree.delete(*self._temp_tree.get_children())
            if not temps:
                tk.Label(self._temp_cards_frame,
                    text="Temperature sensors not available on this system.\n"
                         "Windows requires OpenHardwareMonitor or compatible drivers.",
                    fg=TEXT2, font=F_BODY, bg=BG, justify="left").pack(anchor="w", padx=4, pady=16)
                self._setstatus("Done.", TEXT2); return
            warnings = []
            for t in temps:
                card = tk.Frame(self._temp_cards_frame, bg=CARD,
                                highlightbackground=t["color"], highlightthickness=2)
                card.pack(side="left", padx=6, pady=4, fill="x", expand=True)
                tk.Label(card, text=t["label"][:20], fg=TEXT2,
                         font=F_SM, bg=CARD).pack(anchor="w", padx=14, pady=(12,0))
                tk.Label(card, text=f"{t['current']} °C",
                         fg=t["color"], font=("Consolas", 24, "bold"), bg=CARD).pack(anchor="w", padx=14)
                tk.Label(card, text=t["status"], fg=t["color"],
                         font=F_SM, bg=CARD).pack(anchor="w", padx=14, pady=(0,12))
                tag = "crit" if t["current"]>85 else "warn" if t["current"]>70 else "good"
                self._temp_tree.insert("", "end",
                    values=(t["sensor"], t["label"],
                            f"{t['current']} °C",
                            f"{t['high']} °C" if t["high"] else "—",
                            f"{t['critical']} °C" if t["critical"] else "—",
                            t["status"]),
                    tags=(tag,))
                if t["current"] > 80: warnings.append(f"{t['label']}:  {t['current']}°C")
            self._temp_warn.configure(
                text="⚠  HIGH TEMPERATURE:  " + "  |  ".join(warnings) if warnings else "")
            self._setstatus("Done.", TEXT2)
        _bg(get_temperatures, done=_done)

    # ── Cleaner ───────────────────────────────────────────────────────────────
    def _pg_cleaner(self):
        p = tk.Frame(self._content, bg=BG)
        page_header(p, "Junk File Cleaner")
        divider(p)

        # Stats banner
        self._clean_card = tk.Frame(p, bg=CARD,
                                     highlightbackground=BORDER, highlightthickness=1)
        self._clean_card.pack(fill="x", padx=20, pady=12)
        self._clean_stats = tk.Label(self._clean_card,
            text="   Click  Scan Temp Files  to find junk on your system…",
            fg=TEXT2, font=F_BOLD, bg=CARD)
        self._clean_stats.pack(side="left", padx=4, pady=16)

        bf = tk.Frame(p, bg=BG); bf.pack(fill="x", padx=20, pady=(0, 8))
        mkbtn(bf, "🔍  Scan Temp Files",      self._scan_clean,  ACCENT, padx=4)
        mkbtn(bf, "🧹  Clean All Temp Files",  self._do_clean,    RED,    padx=4)

        section_label(p, "What Gets Cleaned")
        info_card = tk.Frame(p, bg=CARD,
                              highlightbackground=BORDER, highlightthickness=1)
        info_card.pack(fill="x", padx=20, pady=(0, 10))
        for loc in [
            (r"%TEMP%",          "User temporary files"),
            (r"%TMP%",           "Secondary temp folder"),
            (r"C:\Windows\Temp", "System temp files"),
            (r"%LOCALAPPDATA%\Temp", "App temp cache"),
        ]:
            row = tk.Frame(info_card, bg=CARD); row.pack(fill="x", padx=16, pady=6)
            tk.Label(row, text=loc[0], fg=ACCENT, font=F_MONO_B, bg=CARD,
                     width=26, anchor="w").pack(side="left")
            tk.Label(row, text=loc[1], fg=TEXT, font=F_BODY, bg=CARD,
                     anchor="w").pack(side="left")
        tk.Frame(info_card, bg=CARD, height=8).pack()

        section_label(p, "Temp Files Found")
        cf, self._clean_tree = mktree(p,
            ("File Path","Size KB","Folder"),
            (420, 100, 250))
        cf.pack(fill="both", expand=True, padx=20, pady=(0,16))
        return p

    def _scan_clean(self):
        self._setstatus("Scanning temp files…", AMBER)
        self._clean_stats.configure(text="   Scanning…  Please wait.", fg=AMBER)
        def _done(r):
            self._clean_stats.configure(
                text=f"   Found  {r['total_files']}  temp files  ·  "
                     f"{r['total_size_mb']} MB  ({r['total_size_gb']} GB)  of junk",
                fg=RED)
            self._clean_tree.delete(*self._clean_tree.get_children())
            for f in r["files"][:300]:
                self._clean_tree.insert("", "end",
                    values=(f["path"][-70:], f["size_kb"], f["folder"]),
                    tags=("warn",))
            self._setstatus("Scan done.", TEXT2)
        _bg(scan_temp_files, done=_done)

    def _do_clean(self):
        if not messagebox.askyesno("Clean Temp Files",
                "Delete all temporary files?\n\n"
                "This is completely safe — temp files are recreated automatically.\n"
                "Files currently in use will be skipped automatically."):
            return
        self._setstatus("Cleaning temp files…", AMBER)
        self._clean_stats.configure(text="   Cleaning…  Please wait.", fg=AMBER)
        def _done(r):
            self._clean_stats.configure(
                text=f"   Cleaned  {r['deleted']}  files  ·  {r['freed_mb']} MB  freed",
                fg=GREEN)
            self._clean_tree.delete(*self._clean_tree.get_children())
            self._setstatus("Clean complete.", GREEN)
            messagebox.showinfo("Clean Complete", r["msg"])
        _bg(clean_temp_files, done=_done)

    # ── System Info ───────────────────────────────────────────────────────────
    def _pg_sysinfo(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "System Information")
        mkbtn(h, "⟳  Refresh", self._load_sysinfo, ACCENT, side="right")
        divider(p)

        # Creator banner
        cb = tk.Frame(p, bg=CARD, highlightbackground=CYAN, highlightthickness=2)
        cb.pack(fill="x", padx=20, pady=14)
        tk.Label(cb, text=f"  {APP}", fg=ACCENT,
                 font=("Consolas", 18, "bold"), bg=CARD).pack(anchor="w", padx=16, pady=(14,0))
        tk.Label(cb, text=f"  v{VERSION}  ·  System Optimizer",
                 fg=TEXT2, font=F_BODY, bg=CARD).pack(anchor="w", padx=16)
        tk.Label(cb, text=f"  Created by   {CREATOR}",
                 fg=CYAN, font=("Consolas", 12, "bold"), bg=CARD).pack(anchor="w", padx=16, pady=(4,0))

        links_row = tk.Frame(cb, bg=CARD)
        links_row.pack(anchor="w", padx=16, pady=(6,14))

        gh_btn = tk.Button(links_row,
            text="  ⌥  GitHub: padmesh6119  ",
            command=lambda: webbrowser.open("https://github.com/padmesh6119"),
            bg=CARD2, fg=ACCENT, activebackground=BG, activeforeground=ACCENT,
            font=("Consolas", 10, "bold"), relief="flat", bd=0, cursor="hand2",
            pady=6, padx=4)
        gh_btn.pack(side="left", padx=(0,10), ipady=4, ipadx=6)

        li_btn = tk.Button(links_row,
            text="  ⌘  LinkedIn: padmesh1101  ",
            command=lambda: webbrowser.open("https://www.linkedin.com/in/padmesh1101"),
            bg=CARD2, fg=CYAN, activebackground=BG, activeforeground=CYAN,
            font=("Consolas", 10, "bold"), relief="flat", bd=0, cursor="hand2",
            pady=6, padx=4)
        li_btn.pack(side="left", ipady=4, ipadx=6)

        # Info grid
        grid = tk.Frame(p, bg=BG); grid.pack(fill="both", expand=True, padx=20)
        grid.columnconfigure((0,1), weight=1)
        self._info_vars = {}
        sections = [
            ("OS & Machine", [
                ("Operating System","os"), ("OS Version","os_version"),
                ("Architecture","machine"), ("Computer Name","hostname"),
                ("Python Version","python"),
            ]),
            ("Processor", [
                ("Processor","processor"), ("Physical Cores","cpu_physical"),
                ("Logical Cores","cpu_logical"), ("Current Freq (MHz)","cpu_freq_mhz"),
                ("Max Freq (MHz)","cpu_freq_max"),
            ]),
            ("Memory & Storage", [
                ("Total RAM (GB)","ram_total_gb"), ("Used RAM (GB)","ram_used_gb"),
                ("Last Boot","boot_time"), ("Uptime","uptime"),
            ]),
            ("Wind0c", [
                ("App Version","winslim_ver"), ("Created By","created_by"),
            ]),
        ]
        for i, (sec_name, fields) in enumerate(sections):
            card = tk.Frame(grid, bg=CARD,
                            highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=i//2, column=i%2, padx=6, pady=6, sticky="nsew")
            tk.Label(card, text=sec_name, fg=ACCENT,
                     font=F_BOLD, bg=CARD).pack(anchor="w", padx=16, pady=(12,4))
            for label, key in fields:
                row = tk.Frame(card, bg=CARD); row.pack(fill="x")
                tk.Frame(row, bg=BORDER, height=1).pack(fill="x")
                inner = tk.Frame(row, bg=CARD); inner.pack(fill="x", padx=16, pady=9)
                tk.Label(inner, text=label+":", fg=TEXT2,
                         font=F_SM, bg=CARD, width=22, anchor="w").pack(side="left")
                v = tk.StringVar(value="—")
                col = CYAN if key == "created_by" else ACCENT if key in ("winslim_ver","uptime") else TEXT
                tk.Label(inner, textvariable=v, fg=col,
                         font=F_BOLD, bg=CARD, anchor="w").pack(side="left", fill="x")
                self._info_vars[key] = v
            tk.Frame(card, bg=CARD, height=8).pack()

        self._load_sysinfo()
        return p

    def _load_sysinfo(self):
        def _done(info):
            for key, v in self._info_vars.items():
                v.set(str(info.get(key, "—") or "—"))
        _bg(get_full_system_info, done=_done)

    # ── History ───────────────────────────────────────────────────────────────
    def _pg_hist(self):
        p = tk.Frame(self._content, bg=BG)
        h = page_header(p, "Action History")
        mkbtn(h, "⟳  Refresh", self._load_hist, ACCENT, side="right")
        divider(p)
        tk.Label(p,
            text="  Every kill, boost, disable, and clean — logged here with timestamps.",
            fg=TEXT2, font=F_SM, bg=BG, anchor="w").pack(fill="x", padx=20, pady=8)
        hf, self._htree = mktree(p,
            ("Timestamp","Process","PID","Action","Detail"),
            (165, 200, 75, 130, 0))
        hf.pack(fill="both", expand=True, padx=20, pady=(0,16))
        self._load_hist()
        return p

    def _load_hist(self):
        rows = self.engine.db.get_actions(100)
        self._htree.delete(*self._htree.get_children())
        for name, pid, action, detail, ts in rows:
            tag = ("bloat"   if "KILL"  in action
                   else "caution" if "BOOST" in action else "unknown")
            self._htree.insert("", "end",
                values=(ts[:19].replace("T"," ") if ts else "",
                        name, pid, action, detail),
                tags=(tag,))

    # ── Poll ──────────────────────────────────────────────────────────────────
    def _poll(self):
        if self._busy: self.after(10000, self._poll); return
        self._busy = True
        self._setstatus("Scanning…", AMBER)
        def _do(): return self.engine.scan(), self.engine.get_system_stats()
        def _done(res):
            procs, stats = res
            self._procs = procs
            self._update_dash(stats, procs)
            self._busy = False
            self._setstatus(f"Last scan  {datetime.now().strftime('%H:%M:%S')}", TEXT3)
            self.after(10000, self._poll)
        _bg(_do, done=_done)

    def _update_dash(self, stats, procs):
        cpu = stats.get("cpu_percent", 0)
        ram = stats.get("ram_percent", 0)
        self._tiles["cpu"].set(f"{cpu:.0f}%",
            RED if cpu>80 else AMBER if cpu>50 else GREEN)
        self._tiles["ram"].set(
            f"{stats.get('ram_used_gb',0)}/{stats.get('ram_total_gb',0)} G",
            RED if ram>85 else AMBER if ram>60 else GREEN)
        self._tiles["bloat"].set(stats.get("bloat_count", 0))
        self._tiles["waste"].set(f"{stats.get('wasted_ram_mb',0):.0f} MB")
        self._tiles["uptime"].set(f"{stats.get('uptime_hours',0):.1f} h")
        self._dtree.delete(*self._dtree.get_children())
        for p in stats.get("top_bloat", [])[:14]:
            self._dtree.insert("", "end",
                values=(p.name, f"{p.cpu_percent}%", f"{p.memory_mb} MB",
                        p.safety_rating.upper(), p.impact_score,
                        "KILL" if p.kill_safe else "LOCKED"),
                tags=(p.safety_rating,))
        if self._tab == "PROCESSES":
            self._repop_procs()

    # ── Global actions ────────────────────────────────────────────────────────
    def _nuke(self):
        procs = self._procs or self.engine.scan()
        targets = [p for p in procs if p.kill_safe and p.safety_rating in ("bloat","telemetry")]
        if not targets:
            messagebox.showinfo("All Clear", "No bloat processes found right now."); return
        names = "\n".join(f"    •  {p.name}   ({p.memory_mb} MB)" for p in targets[:15])
        total = sum(p.memory_mb for p in targets)
        if messagebox.askyesno("Nuke All Bloat",
                f"Kill  {len(targets)}  bloat / telemetry processes?\n\n"
                f"{names}\n\nRAM to free:  ~{total:.0f} MB"):
            self._setstatus("Nuking bloat…", RED)
            def _done(r):
                self._setstatus("Nuke complete.", GREEN)
                messagebox.showinfo("Done",
                    f"Killed:       {r['killed']}  processes\n"
                    f"RAM freed:    {r['ram_freed_mb']} MB\n"
                    f"Failed:       {r['failed']}  (need Administrator for those)")
                self._deep_scan()
            _bg(self.engine.kill_all_bloat, done=_done)

    def _deep_scan(self):
        self._setstatus("Scanning…", AMBER)
        def _do(): return self.engine.scan(force=True), self.engine.get_system_stats()
        def _done(res):
            procs, stats = res
            self._procs = procs
            self._update_dash(stats, procs)
            self._setstatus(f"Done  {datetime.now().strftime('%H:%M:%S')}", TEXT3)
        _bg(_do, done=_done)

    def _quick_clean(self):
        if messagebox.askyesno("Clean Temp Files",
                "Delete all temporary files now?\n\nThis is safe — files in use are skipped."):
            self._setstatus("Cleaning temp files…", AMBER)
            def _done(r):
                self._setstatus(f"Cleaned  {r['deleted']}  files  ·  {r['freed_mb']} MB freed.", GREEN)
                messagebox.showinfo("Done", r["msg"])
            _bg(clean_temp_files, done=_done)

    def _report(self):
        stats   = self.engine.get_system_stats()
        procs   = self._procs or self.engine.scan()
        bloat   = [p for p in procs if p.kill_safe and p.safety_rating in ("bloat","telemetry")]
        cpu_top = sorted(procs, key=lambda x: x.cpu_percent, reverse=True)[:10]
        mem_top = sorted(procs, key=lambda x: x.memory_mb,   reverse=True)[:10]
        sysinfo = get_full_system_info()
        bat     = get_battery()

        W = 58
        lines = [
            "=" * W,
            f"  {APP}  v{VERSION}   System Report",
            f"  Created by  {CREATOR}",
            f"  Generated:  {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}",
            "=" * W,
            "", "  SYSTEM", "  " + "─"*W,
            f"  OS            {sysinfo.get('os','')}",
            f"  Hostname      {sysinfo.get('hostname','')}",
            f"  Processor     {sysinfo.get('processor','')[:45]}",
            f"  CPU Cores     {sysinfo.get('cpu_physical','')} physical  /  {sysinfo.get('cpu_logical','')} logical",
            f"  Total RAM     {sysinfo.get('ram_total_gb','')} GB",
            f"  Boot Time     {sysinfo.get('boot_time','')}",
            f"  Uptime        {sysinfo.get('uptime','')}",
            "", "  PERFORMANCE", "  " + "─"*W,
            f"  CPU Load      {stats.get('cpu_percent',0)} %",
            f"  RAM Used      {stats.get('ram_used_gb',0)} / {stats.get('ram_total_gb',0)} GB   ({stats.get('ram_percent',0)} %)",
            f"  Disk Free     {stats.get('disk_free_gb',0)} GB",
            f"  Net Sent      {stats.get('net_sent_mb',0)} MB",
            f"  Net Recv      {stats.get('net_recv_mb',0)} MB",
            f"  Processes     {stats.get('total_processes',0)}  total  ·  {stats.get('bloat_count',0)}  bloat",
            f"  Wasted RAM    {stats.get('wasted_ram_mb',0)} MB",
        ]
        if bat:
            lines += ["", "  BATTERY", "  " + "─"*W,
                f"  Charge        {bat.percent} %",
                f"  Status        {bat.status}",
                f"  Health Est.   {bat.health_estimate}",]
        lines += ["", "  BLOAT TO KILL", "  " + "─"*W]
        for pp in bloat[:15]:
            lines.append(f"  {pp.name:<36} {pp.memory_mb:>7.1f} MB   [{pp.safety_rating.upper()}]")
        lines += ["", "  TOP CPU CONSUMERS", "  " + "─"*W]
        for pp in cpu_top:
            lines.append(f"  {pp.name:<36} {pp.cpu_percent:>6.1f} %   {pp.memory_mb:>7.1f} MB")
        lines += ["", "  TOP MEMORY CONSUMERS", "  " + "─"*W]
        for pp in mem_top:
            lines.append(f"  {pp.name:<36} {pp.memory_mb:>7.1f} MB   {pp.cpu_percent:>6.1f} %")
        lines += ["", "=" * W,
                  f"  — End of Report —   {APP}  v{VERSION}  by  {CREATOR}", ""]

        win = tk.Toplevel(self)
        win.title(f"{APP}  Report  —  {datetime.now().strftime('%Y-%m-%d  %H:%M')}")
        win.geometry("720x620")
        win.configure(bg=BG)

        toolbar = tk.Frame(win, bg=PANEL); toolbar.pack(fill="x", padx=0)
        def _save():
            path = os.path.join(os.path.expanduser("~"), "Desktop", "wind0c_report.txt")
            with open(path, "w") as f: f.write("\n".join(lines))
            messagebox.showinfo("Saved", f"Report saved to:\n{path}")
        mkbtn(toolbar, "Save to Desktop", _save,  ACCENT, side="left", padx=8)
        mkbtn(toolbar, "Close",           win.destroy, TEXT2, padx=4, side="right")

        txt = tk.Text(win, bg=CARD, fg=TEXT, font=("Consolas", 10),
                      relief="flat", bd=12, wrap="none",
                      selectbackground=SEL, selectforeground=TEXT)
        vsb = ttk.Scrollbar(win, command=txt.yview); txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); txt.pack(fill="both", expand=True)
        txt.insert("end", "\n".join(lines))
        txt.configure(state="disabled")


def main():
    app = Wind0c()
    app.mainloop()

if __name__ == "__main__":
    main()
