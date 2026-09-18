"""Interfaz grafica (Tkinter): tabla con seleccion multiple, multiples salidas y notas."""

from __future__ import annotations

import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from ..core import table
from ..core.table import TruthTable, default_vars, MIN_VARS, MAX_VARS, MAX_OUTPUTS
from ..core import ast as expr
from ..core.simplify import solve_output, shared_terms
from ..render.report import Options, build_report, save_report
from ..render import codegen
from .displays import DisplayWidget

from .. import theme

REPO_URL = "https://github.com/leostriker111/ktool"

CYCLE = {0: 1, 1: "x", "x": 0}

SHORTCUTS = [
    ("Clic en celda", "Selecciona esa celda"),
    ("Arrastrar", "Selecciona un rango de celdas"),
    ("Shift + clic / arrastrar", "Agrega a la seleccion"),
    ("1 / 0 / x", "Pone ese valor en todas las seleccionadas"),
    ("Doble clic", "Cambia el valor de una sola celda (0->1->x)"),
    ("Ctrl + C", "Copia la seleccion (formato Excel: TSV)"),
    ("Ctrl + V", "Pega desde el portapapeles"),
    ("Ctrl + X", "Corta (copia y pone 0)"),
    ("Ctrl + A", "Selecciona toda la tabla"),
    ("Esc", "Quita la seleccion"),
    ("Clic en encabezado de salida", "Renombra la salida"),
]

GUIDE = (
    "ktool simplifica logica digital.\n\n"
    "1. Elige cuantas variables (2-6) y cuantas salidas (1-10).\n"
    "2. Llena la tabla: cada celda cicla 0 -> 1 -> x con doble clic, o\n"
    "   selecciona varias y presiona 1, 0 o x.\n"
    "3. Tambien puedes escribir una expresion (ej: A'B + C) y llenar una\n"
    "   columna evaluandola.\n"
    "4. 'Ecuaciones' muestra SOP, POS, XOR/XNOR y la mejor por costo.\n"
    "5. 'Generar documento' arma un HTML con mapas de Karnaugh, circuitos,\n"
    "   el circuito completo con compuertas compartidas y las ecuaciones en\n"
    "   varios lenguajes (Verilog, VHDL, ABEL, Logisim, C, ...).\n\n"
    "Renombra una salida haciendo clic en su encabezado."
)


def _default_name(i, k):
    return "Y" if k == 1 else f"Y{i + 1}"


def _parse_fill_number(text, rows):
    """Numero -> vector de 0/1 de largo 'rows' (binario de izq a der = fila 0..2^n-1).
    Acepta 0b.., 0x.., b.., h.., d.. y decimal pelon. None si no parece numero."""
    t = text.strip().lower().replace(" ", "")
    if not t:
        return None
    if t.startswith("0b"):
        base, digits = 2, t[2:]
    elif t.startswith("0x"):
        base, digits = 16, t[2:]
    elif t.startswith("b") and len(t) > 1 and all(c in "01" for c in t[1:]):
        base, digits = 2, t[1:]
    elif t.startswith("h") and len(t) > 1:
        base, digits = 16, t[1:]
    elif t.startswith("d") and t[1:].isdigit():
        base, digits = 10, t[1:]
    elif t.isdigit():
        base, digits = 10, t
    else:
        return None
    try:
        val = int(digits, base)
    except ValueError:
        return None
    if val < 0 or val >= (1 << rows):
        raise ValueError(f"el numero no cabe en {rows} bits (las filas de la tabla)")
    return [int(c) for c in format(val, f"0{rows}b")]


