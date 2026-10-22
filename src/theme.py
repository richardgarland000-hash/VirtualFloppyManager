"""Color theme for the whole interface (ttk "clam" base with a light palette).

Button styles: Accent (blue), Success (green), Danger (red), Warning (amber),
Slate (dark grey) and the default neutral TButton.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---- palette -------------------------------------------------------------
BG = "#eef2f7"
SURFACE = "#ffffff"
SURFACE_ALT = "#f4f7fb"
TEXT = "#1e293b"
MUTED = "#64748b"
BORDER = "#c3cfdd"

#HEADER = "#1e3a8a"
HEADER = "#1e293b"
HEADER_TEXT = "#ffffff"
HEADER_SUB = "#bfdbfe"

ACCENT = "#2563eb"
ACCENT_DARK = "#1e40af"
SELECTION = "#dbeafe"
SELECTION_TEXT = "#1e3a8a"

SUCCESS = "#15803d"
WARNING = "#b45309"
DANGER = "#b91c1c"
SUCCESS_BORDER = "#16a34a"
WARNING_BORDER = "#d97706"
DANGER_BORDER = "#dc2626"
READ_ONLY_TEXT = "#92400e"

DISABLED_BG = "#e2e8f0"
DISABLED_FG = "#94a3b8"
SLATE = "#475569"

FONT = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 9, "bold")

# name -> (base, hover, pressed)
BUTTONS = {
    "Accent.TButton": ("#2563eb", "#1d4ed8", "#1e40af"),
    "Success.TButton": ("#16a34a", "#15803d", "#166534"),
    "Danger.TButton": ("#dc2626", "#b91c1c", "#991b1b"),
    "Warning.TButton": ("#d97706", "#b45309", "#92400e"),
    "Slate.TButton": ("#475569", "#334155", "#1e293b"),
}


def _button(style, name, base, hover, down, fg):
    style.configure(name, background=base, foreground=fg, bordercolor=base, lightcolor=base,
                    darkcolor=base, focuscolor=base, padding=(12, 5), relief="flat", font=FONT)
    states = [("disabled", DISABLED_BG), ("pressed", down), ("active", hover)]
    style.map(name, background=states, bordercolor=states, lightcolor=states, darkcolor=states,
              foreground=[("disabled", DISABLED_FG)])


def style_menu(menu):
    menu.configure(background=SURFACE, foreground=TEXT, activebackground=ACCENT,
                   activeforeground="#ffffff", disabledforeground=DISABLED_FG,
                   relief="flat", borderwidth=1, font=FONT)


def apply_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=BG)

    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=FONT[0], size=FONT[1])
        except tk.TclError:
            pass

    # Drop-down lists of comboboxes are plain Tk listboxes; colour them via the option database.
    root.option_add("*TCombobox*Listbox.background", SURFACE)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", SELECTION)
    root.option_add("*TCombobox*Listbox.selectForeground", SELECTION_TEXT)
    root.option_add("*TCombobox*Listbox.font", FONT)

    style.configure(".", background=BG, foreground=TEXT, fieldbackground=SURFACE,
                    bordercolor=BORDER, troughcolor=DISABLED_BG, font=FONT,
                    selectbackground=SELECTION, selectforeground=SELECTION_TEXT)

    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Status.TLabel", foreground=MUTED)
    style.configure("StatusSuccess.TLabel", foreground=SUCCESS, font=FONT_BOLD)
    style.configure("StatusWarn.TLabel", foreground=WARNING, font=FONT_BOLD)
    style.configure("StatusError.TLabel", foreground=DANGER, font=FONT_BOLD)

    style.configure("TLabelframe", background=BG, bordercolor=BORDER, lightcolor=BG, darkcolor=BG)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT_DARK, font=FONT_BOLD)

    _button(style, "TButton", "#e2e8f0", "#cbd5e1", "#94a3b8", TEXT)
    style.configure("TButton", bordercolor=BORDER)
    for name, (base, hover, down) in BUTTONS.items():
        _button(style, name, base, hover, down, "#ffffff")

    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(widget, fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER,
                        lightcolor=SURFACE, darkcolor=SURFACE, insertcolor=TEXT, padding=4,
                        arrowcolor=ACCENT_DARK, selectbackground=SELECTION,
                        selectforeground=SELECTION_TEXT)
        style.map(widget,
                  bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
                  darkcolor=[("focus", ACCENT)],
                  fieldbackground=[("disabled", DISABLED_BG), ("readonly", SURFACE)],
                  foreground=[("disabled", DISABLED_FG)])
    style.configure("TCombobox", background="#e2e8f0")
    style.map("TCombobox", background=[("active", "#cbd5e1")],
              selectbackground=[("readonly", SURFACE)], selectforeground=[("readonly", TEXT)])

    style.configure("TCheckbutton", background=BG, foreground=TEXT, indicatorbackground=SURFACE,
                    indicatorforeground=ACCENT, upperbordercolor=BORDER, lowerbordercolor=BORDER)
    style.map("TCheckbutton", background=[("active", BG)],
              indicatorbackground=[("disabled", DISABLED_BG)],
              foreground=[("disabled", DISABLED_FG)])

    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                    rowheight=26, bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE)
    style.map("Treeview", background=[("selected", SELECTION)],
              foreground=[("selected", SELECTION_TEXT)])
    style.configure("Treeview.Heading", background=HEADER, foreground=HEADER_TEXT, font=FONT_BOLD,
                    padding=(6, 5), relief="flat", bordercolor=HEADER, lightcolor=HEADER,
                    darkcolor=HEADER)
    style.map("Treeview.Heading", background=[("active", ACCENT)])

    style.configure("Vertical.TScrollbar", background="#cbd5e1", troughcolor=BG, bordercolor=BG,
                    arrowcolor=MUTED, lightcolor="#cbd5e1", darkcolor="#cbd5e1")
    style.map("Vertical.TScrollbar", background=[("active", "#94a3b8")])

    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=DISABLED_BG,
                    bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)
