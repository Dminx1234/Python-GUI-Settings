#!/usr/bin/env python3
"""
PyEnv Manager — run.py
======================
Double-click this file (or run: python3 run.py) to start the app.

Requirements: Python 3.10+  ·  tkinter (usually included)
If tkinter is missing on Linux, run:
    sudo apt install python3-tk
"""

import sys
import os

# ── Friendly Python version check ────────────────────────────────────────────
if sys.version_info < (3, 10):
    print("=" * 55)
    print("  PyEnv Manager requires Python 3.10 or newer.")
    print(f"  You are running Python {sys.version.split()[0]}")
    print("  Please download a newer Python from:")
    print("  https://www.python.org/downloads/")
    print("=" * 55)
    input("\nPress Enter to close...")
    sys.exit(1)

# ── Friendly tkinter check ────────────────────────────────────────────────────
try:
    import tkinter as tk
except ImportError:
    print("=" * 55)
    print("  tkinter is not installed.")
    print("  On Linux, fix this with:")
    print("    sudo apt install python3-tk")
    print("  On macOS, reinstall Python from python.org")
    print("=" * 55)
    input("\nPress Enter to close...")
    sys.exit(1)

# ── Make sure we can find the other files ─────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# ── Auto chmod so double-click works on macOS/Linux ───────────────────────────
try:
    os.chmod(__file__, 0o755)
except Exception:
    pass

# ── Launch ────────────────────────────────────────────────────────────────────
try:
    from app import PyEnvManager
    app = PyEnvManager()
    app.mainloop()
except Exception as e:
    import traceback
    err = traceback.format_exc()
    try:
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("PyEnv Manager — Startup Error",
            f"Something went wrong:\n\n{e}\n\nSee terminal for details.")
    except Exception:
        pass
    print("\n--- Error ---")
    print(err)
    input("\nPress Enter to close...")
    sys.exit(1)
