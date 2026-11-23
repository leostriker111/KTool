"""Vista para diseñar una maquina de estados (FSM) dentro de la ventana.

No es flotante: es un Frame que se coloca encima de la tabla combinacional (con
boton Volver). Entrada por tablas (estados y transiciones), grafo en vivo y
preview de 7 segmentos del estado activo. Arma una `Machine` y la manda al mismo
motor que la CLI.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ..fsm import Machine, flipflops
from ..render.fsm_report import build_fsm_report, save_report
from ..render.fsm_diagram import _seg7_polys, _node_positions
from .. import io as ktio, segmentos, theme
from ..hw.configuracion import ConfigKit

_STATE_COLS = [("name", "nombre", 8), ("code", "codigo", 7),
               ("label", "etiq.", 6), ("out", "salida (abc..g)", 14)]
_TRANS_COLS = [("from", "origen", 8), ("in", "entrada", 7), ("to", "destino", 8)]

_DEMO = {
    "name": "Contador 0-3", "kind": "moore", "inputs": "",
    "state_bits": "Q1, Q0", "outputs": "", "ff": "T",
    "states": [{"name": "S0", "code": "00", "label": "0"},
               {"name": "S1", "code": "01", "label": "1"},
               {"name": "S2", "code": "10", "label": "2"},
               {"name": "S3", "code": "11", "label": "3"}],
    "transitions": [{"from": "S0", "in": "", "to": "S1"},
                    {"from": "S1", "in": "", "to": "S2"},
                    {"from": "S2", "in": "", "to": "S3"},
                    {"from": "S3", "in": "", "to": "S0"}],
}


def _caracter_de_etiqueta(etiqueta):
    """'12' -> 'C', '7' -> '7', 'A' -> 'A': lo que cabe en un solo display de 7
    segmentos, o None si la etiqueta no se puede mostrar asi."""
    texto = etiqueta.strip()
    if texto.isdigit() and int(texto) < 16:
        return "0123456789ABCDEF"[int(texto)]
    if len(texto) == 1 and texto.upper() in segmentos.soportados("7seg"):
        return texto.upper()
    return None


def _csv(text):
    return [t.strip() for t in text.split(",") if t.strip()]


class FsmView:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.frame = ttk.Frame(self.root, relief="ridge", borderwidth=2)
        self.state_rows = []
        self.trans_rows = []
        self._redraw_job = None
        self._inicial = None
        self.kit_config = ConfigKit()     # se guarda con la maquina y sale en el reporte
        self.con_kit = tk.BooleanVar(value=True)
        self._build()
        self._fill(_DEMO)

    # -- mostrar / ocultar (cubre la vista combinacional) --
    def show(self):
        self.frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frame.lift()
        self.frame.update_idletasks()
        self._redraw_graph()

    def hide(self):
        self.frame.place_forget()

    # -- construccion --
    def _build(self):
        head = ttk.Frame(self.frame, padding=8)
        head.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(head, text="← Volver", command=self.hide).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ttk.Label(head, text="Maquina de estados", font=("", 12, "bold")).grid(row=0, column=1, columnspan=2, sticky="w")

        self.e_name = self._cfg(head, "Nombre:", 1, 1, 40)
        self.cb_kind = ttk.Combobox(head, width=7, state="readonly", values=["moore", "mealy"])
        self.cb_kind.set("moore")
        ttk.Label(head, text="Tipo:").grid(row=1, column=3, sticky="e", padx=(10, 2))
        self.cb_kind.grid(row=1, column=4, sticky="w")
        self.cb_ff = ttk.Combobox(head, width=5, state="readonly", values=list(flipflops.KINDS))
        self.cb_ff.set("JK")
        ttk.Label(head, text="Flip-flop:").grid(row=1, column=5, sticky="e", padx=(10, 2))
        self.cb_ff.grid(row=1, column=6, sticky="w")

        self.e_inputs = self._cfg(head, "Entradas:", 2, 1, 18)
        self.e_bits = self._cfg(head, "Bits de estado:", 2, 3, 14)
        self.e_outputs = self._cfg(head, "Salidas:", 2, 5, 16)
        for e in (self.e_inputs, self.e_bits, self.e_outputs):
            e.bind("<KeyRelease>", self._on_edit)

        body = ttk.Frame(self.frame, padding=(8, 0))
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # panel derecho: grafo + display
        right = ttk.Frame(body)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        ttk.Label(right, text="Vista del grafo", font=("", 9, "bold")).pack(anchor="w")
        self.graph_canvas = tk.Canvas(right, width=360, height=320, bg="#ffffff",
                                      highlightthickness=1, highlightbackground="#ccc")
        self.graph_canvas.pack()
        self.graph_canvas.bind("<Configure>", lambda e: self._schedule_redraw())
        ttk.Label(right, text="Display del estado activo", font=("", 9, "bold")).pack(anchor="w", pady=(8, 0))
        self.seg_canvas = tk.Canvas(right, width=120, height=120, bg=theme.DISP_BG,
                                    highlightthickness=0)
        self.seg_canvas.pack(pady=2)
        self.seg_caption = ttk.Label(right, text="", foreground="#666")
        self.seg_caption.pack()

        # panel izquierdo: tablas
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.states_box = self._table(left, "Estados", _STATE_COLS,
                                      lambda: self._add_row(self.states_box, self.state_rows, _STATE_COLS))
        self.trans_box = self._table(left, "Transiciones", _TRANS_COLS,
                                     lambda: self._add_row(self.trans_box, self.trans_rows, _TRANS_COLS))

        foot = ttk.Frame(self.frame, padding=8)
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(foot, text="Generar reporte...", command=self.generate).pack(side=tk.LEFT)
        ttk.Button(foot, text="Escribir VHDL...", command=self.escribir_vhdl).pack(side=tk.LEFT,
                                                                                   padx=6)
        ttk.Button(foot, text="Kit de hardware...", command=self.abrir_kit).pack(side=tk.LEFT)
        ttk.Checkbutton(foot, text="Kit en el reporte", variable=self.con_kit).pack(
            side=tk.LEFT, padx=6)
        ttk.Separator(foot, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(foot, text="Contador...", command=self.contador).pack(side=tk.LEFT)
        ttk.Button(foot, text="Abrir...", command=self.load).pack(side=tk.LEFT, padx=6)
        ttk.Button(foot, text="Guardar...", command=self.save).pack(side=tk.LEFT)
        self.status = ttk.Label(foot, text="", foreground="#a00")
        self.status.pack(side=tk.LEFT, padx=12)

    def _cfg(self, parent, label, row, col, width):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="e", padx=(8, 2), pady=2)
        e = ttk.Entry(parent, width=width)
        e.grid(row=row, column=col + 1, sticky="w", pady=2)
        return e

    def _table(self, parent, title, cols, on_add):
        box = ttk.LabelFrame(parent, text=title, padding=4)
        box.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=4)
        header = ttk.Frame(box)
        header.pack(fill=tk.X)
        for _key, label, w in cols:
            ttk.Label(header, text=label, width=w, anchor="w",
                      font=("", 8, "bold")).pack(side=tk.LEFT, padx=1)
        ttk.Button(box, text="+ agregar", command=on_add).pack(side=tk.BOTTOM, anchor="w",
                                                               pady=(2, 0))
        # Las filas van en un lienzo con barra: un mod-16 con dos entradas son
        # 64 transiciones y no caben a la vista.
        zona = ttk.Frame(box)
        zona.pack(fill=tk.BOTH, expand=True)
        lienzo = tk.Canvas(zona, highlightthickness=0, height=120)
        barra = ttk.Scrollbar(zona, orient="vertical", command=lienzo.yview)
        lienzo.configure(yscrollcommand=barra.set)
        barra.pack(side=tk.RIGHT, fill=tk.Y)
        lienzo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rows = ttk.Frame(lienzo)
        lienzo.create_window((0, 0), window=rows, anchor="nw")
        rows.bind("<Configure>", lambda e: lienzo.configure(scrollregion=lienzo.bbox("all")))
        box._rows_frame = rows
        return box

    def _add_row(self, box, rows_list, cols, values=None):
        rf = ttk.Frame(box._rows_frame)
        rf.pack(fill=tk.X, pady=1)
        cells = {"_frame": rf}
        for key, _label, w in cols:
            e = ttk.Entry(rf, width=w)
            e.pack(side=tk.LEFT, padx=1)
            e.bind("<KeyRelease>", self._on_edit)
            e.bind("<FocusIn>", lambda ev, row=cells: self._on_focus(row))
            cells[key] = e
        ttk.Button(rf, text="x", width=2,
                   command=lambda: self._del_row(rows_list, cells)).pack(side=tk.LEFT)
        if values:
            for key, _l, _w in cols:
                cells[key].insert(0, values.get(key, ""))
        rows_list.append(cells)
        return cells

    def _del_row(self, rows_list, cells):
        cells["_frame"].destroy()
        if cells in rows_list:
            rows_list.remove(cells)
        self._schedule_redraw()

    # -- eventos --
    def _on_edit(self, _event=None):
        self._schedule_redraw()

    def _on_focus(self, row):
        if "out" in row:
            self._draw_7seg(row["out"].get().strip(),
                            row["label"].get().strip() or row["name"].get().strip())

    def _schedule_redraw(self):
        if self._redraw_job is not None:
            try:
                self.root.after_cancel(self._redraw_job)
            except Exception:
                pass
        self._redraw_job = self.root.after(350, self._redraw_graph)

    # -- grafo en vivo --
    def _redraw_graph(self):
        self._redraw_job = None
        c = self.graph_canvas
        c.delete("all")
        states = []
        for row in self.state_rows:
            nm = row["name"].get().strip()
            if not nm:
                continue
            states.append((nm, row["label"].get().strip() or nm, row["code"].get().strip()))
        if not states:
            return
        W = c.winfo_width() or 360
        H = c.winfo_height() or 320
        n = len(states)
        nr = 20
        R = max(46, min(W, H) / 2 - nr - 22)
        cx, cy = W / 2, H / 2
        pos = _node_positions(n, cx, cy, R)
        idx = {nm: i for i, (nm, _, _) in enumerate(states)}
        for row in self.trans_rows:
            src = row["from"].get().strip()
            dst = row["to"].get().strip()
            if src not in idx or dst not in idx:
                continue
            p1, p2 = pos[idx[src]], pos[idx[dst]]
            if src == dst:
                self._self_loop(c, p1, (cx, cy), nr)
            else:
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                d = math.hypot(dx, dy) or 1
                ux, uy = dx / d, dy / d
                c.create_line(p1[0] + ux * nr, p1[1] + uy * nr,
                              p2[0] - ux * nr, p2[1] - uy * nr,
                              arrow=tk.LAST, fill="#666", width=1.5)
        for i, (nm, label, code) in enumerate(states):
            x, y = pos[i]
            c.create_oval(x - nr, y - nr, x + nr, y + nr, fill="#eef4ff",
                          outline="#33518f", width=2)
            c.create_text(x, y - 4, text=label, font=("", 11, "bold"), fill="#1a2a52")
            if code:
                c.create_text(x, y + 9, text=code, font=("Consolas", 7), fill="#5a6a8a")

    def _self_loop(self, c, p, center, nr):
        ox, oy = p[0] - center[0], p[1] - center[1]
        d = math.hypot(ox, oy) or 1
        ox, oy = ox / d, oy / d
        tx, ty = -oy, ox
        a = (p[0] + nr * (ox * 0.4 + tx * 0.5), p[1] + nr * (oy * 0.4 + ty * 0.5))
        m = (p[0] + nr * 2.4 * ox, p[1] + nr * 2.4 * oy)
        b = (p[0] + nr * (ox * 0.4 - tx * 0.5), p[1] + nr * (oy * 0.4 - ty * 0.5))
        c.create_line(a[0], a[1], m[0], m[1], b[0], b[1], smooth=True,
                      arrow=tk.LAST, fill="#666")

    # -- preview 7 segmentos --
    def _draw_7seg(self, bits, caption):
        """El display del estado: sus salidas a..g si la maquina las tiene; si no
        (un contador), el numero de su etiqueta en hexadecimal, como lo mostraria
        un decodificador BCD/hex a 7 segmentos."""
        c = self.seg_canvas
        c.delete("all")
        segs = _csv(self.e_outputs.get()) or list("abcdefg")
        if not bits:
            caracter = _caracter_de_etiqueta(caption)
            if caracter is not None:
                encendidos = segmentos.segmentos(caracter, "7seg")
                segs = list("abcdefg")
                bits = "".join(str(encendidos[s]) for s in segs)
        sc = 0.6
        for name, poly in _seg7_polys():
            i = segs.index(name) if name in segs else -1
            on = 0 <= i < len(bits) and bits[i] == "1"
            pts = []
            for k in range(0, len(poly), 2):
                pts += [poly[k] * sc + 6, poly[k + 1] * sc + 6]
            c.create_polygon(pts, fill=theme.SEG_ON if on else theme.SEG_OFF, outline="#000")
        self.seg_caption.config(text=caption)

    # -- datos --
    def _to_dict(self):
        d = {
            "doc_type": "fsm",
            "name": self.e_name.get().strip() or "Maquina",
            "kind": self.cb_kind.get(),
            "inputs": _csv(self.e_inputs.get()),
            "state_bits": _csv(self.e_bits.get()),
            "outputs": _csv(self.e_outputs.get()),
            "states": [],
            "transitions": [],
        }
        for row in self.state_rows:
            nm = row["name"].get().strip()
            code = row["code"].get().strip()
            if not nm and not code:
                continue
            st = {"name": nm, "code": code}
            if row["label"].get().strip():
                st["label"] = row["label"].get().strip()
            if row["out"].get().strip():
                st["out"] = row["out"].get().strip()
            d["states"].append(st)
        for row in self.trans_rows:
            src = row["from"].get().strip()
            to = row["to"].get().strip()
            if not src and not to:
                continue
            d["transitions"].append({"from": src, "in": row["in"].get().strip(), "to": to})
        # el estado inicial de un contador (al que lleva el reset), si sigue existiendo
        if self._inicial and any(s["name"] == self._inicial for s in d["states"]):
            d["inicial"] = self._inicial
        return d

    def _machine(self):
        return Machine.from_dict(self._to_dict())

    def _fill(self, src):
        def join(v):
            return ", ".join(v) if isinstance(v, list) else str(v or "")
        self._inicial = src.get("inicial")
        # la configuracion del kit es de ESTA maquina: sus pines no sirven en otra
        self.kit_config = ConfigKit.desde_dict(src.get("kit"))
        self.e_name.delete(0, tk.END); self.e_name.insert(0, src.get("name", ""))
        self.cb_kind.set(src.get("kind") if src.get("kind") in ("moore", "mealy") else "moore")
        self.cb_ff.set(src.get("ff", "JK"))
        self.e_inputs.delete(0, tk.END); self.e_inputs.insert(0, join(src.get("inputs")))
        self.e_bits.delete(0, tk.END); self.e_bits.insert(0, join(src.get("state_bits")))
        self.e_outputs.delete(0, tk.END); self.e_outputs.insert(0, join(src.get("outputs")))
        for r in list(self.state_rows):
            r["_frame"].destroy()
        self.state_rows.clear()
        for r in list(self.trans_rows):
            r["_frame"].destroy()
        self.trans_rows.clear()
        for s in src.get("states", []):
            self._add_row(self.states_box, self.state_rows, _STATE_COLS, {
                "name": s.get("name", ""), "code": s.get("code", ""),
                "label": s.get("label", ""), "out": s.get("out", "")})
        for t in src.get("transitions", []):
            self._add_row(self.trans_box, self.trans_rows, _TRANS_COLS, {
                "from": t.get("from", ""), "in": t.get("in", ""), "to": t.get("to", "")})
        self._schedule_redraw()
        if self.state_rows:               # el display arranca en el primer estado
            self._on_focus(self.state_rows[0])

    # -- acciones --
    def cargar(self, fuente):
        """Muestra el editor con una maquina (desde Archivo > Abrir o Ejemplos)."""
        self._fill(fuente)
        self.show()

    def _portada(self):
        """La portada de la pestana Portada de la ventana, si se lleno algo."""
        datos = self.app.resultados.datos_portada()
        return datos if any(datos.values()) else None

    def generate(self):
        """El documento: diagrama, tablas, excitacion, ecuaciones, circuito y VHDL."""
        from .resultados import nombre_de_archivo
        self.status.config(text="")
        try:
            fuente = self._to_dict()
            machine = Machine.from_dict(fuente)
            html = build_fsm_report(machine, ff_kind=self.cb_ff.get(), fuente=fuente,
                                    portada=self._portada(), kit_html=self._kit_html(fuente))
        except (ValueError, KeyError) as e:
            self.status.config(text=f"Error: {e}")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".html", filetypes=[("HTML", "*.html")],
            initialfile=nombre_de_archivo(fuente["name"]) + ".html")
        if not path:
            return
        saved = save_report(html, path, open_browser=True)
        self.status.config(text=f"Reporte en {saved} (abierto en el navegador)", foreground="#555")

    def abrir_kit(self):
        """La misma ventana del kit que la de las tablas, con esta maquina."""
        from .kit_ventana import FuenteMaquina, VentanaKit
        try:
            Machine.from_dict(self._to_dict())
        except (ValueError, KeyError) as e:
            self.status.config(text=f"Error: {e}", foreground="#a00")
            return
        VentanaKit(self.root, self.kit_config, FuenteMaquina(self))

    def _kit_html(self, fuente):
        """La seccion del kit para el reporte, con el calculo del reloj de cada
        placa; vacia si no se palomeo 'Kit en el reporte'."""
        from ..hw import kit_fsm
        from ..render.report import seccion_kit
        if not self.con_kit.get() or not self.kit_config.elegidas:
            return ""
        armado = kit_fsm.armar(fuente, self.kit_config)
        return seccion_kit(armado, self.kit_config, kit_fsm.seccion_reloj(fuente, self.kit_config),
                           secuencial=True)

    def escribir_vhdl(self):
        """Los tres metodos (ecuaciones con el flip-flop elegido, tabla y estados)
        y el banco de prueba, en una carpeta."""
        from ..hw import vhdl_fsm
        self.status.config(text="")
        try:
            fuente = self._to_dict()
            Machine.from_dict(fuente)
        except (ValueError, KeyError) as e:
            self.status.config(text=f"Error: {e}", foreground="#a00")
            return
        carpeta = filedialog.askdirectory(title="Carpeta para el VHDL")
        if not carpeta:
            return
        try:
            nombres = vhdl_fsm.escribir(fuente, carpeta, self.cb_ff.get())
        except (ValueError, KeyError, OSError) as e:
            self.status.config(text=f"No se pudo escribir el VHDL: {e}", foreground="#a00")
            return
        self.status.config(text=f"En {carpeta}: {', '.join(nombres)}", foreground="#555")

    def contador(self):
        """Arma un contador (modulo, secuencia propia, modos por entradas X Y...)
        con fsm/contadores.py y lo pone en el editor."""
        DialogoContador(self)

    def save(self):
        try:
            d = self._to_dict()
            Machine.from_dict(d)  # valida antes de guardar
        except (ValueError, KeyError) as e:
            self.status.config(text=f"Error: {e}")
            return
        d["ff"] = self.cb_ff.get()
        d["kit"] = self.kit_config.a_dict()
        path = filedialog.asksaveasfilename(
            defaultextension=ktio.EXT,
            filetypes=[("Fuente ktool", "*.ktool.json"), ("JSON", "*.json")],
            initialfile="maquina" + ktio.EXT)
        if not path:
            return
        try:
            ktio.save(d, path)
        except OSError as e:
            self.status.config(text=f"No se pudo guardar: {e}")
            return
        messagebox.showinfo("Guardado", f"Fuente guardado en:\n{path}", parent=self.root)

    def load(self):
        path = filedialog.askopenfilename(
            filetypes=[("Fuente ktool", "*.ktool.json *.json"), ("Todos", "*.*")])
        if not path:
            return
        try:
            src = ktio.load(path)
        except (OSError, ValueError) as e:
            self.status.config(text=f"No se pudo abrir: {e}")
            return
        if ktio.doc_type(src) != "fsm":
            messagebox.showinfo("No es una maquina",
                                "Ese archivo es una tabla combinacional, no una maquina.",
                                parent=self.root)
            return
        self._fill(src)
        self.status.config(text=f"Cargado: {path}")


class DialogoContador:
    """Ventana para armar un contador: titulo, entradas de control y que hace
    con cada combinacion. Al dar Crear, el contador queda en el editor."""

    def __init__(self, vista):
        from .resultados import con_ejemplo
        self.vista = vista
        self.win = tk.Toplevel(vista.root)
        self.win.title("Contador")
        self.win.transient(vista.root)
        self.cuerpo = ttk.Frame(self.win, padding=12)
        self.cuerpo.pack(fill=tk.BOTH, expand=True)
        self._con_ejemplo = con_ejemplo

        ttk.Label(self.cuerpo, text="Titulo:").grid(row=0, column=0, sticky="w")
        self.titulo = tk.StringVar()
        e = ttk.Entry(self.cuerpo, textvariable=self.titulo, width=46)
        e.grid(row=0, column=1, columnspan=2, sticky="w", pady=2)
        con_ejemplo(e, self.titulo, "Ej. Contador mod-16 con X Y")

        ttk.Label(self.cuerpo, text="Entradas de control:").grid(row=1, column=0, sticky="w")
        self.entradas = tk.StringVar()
        e = ttk.Entry(self.cuerpo, textvariable=self.entradas, width=20)
        e.grid(row=1, column=1, sticky="w", pady=2)
        con_ejemplo(e, self.entradas, "Ej. X, Y (vacio = ninguna)")
        ttk.Button(self.cuerpo, text="Poner modos", command=self._poner_modos).grid(
            row=1, column=2, sticky="w", padx=4)

        ttk.Label(self.cuerpo, text="Flip-flops (bits):").grid(row=2, column=0, sticky="w")
        self.bits = tk.StringVar()
        e = ttk.Entry(self.cuerpo, textvariable=self.bits, width=20)
        e.grid(row=2, column=1, sticky="w", pady=2)
        con_ejemplo(e, self.bits, "Vacio = los justos")

        self.modos_marco = ttk.LabelFrame(self.cuerpo, text="Que hace con cada combinacion",
                                          padding=6)
        self.modos_marco.grid(row=3, column=0, columnspan=3, sticky="we", pady=(8, 0))
        self.modos = {}
        ttk.Label(self.cuerpo, foreground="#777", justify=tk.LEFT, text=(
            "Cada modo: una lista (4,7,2,6), un rango (0-15 sube, 12-0 baja),\n"
            "paro (se queda), reinicio (al primer numero) o set (todo a 1).\n"
            "Si un modo arranca desde un numero que no esta en su lista, salta al primero.")).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        botones = ttk.Frame(self.cuerpo)
        botones.grid(row=5, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(botones, text="Cancelar", command=self.win.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(botones, text="Crear", command=self.crear).pack(side=tk.RIGHT)
        self._poner_modos()

    def _nombres_de_entrada(self):
        return [x.strip() for x in self.entradas.get().split(",") if x.strip()]

    def _poner_modos(self):
        """Un cuadro por combinacion de entradas (o uno solo si no hay entradas).
        Lo ya escrito se conserva si la combinacion sigue existiendo."""
        anteriores = {c: v.get() for c, v in self.modos.items()}
        for w in self.modos_marco.winfo_children():
            w.destroy()
        entradas = self._nombres_de_entrada()
        if len(entradas) > 3:
            messagebox.showerror("Demasiadas entradas", "Hasta 3 entradas de control.",
                                 parent=self.win)
            return
        combos = [format(i, f"0{len(entradas)}b") for i in range(1 << len(entradas))] if entradas else [""]
        ejemplos = ["0-15", "paro", "reinicio", "15,12,9,6,3,0", "set", "0,2,4,6", "paro", "reinicio"]
        self.modos = {}
        for k, combo in enumerate(combos):
            etiqueta = (", ".join(f"{e}={b}" for e, b in zip(entradas, combo)) if entradas
                        else "Secuencia")
            ttk.Label(self.modos_marco, text=etiqueta + ":").grid(row=k, column=0, sticky="w")
            var = tk.StringVar(value=anteriores.get(combo, ""))
            e = ttk.Entry(self.modos_marco, textvariable=var, width=34)
            e.grid(row=k, column=1, sticky="w", padx=4, pady=1)
            self._con_ejemplo(e, var, "Ej. " + (ejemplos[k] if entradas else "4,7,2,6,0,3,5,1  o  12-0"))
            self.modos[combo] = var

    def crear(self):
        from ..fsm import contadores
        entradas = self._nombres_de_entrada()
        try:
            modos = {c: contadores.leer_modo(v.get()) for c, v in self.modos.items()}
            bits = int(self.bits.get()) if self.bits.get().strip() else None
            titulo = self.titulo.get().strip() or "Contador"
            fuente = contadores.contador(titulo, modos, entradas, bits=bits)
            fuente["ff"] = self.vista.cb_ff.get()
            Machine.from_dict(fuente)
        except ValueError as e:
            messagebox.showerror("No se pudo armar el contador", str(e), parent=self.win)
            return
        self.win.destroy()
        self.vista.cargar(fuente)
