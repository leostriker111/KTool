"""Displays insertables: 7, 14 y 16 segmentos, barra de 10 LEDs y LED.

Cada segmento tiene un nombre que lo conecta con la salida del mismo nombre;
se enciende segun la fila activa de la tabla (relight). La geometria de los
segmentos sale de ktool/segmentos.py, la misma que dibuja el documento.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, simpledialog
from .. import theme
from .. import segmentos as seg

TITULOS = {
    "7seg": "7 segmentos",
    "14seg": "14 segmentos",
    "16seg": "16 segmentos",
    "barra10": "Barra de 10 LEDs",
    "led": "LED",
}

# Tamano de letra de los nombres dentro de cada segmento: en 14 y 16 los
# segmentos son mas delgados y los nombres de dos letras (g1, a2) no caben a 8.
LETRA_NOMBRE = {"7seg": 8, "14seg": 7, "16seg": 7, "barra10": 7, "led": 9}


def nombres_por_omision(kind):
    """Los nombres con que nace cada display, en el orden en que se dibujan.

    Existe para comparar contra los nombres guardados en un proyecto."""
    if kind == "led":
        return ["L"]
    poligonos, _ancho, _alto = seg.geometria(kind)
    return [nombre for nombre, _pts in poligonos]


class DisplayWidget:
    """Display que enciende segun el estado activo de la tabla.

    Cada segmento/LED tiene una etiqueta (editable con clic) que lo conecta con
    la salida del mismo nombre. `nombres` (opcional) son los nombres guardados
    en un proyecto, en el orden de nombres_por_omision(kind); si no coinciden
    en cantidad se ignoran.
    """

    def __init__(self, app, parent, kind, nombres=None):
        if kind not in TITULOS:
            raise ValueError(f"tipo de display desconocido: {kind!r}")
        self.app = app
        self.kind = kind
        self.segments = []  # [{'name','poly','text','tag'}]
        self.frame = ttk.Frame(parent, relief="ridge", borderwidth=2, padding=3)
        self.frame.pack(side=tk.TOP, fill=tk.X, pady=4)
        head = ttk.Frame(self.frame)
        head.pack(fill=tk.X)
        ttk.Label(head, text=TITULOS[kind], font=("", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(head, text="x", width=2, command=self.remove).pack(side=tk.RIGHT)
        if kind == "led":
            poligonos, w, h = [], 86, 96
        else:
            poligonos, w, h = seg.geometria(kind)
        self.canvas = tk.Canvas(self.frame, width=w, height=h, bg=theme.DISP_BG,
                                highlightthickness=0)
        self.canvas.pack()
        if kind == "led":
            self._draw_led()
        else:
            self._draw_segments(poligonos, h)
        if nombres is not None and len(nombres) == len(self.segments):
            for s, nombre in zip(self.segments, nombres):
                self._poner_nombre(s, str(nombre))

    @staticmethod
    def _centroid(poly):
        xs, ys = poly[0::2], poly[1::2]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    def _add_seg(self, name, poly_id, text_id, tag):
        s = {"name": name, "poly": poly_id, "text": text_id, "tag": tag}
        self.segments.append(s)
        self.canvas.tag_bind(tag, "<Button-1>", lambda e, s=s: self._rename(s))

    def _draw_segments(self, poligonos, alto):
        """Un poligono por segmento con su nombre encima. En la barra el nombre
        va debajo de cada LED: dentro no cabe."""
        letra = ("Consolas", LETRA_NOMBRE[self.kind], "bold")
        for i, (name, poly) in enumerate(poligonos):
            tag = f"s{i}"
            pid = self.canvas.create_polygon(poly, fill=theme.SEG_OFF, outline="#000",
                                             tags=(tag,))
            cx, cy = self._centroid(poly)
            if self.kind == "barra10":
                cy = alto - 12
            elif name == seg.PUNTO:
                cy = cy - 14       # el nombre del punto arriba del punto, no encima
            tid = self.canvas.create_text(cx, cy, text=name, fill=theme.NAME_FG,
                                          font=letra, tags=(tag,))
            self._add_seg(name, pid, tid, tag)

    def _draw_led(self):
        pid = self.canvas.create_oval(18, 14, 68, 64, fill=theme.SEG_OFF, outline="#000",
                                      width=2, tags=("L",))
        tid = self.canvas.create_text(43, 80, text="L", fill=theme.NAME_FG,
                                      font=("Consolas", LETRA_NOMBRE["led"], "bold"), tags=("L",))
        self._add_seg("L", pid, tid, "L")

    def _poner_nombre(self, s, nombre):
        s["name"] = nombre
        self.canvas.itemconfig(s["text"], text=nombre)

    def _rename(self, s):
        new = simpledialog.askstring(
            "Nombre del segmento/LED",
            "Se conecta con la salida del mismo nombre:",
            initialvalue=s["name"], parent=self.app.root,
        )
        if not new or not new.strip():
            return
        self._poner_nombre(s, new.strip())
        self.app._refresh_displays()

    def relight(self, name_value):
        for s in self.segments:
            on = name_value.get(s["name"]) == 1
            self.canvas.itemconfig(s["poly"], fill=theme.SEG_ON if on else theme.SEG_OFF)
            # en la barra el nombre va fuera del LED, sobre el fondo negro
            if self.kind == "barra10":
                continue
            self.canvas.itemconfig(s["text"], fill="#0a0a0a" if on else theme.NAME_FG)

    def nombres(self):
        """Los nombres actuales, en el orden de nombres_por_omision(kind)."""
        return [s["name"] for s in self.segments]

    def a_dict(self):
        """Lo que se guarda en el proyecto: el tipo y los nombres de los segmentos.

        Existe porque el usuario renombra segmentos para conectarlos con sus
        salidas, y eso se perdia al guardar solo el tipo."""
        return {"kind": self.kind, "nombres": self.nombres()}

    def remove(self):
        self.frame.destroy()
        if self in self.app.displays:
            self.app.displays.remove(self)


def leer_display(datos):
    """(kind, nombres) de una entrada de la lista "displays" de un proyecto.

    Existe para abrir los dos formatos: el viejo guardaba solo el tipo ("7seg")
    y el nuevo guarda {"kind": ..., "nombres": [...]}. Devuelve None si el tipo
    no existe en esta version (asi un proyecto nuevo abre en una version vieja
    sin romperse, y al reves).
    """
    if isinstance(datos, dict):
        kind = datos.get("kind", "7seg")
        nombres = datos.get("nombres")
    else:
        kind, nombres = datos, None
    if kind not in TITULOS:
        return None
    if not isinstance(nombres, list):
        nombres = None
    return kind, nombres


def display_desde_dict(app, parent, datos):
    """Crea el DisplayWidget de una entrada guardada, o devuelve None si el tipo
    no se conoce. Existe para que app.aplicar no tenga que saber el formato."""
    leido = leer_display(datos)
    if leido is None:
        return None
    kind, nombres = leido
    return DisplayWidget(app, parent, kind, nombres=nombres)


def display_de_salidas(salidas):
    """El display que corresponde a una tabla por los nombres de sus salidas:
    a1 es de 16 segmentos, g1 sin a1 de 14, a..g de 7 y L0..L9 la barra.
    None si la tabla no es de un display."""
    nombres = set(salidas)
    if {"a1", "a2", "g1", "g2"} <= nombres:
        return "16seg"
    if {"a", "g1", "g2"} <= nombres:
        return "14seg"
    if set("abcdefg") <= nombres:
        return "7seg"
    if {f"L{k}" for k in range(10)} <= nombres:
        return "barra10"
    return None
