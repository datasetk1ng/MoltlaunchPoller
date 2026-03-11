"""
MoltlaunchPoller — Moltlaunch Agency Control Center
====================================================
An open-source desktop dashboard for monitoring Moltlaunch agents.

Requirements:
    pip install customtkinter

Usage:
    python MoltlaunchPoller.py

Notes:
    - Requires the moltlaunch CLI (mltl) to be installed and on your PATH.
      Install via: npm install -g moltlaunch
    - Agent IDs are session-only by default. Use Save/Load/Update in the sidebar
      to persist them across sessions in a plain .txt file.
    - Window size and position are saved automatically to .moltlaunch_config.json
      in the same folder as the script.
    - Auto Poll is disabled by default; enable it via the checkbox in the sidebar.
"""

import customtkinter as ctk
import subprocess
import threading
from datetime import datetime
import os
import json
from tkinter import filedialog, messagebox

os.environ["PYTHONIOENCODING"] = "utf-8"

# ──────────────────────────────────────────────
# APPEARANCE
# ──────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

REFRESH_INTERVAL = 15000  # ms

ACCENT   = "#3B82F6"
SUCCESS  = "#22C55E"
WARNING  = "#F59E0B"
DANGER   = "#EF4444"
BG_CARD  = "#1E1E2E"
BG_MAIN  = "#13131F"
FG_DIM   = "#6B7280"
FG_TEXT  = "#E2E8F0"


# ──────────────────────────────────────────────
# MAIN APP
# ──────────────────────────────────────────────

class MoltlaunchApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Moltlaunch Control Center")
        self.minsize(900, 640)
        self.configure(fg_color=BG_MAIN)

        # Config file lives next to the script
        self._config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".moltlaunch_config.json"
        )
        self._restore_geometry()

        # State — agents live in memory only, never written to disk
        self.agents: dict[str, str] = {}
        self.agent_status: dict[str, tuple] = {}
        self.last_seen: dict[str, str] = {}
        self.busy = False
        self.busy_lock = threading.Lock()
        self.auto_enabled = ctk.BooleanVar(value=False)  # OFF by default
        self.save_file: str | None = None  # path of last used agents file

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.log("Moltlaunch Control Center started. Add agents to begin.", tag="info")
        self.after(REFRESH_INTERVAL, self._auto_refresh_tick)

    def _restore_geometry(self):
        """Load saved window size and position, or use sensible defaults."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            w = int(cfg.get("width", 1100))
            h = int(cfg.get("height", 760))
            x = cfg.get("x", None)
            y = cfg.get("y", None)
        except (FileNotFoundError, KeyError, json.JSONDecodeError, ValueError):
            w, h, x, y = 1100, 760, None, None

        # Clamp size
        w = max(900, min(w, sw))
        h = max(640, min(h, sh))

        # Centre on first run, otherwise clamp saved position to screen
        if x is None or y is None:
            x = (sw - w) // 2
            y = (sh - h) // 2
        else:
            x = max(0, min(int(x), sw - w))
            y = max(0, min(int(y), sh - h))

        # Store exactly what we're setting — this is what gets saved on close
        self._last_geometry = (w, h, x, y)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Track user resize/move via Configure event (debounced)
        self._geo_save_job = None
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event):
        """Debounced handler — only records geometry after resizing stops."""
        if event.widget is not self:
            return
        if self._geo_save_job:
            self.after_cancel(self._geo_save_job)
        self._geo_save_job = self.after(400, self._record_geometry)

    def _record_geometry(self):
        """Parse and store the current geometry string exactly as set."""
        try:
            geo = self.geometry()   # "WxH+X+Y"
            size, xpos, ypos = geo.split("+")
            w, h = size.split("x")
            self._last_geometry = (int(w), int(h), int(xpos), int(ypos))
        except Exception:
            pass

    def _save_geometry(self):
        """Write the last recorded geometry to disk."""
        try:
            w, h, x, y = self._last_geometry
            cfg = {"width": w, "height": h, "x": x, "y": y}
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
        except Exception:
            pass

    def _on_close(self):
        self._save_geometry()
        self.destroy()

    # ──────────────────────────────────────────
    # BUILD UI
    # ──────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_body()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="  ◈  MOLTLAUNCH",
            font=ctk.CTkFont(family="Courier New", size=20, weight="bold"),
            text_color=ACCENT
        ).grid(row=0, column=0, padx=20, pady=18, sticky="w")

        ctk.CTkLabel(
            header,
            text="Agency Control Center",
            font=ctk.CTkFont(size=12),
            text_color=FG_DIM
        ).grid(row=0, column=1, padx=0, pady=18, sticky="w")

        self.balance_label = ctk.CTkLabel(
            header,
            text="Wallet: —",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=SUCCESS
        )
        self.balance_label.grid(row=0, column=2, padx=10)

        ctk.CTkButton(
            header,
            text="Refresh Balance",
            width=130,
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color=ACCENT,
            text_color=ACCENT,
            hover_color="#1E3A5F",
            command=lambda: threading.Thread(target=self._refresh_balance, daemon=True).start()
        ).grid(row=0, column=3, padx=20)

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        body.grid_columnconfigure(0, weight=0, minsize=280)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_main_panel(body)

    # ── Sidebar ───────────────────────────────

    def _build_sidebar(self, parent):
        sidebar = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12, width=280)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="AGENTS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=FG_DIM
        ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")

        add_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        add_frame.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        add_frame.grid_columnconfigure(0, weight=1)
        add_frame.grid_columnconfigure(1, weight=1)

        self.entry_id = ctk.CTkEntry(
            add_frame,
            placeholder_text="Agent ID",
            height=32,
            font=ctk.CTkFont(size=12)
        )
        self.entry_id.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.entry_id.bind("<Return>", lambda e: self._add_agent())

        ctk.CTkButton(
            add_frame,
            text="+ Add Agent",
            height=32,
            fg_color=ACCENT,
            hover_color="#2563EB",
            command=self._add_agent
        ).grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky="ew")

        self.agent_scroll = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            label_text=""
        )
        self.agent_scroll.grid(row=2, column=0, padx=8, pady=4, sticky="nsew")
        sidebar.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            sidebar,
            text="ACTIONS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=FG_DIM
        ).grid(row=3, column=0, padx=16, pady=(8, 4), sticky="w")

        btn_cfg = dict(height=34, corner_radius=8, font=ctk.CTkFont(size=12))

        ctk.CTkButton(
            sidebar,
            text="Check All Inboxes",
            fg_color=ACCENT,
            hover_color="#2563EB",
            command=lambda: threading.Thread(target=self._check_all_inboxes, daemon=True).start(),
            **btn_cfg
        ).grid(row=4, column=0, padx=12, pady=3, sticky="ew")

        ctk.CTkButton(
            sidebar,
            text="Refresh Gigs",
            fg_color="transparent",
            border_width=1,
            border_color=ACCENT,
            text_color=ACCENT,
            hover_color="#1E3A5F",
            command=lambda: threading.Thread(target=self._refresh_gigs, daemon=True).start(),
            **btn_cfg
        ).grid(row=5, column=0, padx=12, pady=3, sticky="ew")

        # Divider label
        ctk.CTkLabel(
            sidebar,
            text="AGENT LIST",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=FG_DIM
        ).grid(row=6, column=0, padx=16, pady=(10, 4), sticky="w")

        file_btn_cfg = dict(height=32, corner_radius=8, font=ctk.CTkFont(size=11))

        ctk.CTkButton(
            sidebar,
            text="💾  Save Agent List",
            fg_color="transparent",
            border_width=1,
            border_color=SUCCESS,
            text_color=SUCCESS,
            hover_color="#14532D",
            command=self._save_agents,
            **file_btn_cfg
        ).grid(row=7, column=0, padx=12, pady=2, sticky="ew")

        ctk.CTkButton(
            sidebar,
            text="📂  Load Agent List",
            fg_color="transparent",
            border_width=1,
            border_color=FG_DIM,
            text_color=FG_DIM,
            hover_color="#2D2D3F",
            command=self._load_agents,
            **file_btn_cfg
        ).grid(row=8, column=0, padx=12, pady=2, sticky="ew")

        self.update_btn = ctk.CTkButton(
            sidebar,
            text="🔄  Update Saved List",
            fg_color="transparent",
            border_width=1,
            border_color=FG_DIM,
            text_color=FG_DIM,
            hover_color="#2D2D3F",
            state="disabled",
            command=self._update_agents,
            **file_btn_cfg
        )
        self.update_btn.grid(row=9, column=0, padx=12, pady=2, sticky="ew")

        ctk.CTkCheckBox(
            sidebar,
            text="Auto Poll (15s)",
            variable=self.auto_enabled,
            font=ctk.CTkFont(size=12),
            checkbox_width=18,
            checkbox_height=18
        ).grid(row=10, column=0, padx=16, pady=(10, 16), sticky="w")

    # ── Main Panel ────────────────────────────

    def _build_main_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        console_frame = ctk.CTkFrame(panel, fg_color=BG_CARD, corner_radius=12, height=56)
        console_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_propagate(False)

        inner = ctk.CTkFrame(console_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=10)
        inner.columnconfigure(0, weight=1)

        self.cmd_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Run CLI command…",
            height=34,
            font=ctk.CTkFont(family="Courier New", size=12)
        )
        self.cmd_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.cmd_entry.bind("<Return>", lambda e: self._run_console_in_thread())

        ctk.CTkButton(
            inner,
            text="Run",
            width=72,
            height=34,
            fg_color=ACCENT,
            hover_color="#2563EB",
            command=self._run_console_in_thread
        ).grid(row=0, column=1)

        log_frame = ctk.CTkFrame(panel, fg_color=BG_CARD, corner_radius=12)
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent", height=38)
        log_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        log_header.grid_columnconfigure(0, weight=1)
        log_header.grid_propagate(False)

        ctk.CTkLabel(
            log_header,
            text="ACTIVITY LOG",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=FG_DIM
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            log_header,
            text="Clear",
            width=60,
            height=26,
            fg_color="transparent",
            border_width=1,
            border_color=FG_DIM,
            text_color=FG_DIM,
            hover_color="#2D2D3F",
            command=self._clear_log
        ).grid(row=0, column=1, sticky="e")

        self.logbox = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="transparent",
            text_color=FG_TEXT,
            wrap="word",
            state="disabled"
        )
        self.logbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 10))

        # Color tags via underlying tk widget
        self.logbox._textbox.tag_config("info",    foreground=FG_TEXT)
        self.logbox._textbox.tag_config("success", foreground=SUCCESS)
        self.logbox._textbox.tag_config("warning", foreground=WARNING)
        self.logbox._textbox.tag_config("error",   foreground=DANGER)
        self.logbox._textbox.tag_config("dim",     foreground=FG_DIM)
        self.logbox._textbox.tag_config("accent",  foreground=ACCENT)

    # ──────────────────────────────────────────
    # AGENT MANAGEMENT
    # ──────────────────────────────────────────

    def _add_agent(self):
        raw_id = self.entry_id.get().strip()

        if not raw_id:
            self.log("Please enter an agent ID.", tag="warning")
            return

        if raw_id in self.agents:
            self.log(f"Agent {raw_id} is already added.", tag="warning")
            return

        self.entry_id.delete(0, "end")
        self.agents[raw_id] = raw_id
        self._render_agent_row(raw_id)
        self.log(f"Agent {raw_id} added.", tag="success")

    def _render_agent_row(self, aid: str):
        row = ctk.CTkFrame(self.agent_scroll, fg_color="#252535", corner_radius=8)
        row.pack(fill="x", pady=3, padx=2)

        # Simple horizontal layout: indicator | ID (expands) | status | remove
        row.grid_columnconfigure(1, weight=1)

        indicator = ctk.CTkLabel(
            row, text="●", text_color=FG_DIM, width=16,
            font=ctk.CTkFont(size=9)
        )
        indicator.grid(row=0, column=0, padx=(10, 6), pady=10)

        ctk.CTkLabel(
            row,
            text=f"#{aid}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=FG_TEXT,
            anchor="w"
        ).grid(row=0, column=1, sticky="w")

        status_lbl = ctk.CTkLabel(
            row, text="Idle",
            font=ctk.CTkFont(size=10),
            text_color=FG_DIM,
            width=56
        )
        status_lbl.grid(row=0, column=2, padx=4)

        ctk.CTkButton(
            row,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            text_color=FG_DIM,
            hover_color=DANGER,
            command=lambda a=aid, r=row: self._remove_agent(a, r)
        ).grid(row=0, column=3, padx=(2, 8))

        self.agent_status[aid] = (indicator, status_lbl)

    def _remove_agent(self, aid: str, row_widget):
        self.agents.pop(aid, None)
        self.agent_status.pop(aid, None)
        self.last_seen.pop(aid, None)
        row_widget.destroy()
        self.log(f"Agent {aid} removed.", tag="dim")

    # ──────────────────────────────────────────
    # SAVE / LOAD / UPDATE
    # ──────────────────────────────────────────

    def _save_agents(self):
        if not self.agents:
            self.log("No agents to save.", tag="warning")
            return
        path = filedialog.asksaveasfilename(
            title="Save Agent List",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="moltlaunch_agents.txt"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.agents.keys()))
            self.save_file = path
            self.after(0, lambda: self.update_btn.configure(
                state="normal", border_color=WARNING, text_color=WARNING))
            self.log(f"Agent list saved to: {os.path.basename(path)}", tag="success")
        except Exception as e:
            self.log(f"Save failed: {e}", tag="error")

    def _load_agents(self):
        path = filedialog.askopenfilename(
            title="Load Agent List",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                ids = [line.strip() for line in f if line.strip()]
            added = 0
            for aid in ids:
                if aid not in self.agents:
                    self.agents[aid] = aid
                    self.after(0, self._render_agent_row, aid)
                    added += 1
            self.save_file = path
            self.after(0, lambda: self.update_btn.configure(
                state="normal", border_color=WARNING, text_color=WARNING))
            self.log(f"Loaded {added} agent(s) from: {os.path.basename(path)}", tag="success")
        except Exception as e:
            self.log(f"Load failed: {e}", tag="error")

    def _update_agents(self):
        if not self.save_file:
            self.log("No save file linked. Use Save first.", tag="warning")
            return
        try:
            with open(self.save_file, "w", encoding="utf-8") as f:
                f.write("\n".join(self.agents.keys()))
            self.log(f"Agent list updated: {os.path.basename(self.save_file)}", tag="success")
        except Exception as e:
            self.log(f"Update failed: {e}", tag="error")

    def _set_agent_status(self, aid: str, status: str, color: str):
        def _update():
            if aid in self.agent_status:
                indicator, lbl = self.agent_status[aid]
                indicator.configure(text_color=color)
                lbl.configure(text=status, text_color=color)
        self.after(0, _update)

    # ──────────────────────────────────────────
    # LOGGING
    # ──────────────────────────────────────────

    def log(self, msg: str, tag: str = "info"):
        self.after(0, self._log_safe, msg, tag)

    def _log_safe(self, msg: str, tag: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logbox.configure(state="normal")
        self.logbox._textbox.insert("end", f"[{timestamp}] ", "dim")
        self.logbox._textbox.insert("end", f"{msg}\n", tag)
        self.logbox.configure(state="disabled")
        self.logbox._textbox.see("end")

    def _clear_log(self):
        self.logbox.configure(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.configure(state="disabled")

    # ──────────────────────────────────────────
    # COMMAND RUNNER
    # ──────────────────────────────────────────

    def _run_cmd(self, cmd: str) -> str:
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=25
            )
            output = result.stdout or result.stderr
            return output.strip() if output else ""
        except subprocess.TimeoutExpired:
            return "Command timed out."
        except Exception as e:
            return f"Command error: {e}"

    # ──────────────────────────────────────────
    # WALLET
    # ──────────────────────────────────────────

    def _refresh_balance(self):
        balance = "Unknown"
        address = ""

        try:
            proc = subprocess.run(
                "mltl wallet --json",
                shell=True,
                capture_output=True,
                encoding="utf-8",
                errors="ignore",
                timeout=25
            )
            combined = proc.stdout.strip() or proc.stderr.strip()
        except Exception as e:
            self.log(f"Wallet command error: {e}", tag="error")
            self.after(0, lambda: self.balance_label.configure(text="Wallet: Error"))
            return

        if combined:
            try:
                data = json.loads(combined)
                balance = str(data.get("balance", data.get("Balance", "Unknown")))
                address = str(data.get("address", data.get("Address", "")))
            except (json.JSONDecodeError, AttributeError):
                for line in combined.splitlines():
                    stripped = line.strip()
                    low = stripped.lower()
                    if low.startswith("balance:"):
                        val = stripped.split(":", 1)[-1].strip()
                        if val:
                            balance = val
                    if low.startswith("address:"):
                        val = stripped.split(":", 1)[-1].strip()
                        if val:
                            address = val

        # Format balance to 6 decimal places if it's a number
        try:
            balance = f"{float(balance):.6f} ETH"
        except (ValueError, TypeError):
            pass

        display = f"Wallet: {balance}"
        if address:
            short = f"{address[:6]}…{address[-4:]}"
            display += f"  ({short})"
        self.after(0, lambda d=display: self.balance_label.configure(text=d))
        self.log("Wallet balance updated.", tag="success")

    # ──────────────────────────────────────────
    # INBOX
    # ──────────────────────────────────────────

    def _check_all_inboxes(self):
        with self.busy_lock:
            if self.busy:
                self.log("Skipped: already polling.", tag="warning")
                return
            self.busy = True

        if not self.agents:
            self.log("No agents added. Use the sidebar to add agents first.", tag="warning")
            with self.busy_lock:
                self.busy = False
            return

        try:
            self.log("Scanning inboxes…", tag="dim")
            for aid in list(self.agents):
                self._set_agent_status(aid, "Checking", ACCENT)
                result = self._run_cmd(f"mltl inbox --agent {aid} --json")

                new_task_found = False
                summary = ""

                if result:
                    try:
                        data = json.loads(result)
                        tasks = data.get("tasks", [])
                        total = data.get("total", len(tasks))
                        if total > 0:
                            summary = f"{total} task(s): " + ", ".join(
                                t.get("status", "?") for t in tasks[:5]
                            )
                            new_requests = [t for t in tasks if t.get("status") == "requested"]
                            if new_requests and self.last_seen.get(aid) != result:
                                new_task_found = True
                                self.last_seen[aid] = result
                        else:
                            summary = "Empty"
                    except (json.JSONDecodeError, AttributeError):
                        summary = result[:120].replace("\n", " ")
                        if "NEW REQUESTS" in result and self.last_seen.get(aid) != result:
                            new_task_found = True
                            self.last_seen[aid] = result
                else:
                    summary = "No response"

                if new_task_found:
                    self.log(f"[!!] New task detected for #{aid}", tag="warning")
                    self._set_agent_status(aid, "New Task!", WARNING)
                else:
                    self._set_agent_status(aid, "Idle", FG_DIM)

                self.log(f"── #{aid} ── {summary}", tag="info")

        finally:
            with self.busy_lock:
                self.busy = False

    # ──────────────────────────────────────────
    # GIGS
    # ──────────────────────────────────────────

    def _refresh_gigs(self):
        if not self.agents:
            self.log("No agents added.", tag="warning")
            return
        self.log("Refreshing gigs…", tag="dim")
        for aid in list(self.agents):
            result = self._run_cmd(f"mltl gig list --agent {aid} --json")
            if result:
                try:
                    data = json.loads(result)
                    # API returns a raw array
                    gigs = data if isinstance(data, list) else data.get("gigs", [])
                    if gigs:
                        lines = []
                        for g in gigs:
                            title = g.get("title", "Untitled")
                            delivery = g.get("deliveryTime", g.get("delivery", "?"))
                            category = g.get("category", "")
                            # Convert priceWei (string, in wei) to ETH
                            try:
                                eth = float(g.get("priceWei", 0)) / 1e18
                                price = f"{eth:.4f} ETH"
                            except (ValueError, TypeError):
                                price = g.get("price", "? ETH")
                            tag_str = f"[{category}]" if category else ""
                            lines.append(f"  • {title} {tag_str} — {price} — {delivery}")
                        self.log(f"── #{aid} ({len(gigs)} gig{'s' if len(gigs) != 1 else ''}) ──\n" + "\n".join(lines), tag="info")
                    else:
                        self.log(f"── #{aid}: no gigs listed", tag="dim")
                except (json.JSONDecodeError, AttributeError):
                    self.log(f"── #{aid} Gigs: parse error", tag="error")
            else:
                self.log(f"── #{aid} Gigs: (no response)", tag="dim")

    # ──────────────────────────────────────────
    # CONSOLE
    # ──────────────────────────────────────────

    def _run_console_in_thread(self):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self.cmd_entry.delete(0, "end")
        threading.Thread(target=self._run_console_command, args=(cmd,), daemon=True).start()

    def _run_console_command(self, cmd: str):
        self.log(f"> {cmd}", tag="accent")
        output = self._run_cmd(cmd)
        self.log(output if output else "(no output)", tag="info" if output else "dim")

    # ──────────────────────────────────────────
    # AUTO POLL
    # ──────────────────────────────────────────

    def _auto_refresh_tick(self):
        if self.auto_enabled.get():
            threading.Thread(target=self._check_all_inboxes, daemon=True).start()
        self.after(REFRESH_INTERVAL, self._auto_refresh_tick)


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────

if __name__ == "__main__":
    app = MoltlaunchApp()
    app.mainloop()