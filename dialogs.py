# dialogs.py — popup dialogs for PyEnv Manager
import os, re, shutil, subprocess, threading, platform, webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from theme import (BG, SURFACE, CARD, BORDER, ACCENT, ACCENT2,
                   GREEN, YELLOW, RED, PURPLE, FG, FG_DIM, FG_MID,
                   MONO, TYPE_COLORS, btn, badge, make_log, entry)
from core  import EnvDiscovery, Environment, CONFIG_DIR


# ─────────────────────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────────────────────
def _dialog(parent, title, w, h):
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(f"{w}x{h}")
    win.configure(bg=BG)
    win.resizable(True, True)
    win.grab_set()
    win.focus_set()
    return win


def _section(parent, label):
    tk.Label(parent, text=label, bg=BG, fg=FG_DIM,
             font=(MONO, 8, "bold")).pack(anchor="w", padx=20, pady=(10, 3))


def _divider(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=20, pady=8)


def _type_toggle(parent, var, options, on_change=None):
    """Renders a row of toggle buttons; returns {val: button} dict."""
    frame = tk.Frame(parent, bg=BG)
    frame.pack(side="left")
    btns = {}

    def _pick(v):
        var.set(v)
        for k, b in btns.items():
            b.config(bg=ACCENT if k == v else CARD,
                     fg="#fff"  if k == v else FG_MID)
        if on_change:
            on_change(v)

    for val, lbl in options:
        b = tk.Button(frame, text=lbl,
                      bg=ACCENT if var.get() == val else CARD,
                      fg="#fff"  if var.get() == val else FG_MID,
                      relief="flat", cursor="hand2",
                      font=(MONO, 9), padx=14, pady=5,
                      activebackground=BORDER, activeforeground=FG,
                      command=lambda v=val: _pick(v))
        b.pack(side="left", padx=(0, 4))
        btns[val] = b

    return btns


