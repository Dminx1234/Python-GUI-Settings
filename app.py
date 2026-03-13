# app.py — PyEnv Manager main window
import os, platform, shutil, subprocess, threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path

from theme   import (BG, SURFACE, CARD, BORDER, ACCENT, ACCENT2,
                     GREEN, YELLOW, RED, PURPLE, FG, FG_DIM, FG_MID,
                     MONO, TYPE_COLORS, setup_styles, btn, badge, make_log)
from core    import (Config, Environment, EnvDiscovery,
                     CONFIG_DIR, ACTIVE_FILE, LAUNCH_TMP, SHELL_HOOK)
from dialogs import (open_create_dialog, open_packages_dialog,
                     open_python_versions_dialog)


class PyEnvManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.title("PyEnv Manager")
        self.geometry("1100x700")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(800, 520)

        self._envs: list[Environment] = []
        self._filtered: list[Environment] = []
        self._selected: Environment | None = None

        setup_styles(self)
        self._build_ui()
        self.after(80,  self._refresh_envs)
        self.after(900, self._check_shell_integration)

    # ─────────────────────────────────────────────────────────────────────────
    #  Layout
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_body()
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=SURFACE, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="⬡ PyEnv Manager",
                 bg=SURFACE, fg=ACCENT, font=(MONO, 13, "bold")
                 ).pack(side="left", padx=16)
        tk.Frame(hdr, bg=BORDER, width=1).pack(side="left", fill="y", pady=10)

        self._active_label = tk.Label(hdr, text="  no active environment",
                                       bg=SURFACE, fg=FG_DIM, font=(MONO, 9))
        self._active_label.pack(side="left", padx=12)

        for text, cmd in [("⟳ Refresh",         self._refresh_envs),
                           ("⬡ Python Versions", self._open_python_versions),
                           ("⚙ Shell Setup",     self._show_shell_setup)]:
            tk.Button(hdr, text=text, bg=SURFACE, fg=FG_MID,
                      relief="flat", cursor="hand2",
                      font=(MONO, 9), padx=8,
                      activebackground=CARD, activeforeground=FG,
                      command=cmd).pack(side="right", padx=4, pady=8)

    def _build_body(self):
        pane = tk.PanedWindow(self, orient="horizontal", bg=BG,
                               sashwidth=3, sashrelief="flat",
                               sashpad=0, handlesize=0)
        pane.pack(fill="both", expand=True)

        left = tk.Frame(pane, bg=SURFACE, width=240)
        pane.add(left, minsize=180, stretch="never")
        self._build_left_panel(left)

        right = tk.Frame(pane, bg=BG)
        pane.add(right, minsize=500, stretch="always")
        self._detail_host = right
        self._show_splash()

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=CARD, height=22)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(bar, textvariable=self._status_var,
                 bg=CARD, fg=FG_DIM, font=(MONO, 8)
                 ).pack(side="left", padx=12)
        tk.Label(bar, text=f"{platform.system()} · Python {__import__('sys').version.split()[0]}",
                 bg=CARD, fg=FG_DIM, font=(MONO, 8)
                 ).pack(side="right", padx=12)

    # ─────────────────────────────────────────────────────────────────────────
    #  Left panel
    # ─────────────────────────────────────────────────────────────────────────
    def _build_left_panel(self, parent):
        tk.Label(parent, text="ENVIRONMENTS",
                 bg=SURFACE, fg=FG_DIM, font=(MONO, 8, "bold")
                 ).pack(anchor="w", padx=10, pady=(10, 4))

        # Search bar
        sf = tk.Frame(parent, bg=BORDER, pady=1)
        sf.pack(fill="x", padx=8, pady=(0, 6))
        inner = tk.Frame(sf, bg=CARD)
        inner.pack(fill="x")
        tk.Label(inner, text="⌕", bg=CARD, fg=FG_DIM,
                 font=(MONO, 11)).pack(side="left", padx=6)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filter())
        tk.Entry(inner, textvariable=self._search_var,
                 bg=CARD, fg=FG, insertbackground=ACCENT,
                 relief="flat", font=(MONO, 9), bd=0
                 ).pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))

        # New environment button
        tk.Button(parent, text="⊕  New Environment",
                  bg=ACCENT, fg="#ffffff", relief="flat", cursor="hand2",
                  font=(MONO, 9, "bold"), padx=8, pady=6,
                  activebackground=ACCENT2, activeforeground="#ffffff",
                  command=self._open_create_dialog
                  ).pack(fill="x", padx=8, pady=(0, 6))

        # Env listbox
        lb_frame = tk.Frame(parent, bg=SURFACE)
        lb_frame.pack(fill="both", expand=True)
        sb = tk.Scrollbar(lb_frame, bg=SURFACE, troughcolor=SURFACE,
                          activebackground=BORDER, relief="flat", bd=0, width=5)
        sb.pack(side="right", fill="y")
        self._listbox = tk.Listbox(
            lb_frame, bg=SURFACE, fg=FG,
            selectbackground=BORDER, selectforeground=ACCENT2,
            relief="flat", bd=0, highlightthickness=0,
            font=(MONO, 10), activestyle="none",
            yscrollcommand=sb.set, cursor="hand2"
        )
        self._listbox.pack(side="left", fill="both", expand=True)
        sb.config(command=self._listbox.yview)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # Right-click context menu on env list
        ctx = tk.Menu(self._listbox, tearoff=0, bg=CARD, fg=FG,
                      activebackground=BORDER, activeforeground=ACCENT2,
                      relief="flat", bd=0, font=(MONO, 9))

        def _ctx_menu(event):
            row = self._listbox.nearest(event.y)
            if row < len(self._filtered):
                self._listbox.selection_clear(0, "end")
                self._listbox.selection_set(row)
                self._on_select()
                env = self._filtered[row]
                ctx.delete(0, "end")
                ctx.add_command(label=f"  ▶  Set as Active",
                                command=lambda: self._set_active(env))
                ctx.add_command(label=f"  ✎  Rename",
                                command=lambda: self._rename_env(env))
                ctx.add_command(label=f"  ↓  Export requirements.txt",
                                command=lambda: self._export_reqs(env))
                ctx.add_separator()
                ctx.add_command(label=f"  ⊗  Delete Environment",
                                foreground=RED,
                                command=lambda: self._delete_env(env))
                ctx.tk_popup(event.x_root, event.y_root)

        self._listbox.bind("<Button-3>", _ctx_menu)
        self._listbox.bind("<Button-2>", _ctx_menu)

    # ─────────────────────────────────────────────────────────────────────────
    #  Splash / empty state
    # ─────────────────────────────────────────────────────────────────────────
    def _show_splash(self):
        self._clear_detail()
        f = tk.Frame(self._detail_host, bg=BG)
        f.pack(expand=True)
        tk.Label(f, text="⬡", bg=BG, fg=BORDER,
                 font=(MONO, 48)).pack(pady=(0, 8))
        tk.Label(f, text="Select an environment",
                 bg=BG, fg=FG_DIM, font=(MONO, 13)).pack()
        tk.Label(f, text="or create one with  ⊕ New Environment",
                 bg=BG, fg=FG_DIM, font=(MONO, 10)).pack(pady=(4, 0))

    # ─────────────────────────────────────────────────────────────────────────
    #  Detail panel
    # ─────────────────────────────────────────────────────────────────────────
    def _show_detail(self, env: Environment):
        self._clear_detail()

        # Scrollable canvas wrapper
        canvas = tk.Canvas(self._detail_host, bg=BG, highlightthickness=0)
        vsb = tk.Scrollbar(self._detail_host, orient="vertical",
                           command=canvas.yview,
                           bg=SURFACE, troughcolor=BG, relief="flat", bd=0, width=5)
        canvas.configure(yscrollcommand=vsb.set)
        inner = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_cfg(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_cfg)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

        def _scroll(e):
            canvas.yview_scroll(-1 if (e.num == 4 or e.delta > 0) else 1, "units")

        for w in (canvas, inner):
            w.bind("<Button-4>", _scroll)
            w.bind("<Button-5>", _scroll)
            w.bind("<MouseWheel>", _scroll)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._build_header_section(inner, env)
        self._build_info_section(inner, env)
        self._build_actions_section(inner, env)
        self._build_packages_section(inner, env)

    def _build_header_section(self, parent, env: Environment):
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(20, 0))

        bg_c, fg_c = TYPE_COLORS.get(env.type, (CARD, FG))
        badges_row = tk.Frame(hdr, bg=BG)
        badges_row.pack(anchor="w")
        badge(badges_row, env.type.upper(), bg_c, fg_c)
        if env.is_active():
            badge(badges_row, "● ACTIVE", "#0f2d1a", GREEN, padx=(6, 0))

        name_row = tk.Frame(parent, bg=BG)
        name_row.pack(fill="x", padx=20, pady=(6, 0))
        self._env_name_var = tk.StringVar(value=env.display_name)
        tk.Label(name_row, textvariable=self._env_name_var,
                 bg=BG, fg=FG, font=(MONO, 20, "bold")).pack(side="left")
        tk.Button(name_row, text="✎", bg=BG, fg=FG_DIM,
                  relief="flat", cursor="hand2", font=(MONO, 12),
                  activebackground=BG, activeforeground=ACCENT,
                  command=lambda: self._rename_env(env)
                  ).pack(side="left", padx=(10, 0))

        tk.Label(parent, text=str(env.path),
                 bg=BG, fg=FG_DIM, font=(MONO, 8)
                 ).pack(anchor="w", padx=20, pady=(2, 0))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=20, pady=12)

    def _build_info_section(self, parent, env: Environment):
        frame = tk.Frame(parent, bg=CARD)
        frame.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(frame, text="ENVIRONMENT INFO",
                 bg=CARD, fg=FG_DIM, font=(MONO, 8, "bold")
                 ).pack(anchor="w", padx=12, pady=(10, 4))

        rows = [
            ("Python",   env.get_version(), ACCENT2),
            ("Type",     env.type.capitalize(), FG),
            ("Location", str(env.path), FG_MID),
        ]
        if env.type != "system":
            rows.append(("Pip", env.pip_bin, FG_MID))

        for label, value, col in rows:
            r = tk.Frame(frame, bg=CARD)
            r.pack(fill="x", padx=12, pady=2)
            tk.Label(r, text=f"{label:<12}", bg=CARD, fg=FG_DIM,
                     font=(MONO, 9)).pack(side="left")
            disp = value if len(value) < 65 else "…" + value[-64:]
            tk.Label(r, text=disp, bg=CARD, fg=col,
                     font=(MONO, 9)).pack(side="left")
        tk.Frame(frame, bg=BG, height=8).pack()

    def _build_actions_section(self, parent, env: Environment):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", padx=20, pady=(0, 4))

        # Row 1 — primary actions
        row1 = tk.Frame(frame, bg=BG)
        row1.pack(fill="x", pady=(0, 6))

        if env.is_active():
            btn(row1, "● Active", GREEN, "#0a2010", lambda: None,
                side="left", bold=True)
        else:
            btn(row1, "▶ Set Active", BG, ACCENT,
                lambda: self._set_active(env),
                side="left", bold=True, border_color=ACCENT)

        btn(row1, "⬡ Terminal",   CARD, FG,
            lambda: self._open_terminal(env), side="left", padx=(8, 0))
        btn(row1, "⊕ Packages",   CARD, FG,
            lambda: self._open_packages(env), side="left", padx=(8, 0))
        btn(row1, "↓ Export reqs", CARD, FG_MID,
            lambda: self._export_reqs(env), side="left", padx=(8, 0))

        if env.type in ("venv", "pyenv"):
            btn(row1, "⬡ Change Python", CARD, PURPLE,
                self._open_python_versions, side="left", padx=(8, 0))

        # Row 2 — danger zone
        if env.type != "system":
            row2 = tk.Frame(frame, bg=BG)
            row2.pack(fill="x", pady=(2, 0))
            tk.Button(row2, text="⊗  Delete Environment",
                      bg=BG, fg=RED, relief="flat", cursor="hand2",
                      font=(MONO, 8), padx=0, pady=0,
                      activebackground=BG, activeforeground="#ff9090",
                      command=lambda: self._delete_env(env)
                      ).pack(side="right")

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=20, pady=10)

    def _build_packages_section(self, parent, env: Environment):
        # Header row
        ph = tk.Frame(parent, bg=BG)
        ph.pack(fill="x", padx=20, pady=(0, 4))
        tk.Label(ph, text="INSTALLED PACKAGES",
                 bg=BG, fg=FG_DIM, font=(MONO, 8, "bold")).pack(side="left")

        # Package search bar
        psf = tk.Frame(parent, bg=CARD)
        psf.pack(fill="x", padx=20, pady=(0, 4))
        tk.Label(psf, text="⌕", bg=CARD, fg=FG_DIM,
                 font=(MONO, 11)).pack(side="left", padx=6)
        pkg_search_var = tk.StringVar()
        tk.Entry(psf, textvariable=pkg_search_var,
                 bg=CARD, fg=FG, insertbackground=ACCENT,
                 relief="flat", font=(MONO, 9), bd=0
                 ).pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))
        pkg_count_var = tk.StringVar(value="loading…")
        tk.Label(psf, textvariable=pkg_count_var,
                 bg=CARD, fg=FG_DIM, font=(MONO, 8)
                 ).pack(side="right", padx=8)

        # Treeview
        tv_frame = tk.Frame(parent, bg=BG)
        tv_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        pkg_tree = ttk.Treeview(tv_frame, columns=("pkg", "ver"),
                                 show="headings", height=14, selectmode="browse")
        pkg_tree.heading("pkg", text="Package", anchor="w")
        pkg_tree.heading("ver", text="Version", anchor="w")
        pkg_tree.column("pkg", width=320, stretch=True)
        pkg_tree.column("ver", width=110, stretch=False)

        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=pkg_tree.yview)
        pkg_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        pkg_tree.pack(side="left", fill="both", expand=True)

        # State kept in closures (not on self) — avoids stale-reference bugs
        all_pkgs: list[dict] = []

        def _populate(pkgs):
            nonlocal all_pkgs
            all_pkgs = pkgs
            _render(pkgs)
            n = len(pkgs)
            pkg_count_var.set(f"{n} package{'s' if n != 1 else ''}")
            self._status(f"Loaded {n} packages.")

        def _render(pkgs):
            pkg_tree.delete(*pkg_tree.get_children())
            for p in pkgs:
                pkg_tree.insert("", "end", values=(p["name"], p["version"]))

        def _filter(*_):
            q = pkg_search_var.get().lower()
            _render([p for p in all_pkgs
                     if q in p["name"].lower() or q in p["version"].lower()])

        pkg_search_var.trace_add("write", _filter)

        def _load():
            pkgs = env.get_packages()
            self.after(0, lambda: _populate(pkgs))

        self._status("Loading packages…")
        threading.Thread(target=_load, daemon=True).start()

        # Right-click context menu
        ctx = tk.Menu(pkg_tree, tearoff=0, bg=CARD, fg=FG,
                      activebackground=BORDER, activeforeground=ACCENT2,
                      relief="flat", bd=0, font=(MONO, 9))

        def _pkg_ctx(event):
            row = pkg_tree.identify_row(event.y)
            if not row: return
            pkg_tree.selection_set(row)
            name = pkg_tree.item(row)["values"][0]
            ctx.delete(0, "end")
            ctx.add_command(label=f"  ↑  Upgrade  {name}",
                            command=lambda: self._pkg_action(env, "upgrade", name, _reload))
            ctx.add_separator()
            ctx.add_command(label=f"  ⊗  Uninstall  {name}",
                            foreground=RED,
                            command=lambda: self._pkg_action(env, "uninstall", name, _reload))
            ctx.tk_popup(event.x_root, event.y_root)

        pkg_tree.bind("<Button-3>", _pkg_ctx)
        pkg_tree.bind("<Button-2>", _pkg_ctx)

        def _reload():
            env._packages = None
            pkg_count_var.set("reloading…")
            threading.Thread(target=_load, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    #  Env list management
    # ─────────────────────────────────────────────────────────────────────────
    def _refresh_envs(self):
        self._status("Scanning for environments…")
        self._listbox.delete(0, "end")
        threading.Thread(target=self._discover, daemon=True).start()

    def _discover(self):
        infos = EnvDiscovery.find_all()
        envs  = [Environment(i, self.cfg) for i in infos]
        self.after(0, lambda: self._on_discovered(envs))

    def _on_discovered(self, envs):
        self._envs = envs
        self._apply_filter()
        self._update_active_badge()
        self._status(f"Found {len(envs)} environment(s).")

    def _apply_filter(self):
        q = self._search_var.get().lower() if hasattr(self, "_search_var") else ""
        self._listbox.delete(0, "end")
        self._filtered = []
        for env in self._envs:
            if q in env.display_name.lower() or q in env.type.lower():
                marker = "● " if env.is_active() else "  "
                self._listbox.insert("end", f"{marker}{env.display_name}")
                if env.is_active():
                    self._listbox.itemconfig(self._listbox.size() - 1, fg=GREEN)
                self._filtered.append(env)

    def _on_select(self, _event=None):
        sel = self._listbox.curselection()
        if not sel: return
        idx = sel[0]
        if idx < len(self._filtered):
            self._selected = self._filtered[idx]
            self._show_detail(self._selected)

    # ─────────────────────────────────────────────────────────────────────────
    #  Actions
    # ─────────────────────────────────────────────────────────────────────────
    def _set_active(self, env: Environment):
        env.set_active()
        self._update_active_badge()
        self._apply_filter()
        self._show_detail(env)
        self._status(f"Active → {env.display_name}")
        messagebox.showinfo(
            "Environment Activated",
            f"'{env.display_name}' is now active.\n\n"
            "New terminal sessions will use this environment automatically.\n"
            "(Restart any open terminals to pick up the change.)"
        )

    def _rename_env(self, env: Environment):
        new = simpledialog.askstring(
            "Rename", f"New name for '{env.display_name}':",
            initialvalue=env.display_name, parent=self)
        if new and new.strip() and new.strip() != env.display_name:
            env.rename(new.strip())
            self._env_name_var.set(new.strip())
            self._apply_filter()
            self._status(f"Renamed → {new.strip()}")

    def _delete_env(self, env: Environment):
        if env.type == "system":
            messagebox.showwarning("Can't delete",
                "System Python installations cannot be deleted here.", parent=self)
            return
        if not messagebox.askyesno(
            "Delete environment?",
            f"Permanently delete  '{env.display_name}'?\n\n"
            f"Location:  {env.path}\n\n"
            "⚠️  This cannot be undone.\n"
            "Tip: export requirements.txt first if you want to recreate it later.",
            icon="warning", parent=self
        ):
            return

        self._status(f"Deleting {env.display_name}…")

        def _do():
            try:
                env.delete()
                self.after(0, lambda: [
                    self._status(f"Deleted '{env.display_name}'."),
                    self._refresh_envs(),
                    self._show_splash(),
                ])
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "Delete failed", str(e), parent=self))

        threading.Thread(target=_do, daemon=True).start()

    def _export_reqs(self, env: Environment):
        p = filedialog.asksaveasfilename(
            parent=self,
            initialfile="requirements.txt",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not p: return
        try:
            env.export_requirements(Path(p))
            messagebox.showinfo("Exported",
                f"requirements.txt saved to:\n{p}", parent=self)
        except Exception as e:
            messagebox.showerror("Export failed", str(e), parent=self)

    def _open_terminal(self, env: Environment):
        LAUNCH_TMP.parent.mkdir(exist_ok=True)
        LAUNCH_TMP.write_text(
            "#!/usr/bin/env bash\n"
            "source ~/.bashrc 2>/dev/null || source ~/.profile 2>/dev/null\n"
            f"{env.activate_cmd}\n"
            f'echo -e "\\033[0;32m✓ Environment: {env.display_name}\\033[0m"\n'
            "exec bash\n"
        )
        LAUNCH_TMP.chmod(0o755)

        launched = False
        if platform.system() == "Darwin":
            script = (
                'tell application "Terminal"\n'
                f'    do script "source \\"{LAUNCH_TMP}\\""\n'
                "    activate\nend tell"
            )
            try:
                subprocess.Popen(["osascript", "-e", script])
                launched = True
            except Exception:
                pass
        else:
            for name, cmd in [
                ("gnome-terminal", ["gnome-terminal", "--", "bash", str(LAUNCH_TMP)]),
                ("kitty",          ["kitty", "--", "bash", str(LAUNCH_TMP)]),
                ("alacritty",      ["alacritty", "-e", "bash", str(LAUNCH_TMP)]),
                ("wezterm",        ["wezterm", "start", "--", "bash", str(LAUNCH_TMP)]),
                ("konsole",        ["konsole", "-e", "bash", str(LAUNCH_TMP)]),
                ("xfce4-terminal", ["xfce4-terminal", "-e", f"bash {LAUNCH_TMP}"]),
                ("xterm",          ["xterm", "-e", f"bash {LAUNCH_TMP}"]),
            ]:
                if shutil.which(name):
                    try:
                        subprocess.Popen(cmd)
                        launched = True
                        self._status(f"Opened {name}.")
                        break
                    except Exception:
                        continue

        if not launched:
            messagebox.showwarning("No terminal found",
                f"Could not find a terminal emulator.\n\nRun manually:\n\n{env.activate_cmd}")

    def _pkg_action(self, env: Environment, action: str, name: str, reload_cb):
        if action == "uninstall":
            if not messagebox.askyesno(
                "Uninstall?", f"Uninstall '{name}' from '{env.display_name}'?",
                parent=self
            ): return
        self._status(f"{action.capitalize()}ing {name}…")

        def _do():
            try:
                if action == "uninstall":
                    r = subprocess.run([env.pip_bin, "uninstall", "-y", name],
                                       capture_output=True, text=True, timeout=60)
                else:
                    r = subprocess.run([env.pip_bin, "install", "--upgrade", name],
                                       capture_output=True, text=True, timeout=120)
                msg = f"{'✓' if r.returncode == 0 else '✗'} {action} {name}"
                self.after(0, lambda: [self._status(msg), reload_cb()])
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=_do, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    #  Dialog launchers
    # ─────────────────────────────────────────────────────────────────────────
    def _open_create_dialog(self):
        open_create_dialog(self, self.cfg, on_done=self._refresh_envs)

    def _open_packages(self, env: Environment):
        def _reload():
            if self._selected == env:
                env._packages = None
                self._show_detail(env)
        open_packages_dialog(self, env, on_done=_reload)

    def _open_python_versions(self):
        open_python_versions_dialog(
            self, self.cfg, self._envs,
            on_done=self._refresh_envs
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  Shell integration
    # ─────────────────────────────────────────────────────────────────────────
    def _check_shell_integration(self):
        rc_files = [Path.home() / f for f in (".bashrc", ".zshrc", ".bash_profile")]
        installed = any(
            f.exists() and "pyenv_manager" in f.read_text()
            for f in rc_files
        )
        if not installed:
            self._show_shell_setup()

    def _show_shell_setup(self):
        win = tk.Toplevel(self)
        win.title("Shell Integration")
        win.geometry("600x460")
        win.configure(bg=BG)
        win.grab_set()
        win.focus_set()

        tk.Label(win, text="Shell Integration Setup",
                 bg=BG, fg=FG, font=(MONO, 14, "bold")
                 ).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(win,
                 text="This one-time setup lets PyEnv Manager activate your chosen\n"
                      "environment automatically every time you open a terminal.",
                 bg=BG, fg=FG_DIM, font=(MONO, 9), justify="left"
                 ).pack(anchor="w", padx=20)

        code = tk.Text(win, bg=CARD, fg=ACCENT2, height=3,
                       font=(MONO, 9), relief="flat", bd=0, padx=12, pady=10)
        code.pack(fill="x", padx=20, pady=12)
        code.insert("1.0", SHELL_HOOK.strip())
        code.config(state="disabled")

        # Status per shell file
        sf = tk.Frame(win, bg=CARD)
        sf.pack(fill="x", padx=20, pady=(0, 16))
        tk.Label(sf, text="Shell files found:",
                 bg=CARD, fg=FG_DIM, font=(MONO, 8, "bold")
                 ).pack(anchor="w", padx=12, pady=(8, 4))
        for f in [Path.home() / n for n in (".bashrc", ".zshrc", ".bash_profile", ".profile")]:
            if f.exists():
                ok = "pyenv_manager" in f.read_text()
                r = tk.Frame(sf, bg=CARD)
                r.pack(fill="x", padx=12, pady=2)
                tk.Label(r, text=f"  {f.name:<22}", bg=CARD, fg=FG_MID,
                         font=(MONO, 9)).pack(side="left")
                tk.Label(r, text="● installed" if ok else "○ not installed",
                         bg=CARD, fg=GREEN if ok else FG_DIM,
                         font=(MONO, 9)).pack(side="left")
        tk.Frame(sf, bg=BG, height=8).pack()

        brow = tk.Frame(win, bg=BG)
        brow.pack(fill="x", padx=20)
        btn(brow, "Auto-Install Hook", BG, ACCENT,
            lambda: [self._install_hook(), win.destroy()],
            side="left", bold=True, border_color=ACCENT)
        if platform.system() == "Linux":
            btn(brow, "Create .desktop File", CARD, FG,
                self._create_desktop_file, side="left", padx=(8, 0))
        btn(brow, "Dismiss", CARD, FG_DIM, win.destroy, side="right")

    def _install_hook(self):
        CONFIG_DIR.mkdir(exist_ok=True)
        if not ACTIVE_FILE.exists():
            ACTIVE_FILE.write_text("# No environment selected yet\n")
        modified = []
        for rc in [Path.home() / ".bashrc", Path.home() / ".zshrc"]:
            if rc.exists():
                c = rc.read_text()
                if "pyenv_manager" not in c:
                    rc.write_text(c + SHELL_HOOK)
                    modified.append(rc.name)
        messagebox.showinfo(
            "Hook Installed" if modified else "Already Installed",
            (f"Added to: {', '.join(modified)}\n\nRestart your terminal to activate."
             if modified else "Hook already present in your shell files.")
        )

    def _create_desktop_file(self):
        import sys
        script = Path(sys.argv[0]).resolve().parent / "run.py"
        desktop_dir = Path.home() / ".local" / "share" / "applications"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        df = desktop_dir / "pyenv-manager.desktop"
        df.write_text(
            "[Desktop Entry]\n"
            "Name=PyEnv Manager\n"
            "Comment=Python Environment Manager\n"
            f"Exec=python3 {script}\n"
            "Icon=python3\n"
            "Terminal=false\n"
            "Type=Application\n"
            "Categories=Development;Utility;\n"
            "StartupNotify=true\n"
        )
        messagebox.showinfo("Done",
            f"Created: {df}\n\nFind PyEnv Manager in your application launcher.")

    # ─────────────────────────────────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _clear_detail(self):
        for w in self._detail_host.winfo_children():
            w.destroy()

    def _update_active_badge(self):
        key = self.cfg.active
        if key:
            for env in self._envs:
                if env.key == key:
                    self._active_label.config(
                        text=f"  ● {env.display_name}  [{env.type}]", fg=GREEN)
                    return
        self._active_label.config(text="  no active environment", fg=FG_DIM)

    def _status(self, msg: str):
        self._status_var.set(msg)
