"""Ventana Texto a segmentos: escribe un mensaje y sale su tabla de verdad.

La tabla la arma ktool/segmentos.py (proyecto_mensaje); esta ventana solo
junta las opciones, dibuja la vista previa y entrega el proyecto a quien la
abrio (al_crear), que lo carga en la ventana principal.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import theme
from .. import segmentos as seg

ESCALA = 0.4          # tamano de los digitos de la vista previa
ANCHO_VISTA = 640     # pixeles; los digitos que no caben pasan al renglon de abajo


class VentanaTextoASegmentos:
    """Ventana chica: texto, tipo de display y conexion; vista previa al
    teclear y boton Crear tabla. Los caracteres que no existen en el tipo
    elegido se avisan en una etiqueta gris, sin ventanas emergentes."""

    def __init__(self, padre, al_crear):
        from .resultados import con_ejemplo
        self.al_crear = al_crear
        self.win = tk.Toplevel(padre)
        self.win.title("Texto a segmentos")
        self.win.transient(padre)
        self.win.resizable(False, False)
        cuerpo = ttk.Frame(self.win, padding=12)
        cuerpo.pack(fill=tk.BOTH, expand=True)
        # el espacio que sobra (la vista previa es la mas ancha) va a la columna
        # de los controles, no a la de las etiquetas
        cuerpo.columnconfigure(1, weight=1)

        ttk.Label(cuerpo, text="Texto:").grid(row=0, column=0, sticky="w")
        self.texto = tk.StringVar()
        self.entrada = ttk.Entry(cuerpo, textvariable=self.texto, width=48)
        self.entrada.grid(row=0, column=1, sticky="w", pady=2)
        con_ejemplo(self.entrada, self.texto, "Ej. HOLA")

        ttk.Label(cuerpo, text="Display:").grid(row=1, column=0, sticky="w")
        self.tipo = tk.StringVar(value="7seg")
        fila = ttk.Frame(cuerpo)
        fila.grid(row=1, column=1, sticky="w", pady=2)
        for tipo in ("7seg", "14seg", "16seg"):
            ttk.Radiobutton(fila, text=seg.NOMBRES_TIPO[tipo], value=tipo,
                            variable=self.tipo).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(cuerpo, text="Conexion:").grid(row=2, column=0, sticky="w")
        self.anodo = tk.BooleanVar(value=False)
        fila = ttk.Frame(cuerpo)
        fila.grid(row=2, column=1, sticky="w", pady=2)
        ttk.Radiobutton(fila, text="Catodo comun (1 = encendido)", value=False,
                        variable=self.anodo).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(fila, text="Anodo comun (0 = encendido)", value=True,
                        variable=self.anodo).pack(side=tk.LEFT)

        marco = ttk.LabelFrame(cuerpo, text="Vista previa", padding=6)
        marco.grid(row=3, column=0, columnspan=2, sticky="we", pady=(8, 0))
        self.vista = tk.Canvas(marco, width=ANCHO_VISTA, height=80, bg=theme.DISP_BG,
                               highlightthickness=0)
        self.vista.pack()

        self.estado = ttk.Label(cuerpo, foreground="#777", justify=tk.LEFT,
                                wraplength=ANCHO_VISTA)
        self.estado.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        botones = ttk.Frame(cuerpo)
        botones.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(botones, text="Cancelar", command=self.win.destroy).pack(
            side=tk.RIGHT, padx=(6, 0))
        self.boton_crear = ttk.Button(botones, text="Crear tabla", command=self.crear)
        self.boton_crear.pack(side=tk.RIGHT)

        for variable in (self.texto, self.tipo, self.anodo):
            variable.trace_add("write", lambda *_: self.actualizar())
        self.actualizar()
        self.entrada.focus_set()

    # ---------------------------------------------------------------- vista

    def _revisar(self):
        """(proyecto o None, mensaje para la etiqueta gris). Un solo lugar
        decide si el texto sirve, para la vista previa y para el boton."""
        cadena = self.texto.get()
        tipo = self.tipo.get()
        if not cadena:
            return None, ("Escriba el texto. Caracteres disponibles en "
                          f"{seg.NOMBRES_TIPO[tipo]}: {self._lista(tipo)}")
        faltan = seg.no_soportados(cadena, tipo)
        if faltan:
            nota = ""
            if tipo == "7seg" and any(c.upper() in seg.SIN_FORMA_EN_7 for c in faltan):
                nota = " K, M, V, W, X y Z no tienen forma legible en 7 segmentos."
            return None, (f"No existen en {seg.NOMBRES_TIPO[tipo]}: "
                          f"{' '.join(repr(c) for c in faltan)}.{nota} "
                          f"Disponibles: {self._lista(tipo)}")
        if len(cadena) > seg.MAX_CARACTERES:
            return None, (f"El texto tiene {len(cadena)} caracteres; el maximo es "
                          f"{seg.MAX_CARACTERES} (6 entradas).")
        try:
            proyecto = seg.proyecto_mensaje(cadena, tipo, anodo_comun=self.anodo.get())
        except ValueError as error:
            return None, str(error)
        n = len(proyecto["input_names"])
        return proyecto, (
            f"{len(cadena)} caracteres: {n} entradas ({' '.join(proyecto['input_names'])}) y "
            f"{len(proyecto['output_names'])} salidas ({' '.join(proyecto['output_names'])}).")

    @staticmethod
    def _lista(tipo):
        """Los caracteres disponibles, legibles: el espacio se nombra."""
        return " ".join("espacio" if c == " " else c for c in seg.soportados(tipo))

    def actualizar(self):
        """Redibuja la vista previa y el aviso cada vez que cambia algo."""
        proyecto, mensaje = self._revisar()
        self.estado.config(text=mensaje)
        self.boton_crear.state(["!disabled"] if proyecto else ["disabled"])
        self._dibujar(self.texto.get()[:seg.MAX_CARACTERES], self.tipo.get())

    def _dibujar(self, cadena, tipo):
        """Los digitos con la geometria de ktool/segmentos.py, con los colores
        del panel de displays. Un caracter que no existe sale apagado con '?'."""
        self.vista.delete("all")
        poligonos, w, h = seg.geometria(tipo)
        paso_x, paso_y = w * ESCALA, h * ESCALA
        por_renglon = max(1, int((ANCHO_VISTA - 8) // paso_x))
        renglones = max(1, -(-len(cadena) // por_renglon))
        self.vista.config(height=int(renglones * paso_y + 8))
        for k, caracter in enumerate(cadena):
            x0 = 4 + (k % por_renglon) * paso_x
            y0 = 4 + (k // por_renglon) * paso_y
            try:
                encendidos = seg.segmentos(caracter, tipo)
                existe = True
            except ValueError:
                encendidos, existe = {}, False
            for nombre, pts in poligonos:
                if nombre == seg.PUNTO:
                    continue
                escalados = []
                for i in range(0, len(pts), 2):
                    escalados += [x0 + pts[i] * ESCALA, y0 + pts[i + 1] * ESCALA]
                relleno = theme.SEG_ON if encendidos.get(nombre) == 1 else theme.SEG_OFF
                self.vista.create_polygon(escalados, fill=relleno, outline="#000")
            if not existe:
                self.vista.create_text(x0 + paso_x / 2, y0 + paso_y / 2, text="?",
                                       fill=theme.NAME_FG, font=("Consolas", 14, "bold"))

    # ---------------------------------------------------------------- crear

    def crear(self):
        """Entrega el proyecto a al_crear y cierra. Si el texto no sirve, no
        hace nada: el motivo ya esta en la etiqueta gris."""
        proyecto, _mensaje = self._revisar()
        if proyecto is None:
            return
        self.win.destroy()
        self.al_crear(proyecto)