# ─────────────────────────────────────────────────────────────────────────────
#  Create Environment dialog
# ─────────────────────────────────────────────────────────────────────────────
def open_create_dialog(parent, cfg, on_done):
    win = _dialog(parent, "Create New Environment", 620, 600)

    tk.Label(win, text="⊕  Create New Environment",
             bg=BG, fg=FG, font=(MONO, 13, "bold")
             ).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(win, text="Set up a new isolated Python environment",
             bg=BG, fg=FG_DIM, font=(MONO, 9)
             ).pack(anchor="w", padx=20)
    _divider(win)

    form = tk.Frame(win, bg=BG)
    form.pack(fill="x", padx=20)

    def _row(label):
        r = tk.Frame(form, bg=BG)
        r.pack(fill="x", pady=(0, 8))
        tk.Label(r, text=label, bg=BG, fg=FG_DIM,
                 font=(MONO, 8, "bold"), width=12, anchor="w").pack(side="left")
        return r

    # ── Type ──────────────────────────────────────────────────────────────────
    type_var = tk.StringVar(value="venv")
    r = _row("Type")
    _type_toggle(r, type_var, [("venv", "venv"), ("conda", "conda")])

    # ── Name ──────────────────────────────────────────────────────────────────
    name_entry = entry(_row("Name"), )
    name_entry.pack(side="left", fill="x", expand=True, ipady=5)

    # ── Location ──────────────────────────────────────────────────────────────
    default_dir = Path.home() / ".virtualenvs"
    default_dir.mkdir(exist_ok=True)
    loc_var = tk.StringVar(value=str(default_dir))
    r = _row("Location")
    loc_e = entry(r, textvariable=loc_var)
    loc_e.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))
    tk.Button(r, text="…", bg=CARD, fg=FG_MID, relief="flat",
              cursor="hand2", font=(MONO, 9), padx=8, pady=4,
              activebackground=BORDER,
              command=lambda: loc_var.set(
                  filedialog.askdirectory(parent=win, initialdir=str(default_dir))
                  or loc_var.get()
              )).pack(side="left")

    # ── Python ────────────────────────────────────────────────────────────────
    pythons = EnvDiscovery.find_python_binaries()
    py_keys   = list(pythons.keys())
    py_labels = list(pythons.values())
    py_var = tk.StringVar(value=py_labels[0] if py_labels else "")

    r = _row("Python")
    if py_labels:
        om = tk.OptionMenu(r, py_var, *py_labels)
        om.config(bg=CARD, fg=FG, activebackground=BORDER,
                  relief="flat", font=(MONO, 9), highlightthickness=0, bd=0)
        om["menu"].config(bg=CARD, fg=FG, font=(MONO, 9),
                          activebackground=BORDER, activeforeground=ACCENT2)
        om.pack(side="left", fill="x", expand=True)
    else:
        tk.Label(r, text="No Python found — install Python first",
                 bg=BG, fg=RED, font=(MONO, 9)).pack(side="left")

    # ── Pre-install packages ──────────────────────────────────────────────────
    r = _row("Packages")
    pkgs_e = entry(r)
    pkgs_e.pack(side="left", fill="x", expand=True, ipady=5)
    tk.Label(form, text="  Optional: space-separated list  e.g.  flask requests numpy",
             bg=BG, fg=FG_DIM, font=(MONO, 8)).pack(anchor="w", pady=(0, 6))

    _divider(win)
    _section(win, "OUTPUT")

    log_frame, log = make_log(win, height=6)
    log_frame.pack(fill="both", expand=True, padx=20, pady=(2, 0))

    # ── Buttons ───────────────────────────────────────────────────────────────
    brow = tk.Frame(win, bg=BG)
    brow.pack(fill="x", padx=20, pady=10)

    create_btn = tk.Button(brow, text="⊕  Create",
                           bg=ACCENT, fg="#fff", relief="flat", cursor="hand2",
                           font=(MONO, 9, "bold"), padx=14, pady=7,
                           activebackground=ACCENT2, activeforeground="#fff")
    create_btn.pack(side="left")
    tk.Button(brow, text="Cancel", bg=CARD, fg=FG_DIM, relief="flat",
              cursor="hand2", font=(MONO, 9), padx=14, pady=7,
              activebackground=BORDER, command=win.destroy).pack(side="right")

    def _do_create():
        name     = name_entry.get().strip()
        loc      = loc_var.get().strip()
        env_type = type_var.get()

        if not name:
            messagebox.showwarning("Name required", "Enter a name for the environment.", parent=win)
            return
        env_path = Path(loc) / name
        if env_path.exists():
            messagebox.showerror("Already exists", f"'{env_path}' already exists.", parent=win)
            return

        chosen_py = py_keys[py_labels.index(py_var.get())] if py_labels and py_var.get() in py_labels else "python3"
        extra = pkgs_e.get().strip().split()

        create_btn.config(state="disabled", text="Creating…")
        log(f"Creating {env_type} env at {env_path}", "dim")

        def _worker():
            nonlocal env_path
            try:
                if env_type == "venv":
                    cmd = [chosen_py, "-m", "venv", str(env_path)]
                    log(f"$ {' '.join(cmd)}", "dim")
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if r.stderr: log(r.stderr.strip(), "dim")
                    if r.returncode != 0:
                        log("✗ Failed to create environment.", "err"); return

                elif env_type == "conda":
                    if not shutil.which("conda"):
                        log("✗ conda not found. Install Anaconda/Miniconda first.", "err"); return
                    m = re.search(r"Python (\d+\.\d+)", pythons.get(chosen_py, ""))
                    py_ver = m.group(1) if m else "3.11"
                    cmd = ["conda", "create", "-y", "--prefix", str(env_path), f"python={py_ver}"]
                    log(f"$ {' '.join(cmd)}", "dim")
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True)
                    for line in proc.stdout: log(line.rstrip())
                    proc.wait()
                    if proc.returncode != 0:
                        log("✗ conda create failed.", "err"); return

                log(f"✓ Environment created!", "ok")

                if extra:
                    pip = str(env_path / "bin" / "pip")
                    if not Path(pip).exists():
                        pip = str(env_path / "bin" / "pip3")
                    log(f"Installing: {' '.join(extra)}", "dim")
                    proc = subprocess.Popen([pip, "install"] + extra,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True)
                    for line in proc.stdout: log(line.rstrip())
                    proc.wait()
                    log("✓ Packages installed." if proc.returncode == 0
                        else "⚠ Some packages may have failed.", 
                        "ok" if proc.returncode == 0 else "err")

                log("Done — refreshing list…", "dim")
                parent.after(300, on_done)
                parent.after(1500, win.destroy)

            except Exception as e:
                log(f"✗ {e}", "err")
            finally:
                parent.after(0, lambda: create_btn.config(
                    state="normal", text="⊕  Create"))

        threading.Thread(target=_worker, daemon=True).start()

    create_btn.config(command=_do_create)
    name_entry.focus_set()
    win.bind("<Return>", lambda _: _do_create())