class App:
    def __init__(self, root):
        self.root = root
        root.title("ktool - simplificador de logica digital")
        root.geometry("1120x740")

        self.nvars = tk.IntVar(value=3)
        self.nouts = tk.IntVar(value=1)
        self.notes_on = tk.BooleanVar(value=False)
        self.form = tk.StringVar(value="auto")

        self.output_names = ["Y"]
        self.values = []                 # values[oi][row]
        self.cell_widget = {}            # (oi,row) -> Label
        self.widget_cell = {}            # Label -> (oi,row)
        self.note_entries = {}           # row -> Entry
        self.out_headers = {}            # oi -> Label
        self.selected = set()
        self.drag_anchor = None
        self.drag_base = set()
        self.cursor = None               # (oi,row) celda activa para teclado
        self._rebuilding = False
        self.displays = []               # DisplayWidget insertados

        self._build_menu()
        self._build_controls()
        self._build_table_area()
        self._build_bottom()
        self._bind_keys()
        self.rebuild_table()

    # ---------- menu ----------
    def _build_menu(self):
        menubar = tk.Menu(self.root)

        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label="Generar documento", command=self.generate)
        m_file.add_separator()
        m_file.add_command(label="Salir", command=self.root.destroy)
        menubar.add_cascade(label="Archivo", menu=m_file)

        m_edit = tk.Menu(menubar, tearoff=0)
        m_edit.add_command(label="Copiar", command=self.copy)
        m_edit.add_command(label="Pegar", command=self.paste)
        m_edit.add_command(label="Cortar", command=self.cut)
        m_edit.add_separator()
        m_edit.add_command(label="Seleccionar todo", command=self.select_all)
        m_edit.add_command(label="Limpiar valores", command=self.clear_values)
        menubar.add_cascade(label="Editar", menu=m_edit)

        m_ins = tk.Menu(menubar, tearoff=0)
        m_disp = tk.Menu(m_ins, tearoff=0)
        m_disp.add_command(label="7 segmentos", command=lambda: self.insert_display("7seg"))
        m_disp.add_command(label="LED", command=lambda: self.insert_display("led"))
        m_ins.add_cascade(label="Display", menu=m_disp)
        m_ins.add_separator()
        m_ins.add_command(label="Quitar todos", command=self.clear_displays)
        menubar.add_cascade(label="Insertar", menu=m_ins)

        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label="Guia rapida", command=self.show_guide)
        m_help.add_command(label="Atajos de teclado", command=self.show_shortcuts)
        m_help.add_separator()
        m_help.add_command(label="Repositorio (GitHub)", command=lambda: webbrowser.open(REPO_URL))
        m_help.add_command(label="README", command=lambda: webbrowser.open(REPO_URL + "#readme"))
        menubar.add_cascade(label="Ayuda", menu=m_help)

        self.root.config(menu=menubar)

    # ---------- controles ----------
    def _build_controls(self):
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(bar, text="Variables:").pack(side=tk.LEFT)
        self.sp_vars = ttk.Spinbox(bar, from_=MIN_VARS, to=MAX_VARS, width=3, textvariable=self.nvars)
        self.sp_vars.pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(bar, text="Salidas:").pack(side=tk.LEFT)
        self.sp_outs = ttk.Spinbox(bar, from_=1, to=MAX_OUTPUTS, width=3, textvariable=self.nouts)
        self.sp_outs.pack(side=tk.LEFT, padx=(2, 6))
        ttk.Button(bar, text="Aplicar", command=self.apply_dims).pack(side=tk.LEFT, padx=(0, 12))
        for sp in (self.sp_vars, self.sp_outs):
            sp.bind("<Return>", self.apply_dims)
            sp.bind("<KP_Enter>", self.apply_dims)

        ttk.Checkbutton(bar, text="Notas", variable=self.notes_on,
                        command=self.rebuild_table).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(bar, text="Forma:").pack(side=tk.LEFT)
        ttk.OptionMenu(bar, self.form, "auto", "auto", "sop", "pos", "both").pack(
            side=tk.LEFT, padx=(2, 12))

        ttk.Label(bar, text="Poner:").pack(side=tk.LEFT)
        for val, txt in ((1, "1"), (0, "0"), ("x", "x")):
            ttk.Button(bar, text=txt, width=2,
                       command=lambda v=val: self.apply_value(v)).pack(side=tk.LEFT, padx=1)

        ttk.Button(bar, text="Ecuaciones", command=self.show_equations).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Button(bar, text="Generar documento", command=self.generate).pack(side=tk.LEFT, padx=4)

        bar2 = ttk.Frame(self.root, padding=(8, 0, 8, 6))
        bar2.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(bar2, text="Expresion:").pack(side=tk.LEFT)
        self.expr_entry = ttk.Entry(bar2, width=40)
        self.expr_entry.pack(side=tk.LEFT, padx=4)
        self.expr_entry.insert(0, "A'B + C")
        self.expr_entry.bind("<Return>", lambda e: self.fill_from_expr())
        ttk.Label(bar2, text="-> salida:").pack(side=tk.LEFT)
        self.expr_target = ttk.Combobox(bar2, width=5, state="readonly")
        self.expr_target.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Evaluar y llenar", command=self.fill_from_expr).pack(side=tk.LEFT)
        ttk.Label(bar2, text="  traducir a:").pack(side=tk.LEFT)
        self.translate_lang = ttk.Combobox(bar2, width=10, state="readonly",
                                            values=["Todos"] + codegen.LANG_ORDER)
        self.translate_lang.set("Verilog")
        self.translate_lang.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Traducir", command=self.translate_expr).pack(side=tk.LEFT)
        ttk.Label(bar2, text="   expresion (A'B+C) o numero (b1011, h4D, d77) | flechas y Enter navegan | Enter en Salidas aplica",
                  foreground="#777").pack(side=tk.LEFT, padx=8)

    def _build_table_area(self):
        wrap = ttk.Frame(self.root)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8)

        # panel de displays a la derecha (Insertar > Display)
        disp = ttk.LabelFrame(wrap, text="Displays", padding=4)
        disp.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        self._disp_hint = ttk.Label(disp, text="menu Insertar > Display",
                                    foreground="#999", wraplength=150)
        self._disp_hint.pack(pady=2)
        self.disp_inner = ttk.Frame(disp)
        self.disp_inner.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(wrap)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(left, highlightthickness=0, takefocus=True)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.table_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.table_frame, anchor="nw")
        self.table_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        # clic en zona muerta (fuera de las celdas) -> deselecciona
        self.canvas.bind("<Button-1>", lambda e: self._dead_click())
        self.table_frame.bind("<Button-1>", lambda e: self._dead_click())

    def _dead_click(self):
        self.canvas.focus_set()
        self.clear_selection()

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # ---------- displays ----------
    def insert_display(self, kind):
        self.displays.append(DisplayWidget(self, self.disp_inner, kind))
        self._disp_hint.pack_forget()
        self._refresh_displays()

    def clear_displays(self):
        for d in list(self.displays):
            d.remove()
        self._disp_hint.pack(pady=2)

    def _active_row(self):
        if self.cursor:
            return self.cursor[1]
        if self.selected:
            return min(r for _, r in self.selected)
        return 0

    def _name_values(self):
        if not self.values:
            return {}
        row = self._active_row()
        rows = len(self.values[0])
        if row >= rows:
            row = 0
        return {
            name: (1 if self.values[oi][row] == 1 else 0)
            for oi, name in enumerate(self.output_names)
        }

    def _refresh_displays(self):
        if not self.displays:
            return
        nv = self._name_values()
        for d in self.displays:
            d.relight(nv)

    def _build_bottom(self):
        frame = ttk.LabelFrame(self.root, text="Resultados", padding=6)
        frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=6)
        self.result = tk.Text(frame, height=9, font=("Consolas", 10), wrap="none")
        self.result.pack(fill=tk.X)

    def _bind_keys(self):
        r = self.root
        for key in ("1", "0", "x", "X"):
            r.bind(f"<KeyPress-{key}>", self._on_value_key)
        r.bind("<Control-c>", lambda e: self._guarded(self.copy))
        r.bind("<Control-C>", lambda e: self._guarded(self.copy))
        r.bind("<Control-v>", lambda e: self._guarded(self.paste))
        r.bind("<Control-V>", lambda e: self._guarded(self.paste))
        r.bind("<Control-x>", lambda e: self._guarded(self.cut))
        r.bind("<Control-X>", lambda e: self._guarded(self.cut))
        r.bind("<Control-a>", lambda e: self._guarded(self.select_all))
        r.bind("<Control-A>", lambda e: self._guarded(self.select_all))
        r.bind("<Escape>", lambda e: self.clear_selection())
        for sym in ("Up", "Down", "Left", "Right"):
            r.bind(f"<{sym}>", self._on_arrow)
        r.bind("<Return>", self._on_enter)
        r.bind("<KP_Enter>", self._on_enter)

    # ---------- navegacion con teclado ----------
    def _dims(self):
        rows = len(self.values[0]) if self.values else 0
        return len(self.values), rows  # (columnas, filas)

    def _move_to(self, oi, row):
        k, rows = self._dims()
        if k == 0 or rows == 0:
            return
        oi = max(0, min(k - 1, oi))
        row = max(0, min(rows - 1, row))
        self.cursor = (oi, row)
        self._set_selection({(oi, row)})
        self.canvas.focus_set()
        self._ensure_visible(oi, row)

    def _on_arrow(self, event):
        if self._entry_focused():
            return
        d = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}[event.keysym]
        base = self.cursor or (0, 0)
        self._move_to(base[0] + d[0], base[1] + d[1])
        return "break"

    def _on_enter(self, event):
        if self._entry_focused():
            return
        k, rows = self._dims()
        if not k or not rows:
            return
        if self.cursor is None:
            self._move_to(0, 0)
            return
        oi, row = self.cursor
        row += 1
        if row >= rows:           # bajo de columna -> tope de la siguiente
            row, oi = 0, oi + 1
        if oi >= k:               # ya no hay columnas -> deselecciona
            self.cursor = None
            self.clear_selection()
        else:
            self._move_to(oi, row)
        return "break"

    def _ensure_visible(self, oi, row):
        w = self.cell_widget.get((oi, row))
        if not w:
            return
        self.table_frame.update_idletasks()
        total = self.table_frame.winfo_height() or 1
        cy, ch = w.winfo_y(), w.winfo_height()
        top = self.canvas.canvasy(0)
        view = self.canvas.winfo_height()
        if cy < top:
            self.canvas.yview_moveto(cy / total)
        elif cy + ch > top + view:
            self.canvas.yview_moveto(max(0, (cy + ch - view)) / total)

    def apply_dims(self, event=None):
        if self._rebuilding:
            return "break"
        self.rebuild_table()
        return "break"

    # ---------- foco / teclas ----------
    def _entry_focused(self):
        w = self.root.focus_get()
        return isinstance(w, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox))

    def _guarded(self, fn):
        if self._entry_focused():
            return
        fn()

    def _on_value_key(self, event):
        if self._entry_focused():
            return
        ch = event.char.lower()
        if ch in ("1", "0"):
            self.apply_value(int(ch))
        elif ch == "x":
            self.apply_value("x")

    # ---------- construccion de tabla ----------
    def _sync_names(self, k):
        names = []
        for i in range(k):
            if i < len(self.output_names):
                names.append(self.output_names[i])
            else:
                names.append(_default_name(i, k))
        self.output_names = names

    def rebuild_table(self):
        try:
            n = max(MIN_VARS, min(MAX_VARS, int(self.nvars.get())))
            k = max(1, min(MAX_OUTPUTS, int(self.nouts.get())))
        except (tk.TclError, ValueError):
            return
        self._rebuilding = True
        self.sp_vars.config(state="disabled")
        self.sp_outs.config(state="disabled")
        try:
            self.root.config(cursor="watch")
            self.root.update_idletasks()
        except tk.TclError:
            pass
        rows = 1 << n
        variables = default_vars(n)
        self._sync_names(k)
        self.cursor = None

        old = self.values
        self.values = []
        for oi in range(k):
            col = []
            for r in range(rows):
                v = old[oi][r] if oi < len(old) and r < len(old[oi]) else 0
                col.append(v)
            self.values.append(col)

        for w in self.table_frame.winfo_children():
            w.destroy()
        self.cell_widget.clear()
        self.widget_cell.clear()
        self.note_entries.clear()
        self.out_headers.clear()
        self.selected.clear()

        ttk.Label(self.table_frame, text="#", width=4, anchor="center",
                  relief="solid", borderwidth=1).grid(row=0, column=0, sticky="nsew")
        col = 1
        for v in variables:
            ttk.Label(self.table_frame, text=v, width=3, anchor="center",
                      relief="solid", borderwidth=1).grid(row=0, column=col, sticky="nsew")
            col += 1
        out_start = col
        for oi in range(k):
            lbl = tk.Label(self.table_frame, text=self.output_names[oi], width=4, anchor="center",
                           relief="solid", borderwidth=1, bg="#dde7f7", cursor="hand2")
            lbl.grid(row=0, column=col, sticky="nsew")
            lbl.bind("<Button-1>", lambda e, o=oi: self.rename_output(o))
            self.out_headers[oi] = lbl
            col += 1
        notes_col = col
        if self.notes_on.get():
            ttk.Label(self.table_frame, text="nota", width=10, anchor="center",
                      relief="solid", borderwidth=1).grid(row=0, column=col, sticky="nsew")

        for r in range(rows):
            gr = r + 1
            tk.Label(self.table_frame, text=str(r), width=4, relief="solid", borderwidth=1,
                     bg="#efefef", fg="#888").grid(row=gr, column=0, sticky="nsew")
            c = 1
            for b in TruthTable(n).bits(r):
                tk.Label(self.table_frame, text=str(b), width=3, relief="solid",
                         borderwidth=1, bg="#fbfbfb").grid(row=gr, column=c, sticky="nsew")
                c += 1
            for oi in range(k):
                v = self.values[oi][r]
                cell = tk.Label(self.table_frame, text=str(v), width=4, relief="solid",
                                borderwidth=1, bg=theme.CELL_BG[v], fg=theme.CELL_FG[v])
                cell.grid(row=gr, column=out_start + oi, sticky="nsew")
                cell.bind("<Button-1>", lambda e, o=oi, row=r: self.on_press(o, row, False))
                cell.bind("<Shift-Button-1>", lambda e, o=oi, row=r: self.on_press(o, row, True))
                cell.bind("<B1-Motion>", self.on_drag)
                cell.bind("<Double-Button-1>", lambda e, o=oi, row=r: self.on_double(o, row))
                self.cell_widget[(oi, r)] = cell
                self.widget_cell[cell] = (oi, r)
            if self.notes_on.get():
                e = ttk.Entry(self.table_frame, width=12)
                e.grid(row=gr, column=notes_col, sticky="nsew")
                self.note_entries[r] = e

        self.expr_target["values"] = self.output_names
        self.expr_target.current(0)

        self.sp_vars.config(state="normal")
        self.sp_outs.config(state="normal")
        try:
            self.root.config(cursor="")
        except tk.TclError:
            pass
        self._rebuilding = False
        self._refresh_displays()

    # ---------- seleccion ----------
    def _refresh_cell(self, oi, r):
        w = self.cell_widget.get((oi, r))
        if not w:
            return
        v = self.values[oi][r]
        if (oi, r) in self.selected:
            w.config(text=str(v), bg=theme.SEL_BG, fg=theme.SEL_FG)
        else:
            w.config(text=str(v), bg=theme.CELL_BG[v], fg=theme.CELL_FG[v])

    def _set_selection(self, new):
        diff = new ^ self.selected
        self.selected = set(new)
        for oi, r in diff:
            self._refresh_cell(oi, r)
        self._refresh_displays()

    def _rect(self, a, b):
        o1, r1 = a
        o2, r2 = b
        return {
            (o, r)
            for o in range(min(o1, o2), max(o1, o2) + 1)
            for r in range(min(r1, r2), max(r1, r2) + 1)
        }

    def on_press(self, oi, r, shift):
        self.canvas.focus_set()
        self.drag_anchor = (oi, r)
        self.cursor = (oi, r)
        if shift:
            self.drag_base = set(self.selected)
            self._set_selection(self.selected | {(oi, r)})
        else:
            self.drag_base = set()
            self._set_selection({(oi, r)})

    def on_drag(self, event):
        if not self.drag_anchor:
            return
        w = self.root.winfo_containing(event.x_root, event.y_root)
        cell = self.widget_cell.get(w)
        if cell:
            self._set_selection(self.drag_base | self._rect(self.drag_anchor, cell))

    def on_double(self, oi, r):
        v = CYCLE[self.values[oi][r]]
        self.values[oi][r] = v
        self._refresh_cell(oi, r)
        self._refresh_displays()

    def apply_value(self, val):
        if not self.selected:
            return
        for oi, r in self.selected:
            self.values[oi][r] = val
            self._refresh_cell(oi, r)
        self._refresh_displays()

    def select_all(self):
        rows = len(self.values[0]) if self.values else 0
        self._set_selection({(oi, r) for oi in range(len(self.values)) for r in range(rows)})

    def clear_selection(self):
        self._set_selection(set())

    def clear_values(self):
        for oi in range(len(self.values)):
            for r in range(len(self.values[oi])):
                self.values[oi][r] = 0
                self._refresh_cell(oi, r)
        self._refresh_displays()

    # ---------- portapapeles (formato Excel/TSV) ----------
    def _selection_bounds(self):
        ois = [o for o, _ in self.selected]
        rs = [r for _, r in self.selected]
        return min(ois), max(ois), min(rs), max(rs)

    def copy(self):
        if not self.selected:
            return
        o0, o1, r0, r1 = self._selection_bounds()
        lines = []
        for r in range(r0, r1 + 1):
            lines.append("\t".join(str(self.values[o][r]) for o in range(o0, o1 + 1)))
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))

    def cut(self):
        if not self.selected:
            return
        self.copy()
        for oi, r in self.selected:
            self.values[oi][r] = 0
            self._refresh_cell(oi, r)

    def paste(self):
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            return
        if not text:
            return
        if self.selected:
            o0, _, r0, _ = self._selection_bounds()
        else:
            o0, r0 = 0, 0
        rows = len(self.values[0])
        k = len(self.values)
        for di, line in enumerate(text.replace("\r", "").split("\n")):
            if line == "":
                continue
            for dj, tok in enumerate(line.split("\t")):
                t = tok.strip().lower()
                if t in ("1", "0"):
                    v = int(t)
                elif t in ("x", "-"):
                    v = "x"
                else:
                    continue
                o, r = o0 + dj, r0 + di
                if 0 <= o < k and 0 <= r < rows:
                    self.values[o][r] = v
        for oi in range(k):
            for r in range(rows):
                self._refresh_cell(oi, r)
        self._refresh_displays()

    # ---------- renombrar salida ----------
    def rename_output(self, oi):
        current = self.output_names[oi]
        new = simpledialog.askstring("Renombrar salida", "Nuevo nombre:",
                                     initialvalue=current, parent=self.root)
        if not new:
            return
        new = new.strip()
        if not new:
            return
        if new != current and new in self.output_names:
            messagebox.showerror("Nombre repetido", f"Ya existe una salida llamada {new!r}.")
            return
        self.output_names[oi] = new
        self.out_headers[oi].config(text=new)
        self.expr_target["values"] = self.output_names
        self._refresh_displays()

    # ---------- acciones ----------
    def _current_table(self):
        n = max(MIN_VARS, min(MAX_VARS, int(self.nvars.get())))
        variables = default_vars(n)
        outputs = {self.output_names[oi]: list(self.values[oi]) for oi in range(len(self.values))}
        notes = None
        if self.notes_on.get() and self.note_entries:
            rows = len(self.values[0])
            notes = [self.note_entries[r].get() if r in self.note_entries else "" for r in range(rows)]
        return TruthTable(n, variables, outputs, notes)

    def fill_from_expr(self):
        text = self.expr_entry.get().strip()
        if not text:
            return
        n = max(MIN_VARS, min(MAX_VARS, int(self.nvars.get())))
        variables = default_vars(n)
        rows = 1 << n
        target = self.expr_target.get()
        oi = self.output_names.index(target)

        # numero (b.. binario, h.. hex, d.. decimal, 0b/0x, o decimal pelon)
        try:
            nums = _parse_fill_number(text, rows)
        except ValueError as e:
            messagebox.showerror("Numero invalido", str(e))
            return
        if nums is not None:
            for r in range(rows):
                self.values[oi][r] = nums[r]
                self._refresh_cell(oi, r)
            self._refresh_displays()
            return

        try:
            # llena una columna de la tabla: las variables son letras sueltas
            ast = expr.parse(text, letras_sueltas=True)
            used = set()
            expr.collect_vars(ast, used)
            unknown = used - set(variables)
            if unknown:
                raise ValueError(f"variables fuera de A..{variables[-1]}: {', '.join(sorted(unknown))}")
        except Exception as e:
            messagebox.showerror("Entrada invalida", str(e))
            return
        for r in range(rows):
            env = {variables[k]: (r >> (n - 1 - k)) & 1 for k in range(n)}
            self.values[oi][r] = expr.evaluate(ast, env)
            self._refresh_cell(oi, r)
        self._refresh_displays()

    def translate_expr(self):
        text = self.expr_entry.get().strip()
        if not text:
            return
        name = self.expr_target.get() or "Y"
        try:
            ast = expr.parse(text)
        except Exception as e:
            messagebox.showerror("Expresion invalida", str(e))
            return
        choice = self.translate_lang.get()
        langs = codegen.LANG_ORDER if choice == "Todos" else [choice]
        lines = [f"Expresion: {text}", ""]
        for lang in langs:
            lines.append(f"[{lang}]")
            lines.append("  " + codegen.OPS[lang]["assign"].format(
                name=name, rhs=codegen.emit(ast, lang)))
            lines.append("")
        self._text_window(f"Traduccion -> {choice}", "\n".join(lines))

    def show_equations(self):
        table = self._current_table()
        sols = {name: solve_output(v, table.variables) for name, v in table.outputs.items()}
        lines = [f"{table.nvars} variables: {', '.join(table.variables)}", ""]
        for name, sol in sols.items():
            lines.append(f"[{name}]")
            lines.append(f"  SOP : {name} = {sol['sop'].equation}   ({sol['sop'].cost()[0]} comp, {sol['sop'].cost()[1]} lit)")
            lines.append(f"  POS : {name} = {sol['pos'].equation}   ({sol['pos'].cost()[0]} comp, {sol['pos'].cost()[1]} lit)")
            if sol["xor"]:
                lines.append(f"  XOR : {name} = {sol['xor'].equation}   ({sol['xor'].cost()[0]} comp, {sol['xor'].cost()[1]} lit)")
            lines.append(f"  best: {sol['best'].form.upper()} -> {name} = {sol['best'].equation}")
            lines.append("")
        if len(table.outputs) > 1:
            sh = shared_terms(sols, table.variables, "sop")
            if sh:
                lines.append("[terminos reutilizables (SOP)]")
                for d in sh:
                    lines.append(f"  {d['term']:<14} -> {', '.join(d['outputs'])}")
        self.result.delete("1.0", tk.END)
        self.result.insert("1.0", "\n".join(lines))

    def generate(self):
        table = self._current_table()
        opt = Options(form=self.form.get(), title="Resultados ktool")
        html = build_report(table, opt)
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML", "*.html")],
            initialfile="ktool_resultado.html",
        ) or None
        saved = save_report(html, path, open_browser=True)
        self.show_equations()
        messagebox.showinfo("Documento generado", f"Guardado en:\n{saved}")

    # ---------- ventanas de ayuda ----------
    def _text_window(self, title, content, width=70, height=18):
        win = tk.Toplevel(self.root)
        win.title(title)
        txt = tk.Text(win, wrap="word", width=width, height=height, font=("Consolas", 10),
                      padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", content)
        txt.config(state="disabled")
        ttk.Button(win, text="Cerrar", command=win.destroy).pack(pady=6)

    def show_guide(self):
        self._text_window("Guia rapida", GUIDE)

    def show_shortcuts(self):
        lines = ["Atajos de teclado y raton", ""]
        for keys, desc in SHORTCUTS:
            lines.append(f"  {keys:<28} {desc}")
        self._text_window("Atajos de teclado", "\n".join(lines), width=64, height=16)


def launch():
    root = tk.Tk()
    App(root)
    root.mainloop()
