# theme.py — colors, fonts, and ttk style setup for PyEnv Manager
from tkinter import ttk

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = "#0d0f18"
SURFACE = "#13151f"
CARD    = "#181b28"
BORDER  = "#252836"
ACCENT  = "#5b8af0"
ACCENT2 = "#7eb8f7"
GREEN   = "#56d17b"
YELLOW  = "#f0c040"
RED     = "#e05c5c"
PURPLE  = "#b48af0"
FG      = "#d0d8f0"
FG_DIM  = "#4e5575"
FG_MID  = "#8892b0"

MONO = "Monospace"

# ── Type badge colors ─────────────────────────────────────────────────────────
TYPE_COLORS = {
    "conda":  ("#1a3d1a", GREEN),
    "venv":   ("#1a2a45", ACCENT2),
    "pyenv":  ("#2a1a45", PURPLE),
    "system": ("#3d3000", YELLOW),
}


def setup_styles(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=FG, font=(MONO, 10))
    s.configure("TFrame",   background=BG)
    s.configure("TLabel",   background=BG, foreground=FG, font=(MONO, 10))
    s.configure("Treeview",
        background=SURFACE, foreground=FG,
        fieldbackground=SURFACE, borderwidth=0, rowheight=26,
        font=(MONO, 9))
    s.configure("Treeview.Heading",
        background=CARD, foreground=FG_DIM,
        borderwidth=0, relief="flat", font=(MONO, 8))
    s.map("Treeview",
        background=[("selected", BORDER)],
        foreground=[("selected", ACCENT2)])
    s.configure("TScrollbar",
        background=SURFACE, troughcolor=BG,
        borderwidth=0, arrowsize=10)


# ── Reusable widget factories ─────────────────────────────────────────────────
import tkinter as tk

def badge(parent, text, bg, fg, padx=(0, 0)):
    tk.Label(parent, text=f"  {text}  ",
             bg=bg, fg=fg, font=(MONO, 8, "bold"),
             padx=2, pady=2).pack(side="left", padx=padx)


def btn(parent, text, bg, fg, command,
        side="left", bold=False, border_color=None, padx=(0, 0), pady=0):
    if border_color:
        wrap = tk.Frame(parent, bg=border_color, padx=1, pady=1)
        wrap.pack(side=side, padx=padx, pady=pady)
        tk.Button(wrap, text=text, bg=bg, fg=fg,
                  relief="flat", cursor="hand2",
                  font=(MONO, 9, "bold" if bold else "normal"),
                  padx=12, pady=6, activebackground=BORDER,
                  activeforeground=fg, command=command).pack()
    else:
        tk.Button(parent, text=text, bg=bg, fg=fg,
                  relief="flat", cursor="hand2",
                  font=(MONO, 9, "bold" if bold else "normal"),
                  padx=12, pady=6, activebackground=BORDER,
                  activeforeground=FG, command=command
                  ).pack(side=side, padx=padx, pady=pady)


def make_log(parent, height=8):
    """Returns (frame, log_fn). log_fn(msg, tag='') appends to log widget."""
    frame = tk.Frame(parent, bg=CARD)
    t = tk.Text(frame, bg=CARD, fg=FG_MID,
                font=(MONO, 8), relief="flat",
                height=height, bd=0, padx=8, pady=6,
                state="disabled", wrap="word")
    sb = tk.Scrollbar(frame, command=t.yview,
                      bg=CARD, troughcolor=CARD, relief="flat", bd=0, width=5)
    t.config(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(side="left", fill="both", expand=True)
    t.tag_config("ok",  foreground=GREEN)
    t.tag_config("err", foreground=RED)
    t.tag_config("dim", foreground=FG_DIM)
    t.tag_config("hi",  foreground=ACCENT2)

    def log(msg, tag=""):
        t.config(state="normal")
        t.insert("end", msg + "\n", tag)
        t.see("end")
        t.config(state="disabled")

    return frame, log


def entry(parent, textvariable=None, width=None, **kw):
    e = tk.Entry(parent,
                 textvariable=textvariable,
                 bg=CARD, fg=FG, insertbackground=ACCENT,
                 relief="flat", font=(MONO, 10), bd=0,
                 highlightthickness=1,
                 highlightbackground=BORDER,
                 highlightcolor=ACCENT,
                 **({"width": width} if width else {}),
                 **kw)
    return e