# ─────────────────────────────────────────────────────────────────────────────
#  Packages dialog
# ─────────────────────────────────────────────────────────────────────────────
def open_packages_dialog(parent, env: Environment, on_done):
    win = _dialog(parent, f"Packages — {env.display_name}", 640, 540)

    tk.Label(win, text="⊕  Manage Packages",
             bg=BG, fg=FG, font=(MONO, 13, "bold")
             ).pack(anchor="w", padx=20, pady=(16, 2))
    tk.Label(win, text=f"Environment:  {env.display_name}  [{env.type}]  ·  {env.get_version()}",
             bg=BG, fg=FG_DIM, font=(MONO, 9)
             ).pack(anchor="w", padx=20)
    _divider(win)

    # ── Mode toggle ───────────────────────────────────────────────────────────
    mode_var = tk.StringVar(value="install")
    mode_row = tk.Frame(win, bg=BG)
    mode_row.pack(fill="x", padx=20, pady=(0, 10))

    pkg_frame = tk.Frame(win, bg=BG)
    req_frame = tk.Frame(win, bg=BG)

    def _set_mode(m):
        mode_var.set(m)
        if m == "install":
            req_frame.pack_forget()
            pkg_frame.pack(fill="x", padx=20, pady=(0, 8))
        elif m == "requirements":
            pkg_frame.pack_forget()
            req_frame.pack(fill="x", padx=20, pady=(0, 8))
        else:  # upgrade
            pkg_frame.pack_forget()
            req_frame.pack_forget()

    _type_toggle(mode_row, mode_var,
                 [("install", "Install Packages"),
                  ("requirements", "requirements.txt"),
                  ("upgrade", "Upgrade All")],
                 on_change=_set_mode)

    # ── Install packages input ────────────────────────────────────────────────
    tk.Label(pkg_frame,
             text="Packages  (space-separated — or paste  pip install x y z  directly):",
             bg=BG, fg=FG_DIM, font=(MONO, 8)).pack(anchor="w")
    pkg_text = tk.Text(pkg_frame, bg=CARD, fg=FG, insertbackground=ACCENT,
                       relief="flat", font=(MONO, 10), height=3,
                       bd=0, padx=8, pady=6,
                       highlightthickness=1, highlightbackground=BORDER,
                       highlightcolor=ACCENT)
    pkg_text.pack(fill="x", pady=(4, 0))
    pkg_frame.pack(fill="x", padx=20, pady=(0, 8))

    # ── Requirements.txt ──────────────────────────────────────────────────────
    tk.Label(req_frame, text="Select a requirements.txt file:",
             bg=BG, fg=FG_DIM, font=(MONO, 8)).pack(anchor="w")
    req_inner = tk.Frame(req_frame, bg=BG)
    req_inner.pack(fill="x", pady=(4, 0))
    req_var = tk.StringVar()
    req_e = entry(req_inner, textvariable=req_var)
    req_e.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
    tk.Button(req_inner, text="Browse…", bg=CARD, fg=FG_MID,
              relief="flat", cursor="hand2", font=(MONO, 9),
              padx=10, pady=5, activebackground=BORDER,
              command=lambda: req_var.set(
                  filedialog.askopenfilename(
                      parent=win, title="Select requirements.txt",
                      filetypes=[("Text", "*.txt"), ("All", "*.*")]
                  ) or req_var.get()
              )).pack(side="left")
    tk.Label(req_frame,
             text="Tip: Paste  pip install requests flask  in the Install tab too.",
             bg=BG, fg=FG_DIM, font=(MONO, 8)).pack(anchor="w", pady=(6, 0))

    _section(win, "OUTPUT")
    log_frame, log = make_log(win, height=8)
    log_frame.pack(fill="both", expand=True, padx=20, pady=(2, 0))

    brow = tk.Frame(win, bg=BG)
    brow.pack(fill="x", padx=20, pady=10)

    run_btn = tk.Button(brow, text="▶  Run",
                        bg=ACCENT, fg="#fff", relief="flat", cursor="hand2",
                        font=(MONO, 9, "bold"), padx=14, pady=7,
                        activebackground=ACCENT2, activeforeground="#fff")
    run_btn.pack(side="left")

    # Export requirements
    def _export():
        p = filedialog.asksaveasfilename(
            parent=win, initialfile="requirements.txt",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")]
        )
        if p:
            try:
                env.export_requirements(Path(p))
                log(f"✓ Saved requirements to {p}", "ok")
            except Exception as e:
                log(f"✗ {e}", "err")

    tk.Button(brow, text="↓ Export reqs", bg=CARD, fg=FG_MID,
              relief="flat", cursor="hand2", font=(MONO, 9),
              padx=10, pady=7, activebackground=BORDER,
              command=_export).pack(side="left", padx=(8, 0))

    tk.Button(brow, text="Close", bg=CARD, fg=FG_DIM,
              relief="flat", cursor="hand2", font=(MONO, 9),
              padx=14, pady=7, activebackground=BORDER,
              command=lambda: [on_done(), win.destroy()]
              ).pack(side="right")

    def _run():
        mode = mode_var.get()
        run_btn.config(state="disabled", text="Running…")

        def _worker():
            try:
                if mode == "upgrade":
                    log("Checking for outdated packages…", "dim")
                    r = subprocess.run(
                        [env.pip_bin, "list", "--outdated", "--format=columns"],
                        capture_output=True, text=True, timeout=30)
                    pkgs = [l.split()[0] for l in r.stdout.strip().split("\n")[2:] if l.strip()]
                    if not pkgs:
                        log("✓ Everything is already up to date!", "ok")
                    else:
                        log(f"Upgrading {len(pkgs)} package(s)…", "dim")
                        proc = subprocess.Popen(
                            [env.pip_bin, "install", "--upgrade"] + pkgs,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        for line in proc.stdout: log(line.rstrip())
                        proc.wait()
                        log("✓ Upgrade complete." if proc.returncode == 0
                            else "✗ Some upgrades failed.", 
                            "ok" if proc.returncode == 0 else "err")

                elif mode == "requirements":
                    rpath = req_var.get().strip()
                    if not rpath or not Path(rpath).exists():
                        log("✗ File not found. Click Browse to pick a file.", "err"); return
                    log(f"$ pip install -r {Path(rpath).name}", "dim")
                    proc = subprocess.Popen(
                        [env.pip_bin, "install", "-r", rpath],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in proc.stdout:
                        log(line.rstrip(), "ok" if "Successfully installed" in line else "")
                    proc.wait()
                    log("✓ Done." if proc.returncode == 0 else "✗ Some errors occurred.",
                        "ok" if proc.returncode == 0 else "err")

                else:  # install
                    raw = pkg_text.get("1.0", "end").strip()
                    if not raw:
                        log("Enter at least one package name above.", "dim"); return
                    raw = re.sub(r"^\s*pip\s+install\s+", "", raw, flags=re.IGNORECASE)
                    pkgs = raw.split()
                    if not pkgs: return
                    log(f"$ pip install {' '.join(pkgs)}", "dim")
                    proc = subprocess.Popen(
                        [env.pip_bin, "install"] + pkgs,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in proc.stdout:
                        tag = "ok" if "Successfully installed" in line else (
                              "err" if "ERROR" in line else "")
                        log(line.rstrip(), tag)
                    proc.wait()
                    log("✓ Done." if proc.returncode == 0 else "✗ Some errors occurred.",
                        "ok" if proc.returncode == 0 else "err")

                env._packages = None
                parent.after(200, on_done)

            except Exception as e:
                log(f"✗ {e}", "err")
            finally:
                parent.after(0, lambda: run_btn.config(state="normal", text="▶  Run"))

        threading.Thread(target=_worker, daemon=True).start()

    run_btn.config(command=_run)
    pkg_text.focus_set()
    win.bind("<Control-Return>", lambda _: _run())


# ─────────────────────────────────────────────────────────────────────────────
#  Python Version Manager dialog
# ─────────────────────────────────────────────────────────────────────────────
def open_python_versions_dialog(parent, cfg, envs, on_done):
    win = _dialog(parent, "Python Version Manager", 700, 660)

    tk.Label(win, text="⬡  Python Versions",
             bg=BG, fg=FG, font=(MONO, 13, "bold")
             ).pack(anchor="w", padx=20, pady=(16, 2))
    tk.Label(win,
             text="Install new Python versions · Swap the Python used by a venv",
             bg=BG, fg=FG_DIM, font=(MONO, 9)
             ).pack(anchor="w", padx=20)
    _divider(win)

    # ── Installed Pythons ─────────────────────────────────────────────────────
    _section(win, "PYTHONS FOUND ON YOUR SYSTEM")

    tv_frame = tk.Frame(win, bg=CARD)
    tv_frame.pack(fill="x", padx=20, pady=(2, 10))

    cols = ("ver", "path")
    tree = ttk.Treeview(tv_frame, columns=cols, show="headings",
                        height=5, selectmode="browse")
    tree.heading("ver",  text="Version",  anchor="w")
    tree.heading("path", text="Location", anchor="w")
    tree.column("ver",  width=160, stretch=False)
    tree.column("path", width=480, stretch=True)
    tsb = ttk.Scrollbar(tv_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=tsb.set)
    tsb.pack(side="right", fill="y")
    tree.pack(side="left", fill="x", expand=True)

    def _load_installed():
        tree.delete(*tree.get_children())
        for real, label in EnvDiscovery.find_python_binaries().items():
            ver_part = label.split("·")[0].strip()
            path_part = label.split("·")[1].strip() if "·" in label else real
            tree.insert("", "end", values=(ver_part, path_part))

    _load_installed()

    # ── Swap Python ───────────────────────────────────────────────────────────
    venv_envs  = [e for e in envs if e.type in ("venv",)]
    venv_names = [e.display_name for e in venv_envs]

    if venv_envs:
        swap_frame = tk.Frame(win, bg=BG)
        swap_frame.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(swap_frame,
                 text="Select a Python above → choose a venv → Rebuild with that Python:",
                 bg=BG, fg=FG_DIM, font=(MONO, 8)).pack(anchor="w", pady=(0, 4))
        si = tk.Frame(swap_frame, bg=BG)
        si.pack(fill="x")
        swap_var = tk.StringVar(value=venv_names[0])
        om = tk.OptionMenu(si, swap_var, *venv_names)
        om.config(bg=CARD, fg=FG, activebackground=BORDER, relief="flat",
                  font=(MONO, 9), highlightthickness=0, bd=0)
        om["menu"].config(bg=CARD, fg=FG, font=(MONO, 9),
                          activebackground=BORDER, activeforeground=ACCENT2)
        om.pack(side="left", padx=(0, 8))

        def _do_swap():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select Python",
                    "Click a Python version in the list above first.", parent=win)
                return
            py_path = tree.item(sel[0])["values"][1].strip()
            if not os.path.isfile(py_path):
                messagebox.showerror("Not found", f"Cannot find: {py_path}", parent=win)
                return
            target = next((e for e in venv_envs if e.display_name == swap_var.get()), None)
            if not target: return
            if not messagebox.askyesno(
                "Rebuild environment?",
                f"Rebuild  '{target.display_name}'  with:\n{py_path}\n\n"
                "Your packages will be automatically reinstalled from a backup.\n"
                "This cannot be undone.", parent=win
            ): return
            _do_rebuild(target, py_path)

        tk.Button(si, text="⟳  Rebuild venv with this Python",
                  bg=YELLOW, fg="#1a1200", relief="flat", cursor="hand2",
                  font=(MONO, 9, "bold"), padx=12, pady=6,
                  activebackground=ACCENT, activeforeground="#fff",
                  command=_do_swap).pack(side="left")

    _divider(win)

    # ── Install new Python ────────────────────────────────────────────────────
    _section(win, "INSTALL A NEW PYTHON VERSION")

    # Detect available methods
    has_pyenv = bool(shutil.which("pyenv"))
    has_apt   = bool(shutil.which("apt"))
    has_brew  = bool(shutil.which("brew"))
    on_mac    = platform.system() == "Darwin"
    on_linux  = platform.system() == "Linux"

    # Big friendly "Get Python" button always visible
    get_frame = tk.Frame(win, bg=CARD)
    get_frame.pack(fill="x", padx=20, pady=(2, 8))
    inner = tk.Frame(get_frame, bg=CARD)
    inner.pack(fill="x", padx=16, pady=12)

    tk.Label(inner,
             text="The easiest way: download the official installer from Python.org",
             bg=CARD, fg=FG, font=(MONO, 9)).pack(anchor="w")
    tk.Label(inner,
             text="Run the installer, then click  ↺ Refresh List  below to see the new version.",
             bg=CARD, fg=FG_DIM, font=(MONO, 8)).pack(anchor="w", pady=(2, 8))

    def _open_python_org():
        webbrowser.open("https://www.python.org/downloads/")
        _log("Opening Python.org downloads page in your browser…", "dim")

    tk.Button(inner, text="🌐  Download Python from Python.org",
              bg=ACCENT, fg="#fff", relief="flat", cursor="hand2",
              font=(MONO, 10, "bold"), padx=16, pady=8,
              activebackground=ACCENT2, activeforeground="#fff",
              command=_open_python_org).pack(anchor="w")

    # Advanced methods (pyenv / brew / apt) — collapsed by default
    adv_visible = tk.BooleanVar(value=False)
    adv_toggle = tk.Button(win, text="▸ Advanced: install via package manager",
                           bg=BG, fg=FG_DIM, relief="flat", cursor="hand2",
                           font=(MONO, 8), anchor="w",
                           activebackground=BG, activeforeground=FG_MID)
    adv_toggle.pack(anchor="w", padx=20)

    adv_frame = tk.Frame(win, bg=BG)

    def _toggle_adv():
        if adv_visible.get():
            adv_visible.set(False)
            adv_frame.pack_forget()
            adv_toggle.config(text="▸ Advanced: install via package manager")
        else:
            adv_visible.set(True)
            adv_frame.pack(fill="x", padx=20, pady=(4, 0))
            adv_toggle.config(text="▾ Advanced: install via package manager")

    adv_toggle.config(command=_toggle_adv)

    # ── pyenv ──────────────────────────────────────────────────────────────
    if has_pyenv:
        pf = tk.Frame(adv_frame, bg=CARD)
        pf.pack(fill="x", pady=(0, 6))
        pi = tk.Frame(pf, bg=CARD)
        pi.pack(fill="x", padx=12, pady=8)
        tk.Label(pi, text="pyenv  —  version:", bg=CARD, fg=FG_DIM,
                 font=(MONO, 9)).pack(side="left", padx=(0, 8))
        pyenv_ver_var = tk.StringVar(value="3.12.3")
        entry(pi, textvariable=pyenv_ver_var, width=10).pack(
            side="left", ipady=5, padx=(0, 8))

        def _list_pyenv():
            def _fetch():
                try:
                    r = subprocess.run(["pyenv", "install", "--list"],
                                       capture_output=True, text=True, timeout=20)
                    vers = [l.strip() for l in r.stdout.split("\n")
                            if re.match(r"^\s+3\.\d+\.\d+$", l)]
                    parent.after(0, lambda: _pick_version(vers, pyenv_ver_var, win))
                except Exception as e:
                    _log(f"Error: {e}", "err")
            threading.Thread(target=_fetch, daemon=True).start()

        tk.Button(pi, text="List…", bg=SURFACE, fg=FG_MID,
                  relief="flat", cursor="hand2", font=(MONO, 9),
                  padx=8, pady=4, activebackground=BORDER,
                  command=_list_pyenv).pack(side="left", padx=(0, 8))

        def _pyenv_install():
            ver = pyenv_ver_var.get().strip()
            if not ver: return
            _log(f"$ pyenv install {ver}", "dim")
            _stream_cmd(["pyenv", "install", ver])

        tk.Button(pi, text="Install", bg=GREEN, fg="#0a1a0a",
                  relief="flat", cursor="hand2", font=(MONO, 9, "bold"),
                  padx=10, pady=4, activebackground=ACCENT,
                  command=_pyenv_install).pack(side="left")

    # ── brew (macOS) ────────────────────────────────────────────────────────
    if has_brew and on_mac:
        bf = tk.Frame(adv_frame, bg=CARD)
        bf.pack(fill="x", pady=(0, 6))
        bi = tk.Frame(bf, bg=CARD)
        bi.pack(fill="x", padx=12, pady=8)
        tk.Label(bi, text="Homebrew  —  version:", bg=CARD, fg=FG_DIM,
                 font=(MONO, 9)).pack(side="left", padx=(0, 8))
        brew_ver_var = tk.StringVar(value="3.12")
        entry(bi, textvariable=brew_ver_var, width=8).pack(
            side="left", ipady=5, padx=(0, 8))

        def _brew_install():
            ver = brew_ver_var.get().strip()
            _log(f"$ brew install python@{ver}", "dim")
            _stream_cmd(["brew", "install", f"python@{ver}"])

        tk.Button(bi, text="Install", bg=GREEN, fg="#0a1a0a",
                  relief="flat", cursor="hand2", font=(MONO, 9, "bold"),
                  padx=10, pady=4, activebackground=ACCENT,
                  command=_brew_install).pack(side="left")

    # ── apt / deadsnakes (Linux) ───────────────────────────────────────────
    if has_apt and on_linux:
        af = tk.Frame(adv_frame, bg=CARD)
        af.pack(fill="x", pady=(0, 6))
        ai = tk.Frame(af, bg=CARD)
        ai.pack(fill="x", padx=12, pady=8)
        tk.Label(ai, text="apt (deadsnakes)  —  version:", bg=CARD, fg=FG_DIM,
                 font=(MONO, 9)).pack(side="left", padx=(0, 8))
        apt_ver_var = tk.StringVar(value="3.12")
        entry(ai, textvariable=apt_ver_var, width=8).pack(
            side="left", ipady=5, padx=(0, 8))

        def _apt_install():
            ver = apt_ver_var.get().strip()
            pkg = f"python{ver}"
            _log(f"Installing {pkg} via apt + deadsnakes PPA…", "dim")
            cmds = [
                ["sudo", "add-apt-repository", "-y", "ppa:deadsnakes/ppa"],
                ["sudo", "apt-get", "update", "-qq"],
                ["sudo", "apt-get", "install", "-y", pkg, f"{pkg}-venv", f"{pkg}-dev"],
            ]
            def _worker():
                for cmd in cmds:
                    _log(f"$ {' '.join(cmd)}", "dim")
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in proc.stdout: _log(line.rstrip())
                    proc.wait()
                    if proc.returncode != 0:
                        _log("✗ Failed. Try running in a terminal with sudo.", "err")
                        return
                _log(f"✓ {pkg} installed!", "ok")
                parent.after(0, _load_installed)
            threading.Thread(target=_worker, daemon=True).start()

        tk.Button(ai, text="Install", bg=GREEN, fg="#0a1a0a",
                  relief="flat", cursor="hand2", font=(MONO, 9, "bold"),
                  padx=10, pady=4, activebackground=ACCENT,
                  command=_apt_install).pack(side="left")

    # ── Log ───────────────────────────────────────────────────────────────────
    _section(win, "OUTPUT")
    log_frame, _log = make_log(win, height=5)
    log_frame.pack(fill="both", expand=True, padx=20, pady=(2, 0))

    def _stream_cmd(cmd):
        def _worker():
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout: _log(line.rstrip())
                proc.wait()
                if proc.returncode == 0:
                    _log("✓ Done!", "ok")
                    parent.after(0, _load_installed)
                    parent.after(300, on_done)
                else:
                    _log("✗ Command failed.", "err")
            except Exception as e:
                _log(f"✗ {e}", "err")
        threading.Thread(target=_worker, daemon=True).start()

    def _do_rebuild(target_env, py_path):
        def _worker():
            env_path = target_env.path
            backup = CONFIG_DIR / f"{target_env.display_name}_reqs_backup.txt"
            try:
                _log(f"Backing up packages for '{target_env.display_name}'…", "dim")
                target_env.export_requirements(backup)
                _log(f"Saved to {backup}", "dim")

                import shutil as _sh
                _sh.rmtree(str(env_path))
                _log(f"Removed old environment.", "dim")

                r = subprocess.run([py_path, "-m", "venv", str(env_path)],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    _log(f"✗ venv creation failed:\n{r.stderr}", "err"); return
                _log(f"✓ Created new venv with {py_path}", "ok")

                if backup.exists() and backup.read_text().strip():
                    _log("Reinstalling packages…", "dim")
                    proc = subprocess.Popen(
                        [str(env_path / "bin" / "pip"), "install", "-r", str(backup)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in proc.stdout: _log(line.rstrip())
                    proc.wait()
                    _log("✓ Packages reinstalled." if proc.returncode == 0
                         else "⚠ Some packages may have failed.",
                         "ok" if proc.returncode == 0 else "err")

                target_env._version = None
                target_env._packages = None
                parent.after(0, on_done)
                _log("✓ Rebuild complete!", "ok")
            except Exception as e:
                _log(f"✗ {e}", "err")

        threading.Thread(target=_worker, daemon=True).start()

    # ── Bottom buttons ────────────────────────────────────────────────────────
    brow = tk.Frame(win, bg=BG)
    brow.pack(fill="x", padx=20, pady=10)
    tk.Button(brow, text="↺  Refresh List", bg=CARD, fg=FG_MID,
              relief="flat", cursor="hand2", font=(MONO, 9),
              padx=10, pady=7, activebackground=BORDER,
              command=_load_installed).pack(side="left")
    tk.Button(brow, text="Close", bg=CARD, fg=FG_DIM,
              relief="flat", cursor="hand2", font=(MONO, 9),
              padx=14, pady=7, activebackground=BORDER,
              command=win.destroy).pack(side="right")


def _pick_version(versions, var, parent):
    """Small version-picker popup."""
    if not versions:
        messagebox.showinfo("No versions", "Could not fetch version list.", parent=parent)
        return
    pick = tk.Toplevel(parent)
    pick.title("Available Versions")
    pick.geometry("260x380")
    pick.configure(bg=BG)
    pick.grab_set()
    tk.Label(pick, text="Double-click to select:",
             bg=BG, fg=FG_DIM, font=(MONO, 9)
             ).pack(anchor="w", padx=12, pady=(10, 4))
    lb = tk.Listbox(pick, bg=SURFACE, fg=FG,
                    selectbackground=BORDER, selectforeground=ACCENT2,
                    relief="flat", bd=0, highlightthickness=0,
                    font=(MONO, 10), activestyle="none")
    lb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    for v in reversed(versions):
        lb.insert("end", v)

    def _pick(_=None):
        sel = lb.curselection()
        if sel:
            var.set(lb.get(sel[0]).strip())
            pick.destroy()

    lb.bind("<Double-1>", _pick)
    tk.Button(pick, text="Select", bg=ACCENT, fg="#fff",
              relief="flat", cursor="hand2", font=(MONO, 9),
              padx=10, command=_pick).pack(pady=(0, 8))
