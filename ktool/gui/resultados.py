"""El panel de abajo de la ventana: todo lo que sale de la tabla, en un solo lugar.

Cinco pestanas, cada una con sus opciones y UN boton de accion, y el resultado
dentro de la misma pestana (nada de ventanas sueltas):

    Ecuaciones        SOP, POS, NAND, NOR, XOR y la recomendada, al momento
    Portada           titulo, autor, organizacion... y quien revisa y autoriza
    Generar           palomeas que contiene y sale todo de un clic en una carpeta
    Protoboard        el armado fisico: chips, tablero y cables
    Kit de hardware   resumen del kit; su ventana elige placas, pines y ajustes

Todas leen la misma tabla y la misma *Forma* de la barra de arriba, asi que lo
que dice una pestana es lo que hacen las otras. Generar usa la Portada y las
opciones de Protoboard y Kit.

El panel sabe guardar y recuperar todas sus opciones (`a_dict` / `desde_dict`),
y asi el proyecto (.ktool.json) las trae de vuelta tal cual.
"""

from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .. import io as ktio
from ..core.simplify import solve_output, shared_terms
from ..render.report import CAMPOS_PORTADA, Options, build_report, save_report
from ..proto import chips as catalogo_chips
from ..hw import kit as hw_kit
from ..hw.configuracion import ConfigKit
from .kit_ventana import FuenteTabla, VentanaKit

# texto de la pantalla -> valor del motor
MODOS_PROTO = {
    "fiel al diagrama": "fiel",
    "solo los chips que tengo": "forzado",
    "automatico (el ancho mayor)": "automatico",
}
EXTREMOS = {
    "puntos etiquetados": "puntos",
    "LED en cada salida": "led",
    "display 7 seg, catodo comun": "7seg_cc",
    "display 7 seg, anodo comun": "7seg_ca",
    "display 16 seg, catodo comun": "16seg_cc",
    "display 16 seg, anodo comun": "16seg_ca",
}
GRIS = "#777"

# Lo que puede contener el documento, con su texto en pantalla. Todo palomeado
# de entrada: el documento trae todo y se quita lo que sobre.
SECCIONES_DOCUMENTO = [
    ("portada", "Portada"), ("tabla", "Tabla de verdad"), ("kmap", "Mapas de Karnaugh"),
    ("circuito", "Circuitos"), ("compartidos", "Terminos compartidos"),
    ("lenguajes", "Ecuaciones en lenguajes"), ("proto", "Armado en protoboard"),
    ("kit", "Kit de hardware (pines, ajustes y codigo)"),
]
# Lo que ademas se guarda en la carpeta, aparte del documento
ARCHIVOS_APARTE = [
    ("armado_aparte", "El armado en protoboard en su propio HTML"),
    ("kit_carpeta", "La carpeta del kit, con un archivo por placa"),
    ("proyecto", "El proyecto (.ktool.json) para reabrirlo y editarlo"),
]
# El ejemplo que se ve dentro de cada cuadro de la portada mientras esta vacio
EJEMPLOS_PORTADA = {
    "titulo": "Ej. Sumador de 4 bits",
    "subtitulo": "Ej. Practica 4: circuitos aritmeticos",
    "autor": "Ej. tu nombre",
    "organizacion": "Ej. nombre de la escuela",
    "materia": "Ej. Aplicacion de Sistemas Digitales",
    "profesor": "Ej. nombre del profesor",
    "secuencia": "Ej. 2CM40",
    "fecha": "Ej. 22/11/2026",
    "reviso": "Ej. quien revisa",
    "autorizo": "Ej. quien autoriza",
}


def con_ejemplo(entrada, variable, texto):
    """Muestra `texto` en gris DENTRO del cuadro mientras esta vacio y sin foco.

    Es un Label encima del Entry, no texto dentro de la variable: asi
    `variable.get()` nunca devuelve el ejemplo por error. Devuelve una funcion
    para cambiar el ejemplo despues (el de los pines depende de la tabla).
    """
    # sin relleno ni borde: si no, la etiqueta tapa la raya inferior del cuadro
    etiqueta = tk.Label(entrada, text=texto, fg="#9a9a9a", bg="white", anchor="w",
                        font=("Segoe UI", 9), pady=0, bd=0, highlightthickness=0)

    def actualizar(*_):
        if not entrada.winfo_exists():   # la ventana se cerro antes de llegar aqui
            return
        vacio = not variable.get()
        con_foco = entrada.focus_get() is entrada
        habilitado = str(entrada.cget("state")) != "disabled"
        if vacio and not con_foco and habilitado:
            etiqueta.place(x=3, rely=0.5, anchor="w")
        else:
            etiqueta.place_forget()

    def cambiar(nuevo):
        etiqueta.config(text=nuevo)

    etiqueta.bind("<Button-1>", lambda _e: entrada.focus_set())
    entrada.bind("<FocusIn>", actualizar, add="+")
    entrada.bind("<FocusOut>", actualizar, add="+")
    variable.trace_add("write", actualizar)
    # desde la raiz y no desde el cuadro: si el cuadro se destruye antes de que
    # Tk este libre, Tkinter borra sus comandos y la llamada pendiente truena
    entrada._root().after_idle(actualizar)
    entrada.actualizar_ejemplo = actualizar   # para cuando cambia su estado
    return cambiar


def _texto_con_barra(padre, **opciones):
    """Un tk.Text con su barra vertical, empacado a la izquierda de `padre`.
    Con muchas salidas, ni las ecuaciones ni los resumenes caben a la vista."""
    marco = ttk.Frame(padre)
    marco.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    texto = tk.Text(marco, wrap="none", **opciones)
    barra = ttk.Scrollbar(marco, orient="vertical", command=texto.yview)
    texto.configure(yscrollcommand=barra.set)
    barra.pack(side=tk.RIGHT, fill=tk.Y)
    texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return texto


def _escribir_en(texto, lineas):
    """Reemplaza el contenido de un Text de solo lectura."""
    texto.config(state="normal")
    texto.delete("1.0", tk.END)
    texto.insert("1.0", "\n".join(lineas))
    texto.config(state="disabled")


def nombre_de_archivo(titulo):
    """'Sumador de 4 bits' -> 'sumador_de_4_bits': un nombre que cualquier
    sistema de archivos acepta (sin acentos raros ni signos)."""
    limpio = re.sub(r"[^A-Za-z0-9]+", "_", titulo.strip()).strip("_").lower()
    return limpio or "ktool"


class PanelResultados:
    """El Notebook de abajo. `app` es la ventana (gui/app.py): de ella se lee la
    tabla (`app._current_table()`) y la forma (`app.form`)."""

    def __init__(self, app, padre):
        self.app = app
        marco = ttk.LabelFrame(padre, text="Resultados", padding=6)
        marco.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=6)
        self.notebook = ttk.Notebook(marco)
        self.notebook.pack(fill=tk.X)

        self.pestanas = {}
        self._pestana_ecuaciones()
        self._pestana_portada()
        self._pestana_generar()
        self._pestana_protoboard()
        self._pestana_kit()
        # lo que depende de la tabla se recalcula al entrar a su pestana
        self.notebook.bind("<<NotebookTabChanged>>", self._al_cambiar_pestana)

    def mostrar(self, nombre):
        """Abre una pestana: 'ecuaciones', 'portada', 'generar', 'protoboard', 'kit'."""
        self.notebook.select(self.pestanas[nombre])

    def _nueva_pestana(self, nombre, titulo):
        marco = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(marco, text=titulo)
        self.pestanas[nombre] = marco
        return marco

    def _al_cambiar_pestana(self, _evento):
        """La tabla pudo cambiar (valores, entradas, nombres) mientras se veia
        otra pestana: lo que depende de ella se recalcula al entrar."""
        actual = self.notebook.select()
        if actual == str(self.pestanas["ecuaciones"]):
            self.actualizar_ecuaciones()
        elif actual == str(self.pestanas["kit"]):
            self._actualizar_resumen_kit()

    def _forma_unica(self):
        """La forma de la barra, para lo que necesita UNA sola realizacion.
        'both' es solo para el documento (SOP y POS lado a lado)."""
        forma = self.app.form.get()
        return forma if forma in ("sop", "pos", "nand", "nor") else "auto"

    def titulo(self):
        """El titulo del proyecto: el de la portada, o el generico."""
        return self.portada["titulo"].get().strip() or "Resultados ktool"

    # ------------------------------------------------------------ Ecuaciones
    def _pestana_ecuaciones(self):
        p = self._nueva_pestana("ecuaciones", "Ecuaciones")
        lado = ttk.Frame(p, padding=(8, 0, 0, 0))
        lado.pack(side=tk.RIGHT, fill=tk.Y)
        self.texto_ecuaciones = _texto_con_barra(p, height=9, font=("Consolas", 10))
        ttk.Button(lado, text="Actualizar", command=self.actualizar_ecuaciones).pack(fill=tk.X)
        ttk.Label(lado, text="Se actualiza sola al\nvolver a esta pestana.",
                  foreground=GRIS, justify=tk.LEFT).pack(anchor="w", pady=(6, 0))

    def actualizar_ecuaciones(self):
        tabla = self.app._current_table()
        sols = {n: solve_output(v, tabla.variables) for n, v in tabla.outputs.items()}
        lineas = [f"{tabla.nvars} entradas: {', '.join(tabla.variables)}", ""]
        for nombre, sol in sols.items():
            lineas.append(f"[{nombre}]")
            for forma in ("sop", "pos", "nand", "nor"):
                s = sol[forma]
                lineas.append(f"  {forma.upper():<4}: {nombre} = {s.equation}   "
                              f"({s.cost()[0]} comp, {s.cost()[1]} lit)")
            if sol["xor"]:
                s = sol["xor"]
                lineas.append(f"  XOR : {nombre} = {s.equation}   "
                              f"({s.cost()[0]} comp, {s.cost()[1]} lit)")
            lineas.append(f"  mejor por costo: {sol['best'].form.upper()} -> "
                          f"{nombre} = {sol['best'].equation}")
            lineas.append("")
        if len(tabla.outputs) > 1:
            compartidos = shared_terms(sols, tabla.variables, "sop")
            if compartidos:
                lineas.append("[terminos reutilizables (SOP)]")
                for d in compartidos:
                    lineas.append(f"  {d['term']:<14} -> {', '.join(d['outputs'])}")
        self.texto_ecuaciones.delete("1.0", tk.END)
        self.texto_ecuaciones.insert("1.0", "\n".join(lineas))

    # ---------------------------------------------------------------- Portada
    def _pestana_portada(self):
        p = self._nueva_pestana("portada", "Portada")
        self.portada = {}
        # dos columnas de etiqueta + cuadro; lo vacio no sale en el documento
        for i, (clave, etiqueta) in enumerate(CAMPOS_PORTADA):
            fila, columna = i // 2, (i % 2) * 2
            ttk.Label(p, text=etiqueta + ":").grid(row=fila, column=columna, sticky="w",
                                                   padx=(0 if columna == 0 else 16, 4), pady=2)
            var = tk.StringVar()
            entrada = ttk.Entry(p, textvariable=var, width=38)
            entrada.grid(row=fila, column=columna + 1, sticky="w", pady=2)
            con_ejemplo(entrada, var, EJEMPLOS_PORTADA[clave])
            self.portada[clave] = var
        ttk.Label(p, foreground=GRIS, text=(
            "Sale al inicio del documento, con lineas de firma para quien revisa y "
            "quien autoriza. Lo vacio no aparece.")).grid(
            row=len(CAMPOS_PORTADA) // 2 + 1, column=0, columnspan=4, sticky="w", pady=(6, 0))

    def datos_portada(self):
        return {clave: var.get().strip() for clave, var in self.portada.items()}

    # ---------------------------------------------------------------- Generar
    def _pestana_generar(self):
        p = self._nueva_pestana("generar", "Generar")
        izquierda = ttk.Frame(p)
        izquierda.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(izquierda, text="El documento contiene:").grid(row=0, column=0,
                                                                 columnspan=4, sticky="w")
        self.contiene = {}
        for i, (clave, texto) in enumerate(SECCIONES_DOCUMENTO):
            var = tk.BooleanVar(value=True)
            self.contiene[clave] = var
            ttk.Checkbutton(izquierda, text=texto, variable=var).grid(
                row=1 + i // 4, column=i % 4, sticky="w", padx=(0, 10))

        ttk.Label(izquierda, text="Y ademas, en la carpeta:").grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        for i, (clave, texto) in enumerate(ARCHIVOS_APARTE):
            var = tk.BooleanVar(value=True)
            self.contiene[clave] = var
            ttk.Checkbutton(izquierda, text=texto, variable=var).grid(
                row=4 + i // 2, column=(i % 2) * 2, columnspan=2, sticky="w", padx=(0, 10))

        ttk.Label(izquierda, text="Carpeta:").grid(row=6, column=0, sticky="w", pady=(8, 0))
        self.generar_carpeta = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Documents", "ktool"))
        ttk.Entry(izquierda, textvariable=self.generar_carpeta, width=52).grid(
            row=6, column=1, columnspan=2, sticky="we", pady=(8, 0))
        ttk.Button(izquierda, text="Elegir...",
                   command=lambda: self._elegir_carpeta(self.generar_carpeta)).grid(
            row=6, column=3, sticky="w", padx=4, pady=(8, 0))

        derecha = ttk.Frame(p, padding=(16, 0, 0, 0))
        derecha.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        botones = ttk.Frame(derecha)
        botones.pack(fill=tk.X)
        ttk.Button(botones, text="Generar todo", command=self.generar_todo).pack(side=tk.LEFT)
        self.generar_abrir = ttk.Button(
            botones, text="Abrir carpeta", state="disabled",
            command=lambda: os.startfile(self._carpeta_generada))
        if hasattr(os, "startfile"):   # abrir una carpeta solo existe en Windows
            self.generar_abrir.pack(side=tk.LEFT, padx=6)
        caja = ttk.Frame(derecha)
        caja.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.generar_resumen = _texto_con_barra(caja, height=7, width=56,
                                                font=("Consolas", 9), state="disabled")
        _escribir_en(self.generar_resumen, [
            "Palomea lo que quieres y dale Generar todo.",
            "Todo sale en una subcarpeta con el nombre del titulo."])

    def _opciones_documento(self, solo_armado=False):
        """Options del documento con lo palomeado. ValueError si algo no sirve."""
        c = {clave: var.get() for clave, var in self.contiene.items()}
        if solo_armado:   # el armado aparte: la tabla y el protoboard, nada mas
            return Options(form=self._forma_proto(), title=f"{self.titulo()}: armado",
                           table=True, kmap=False, circuit=False, shared=False, langs=[],
                           proto=True, **self._opciones_proto())
        proto = self._opciones_proto() if c["proto"] else {}
        return Options(
            form=self.app.form.get(), title=self.titulo(),
            portada=self.datos_portada() if c["portada"] else None,
            table=c["tabla"], kmap=c["kmap"], circuit=c["circuito"],
            shared=c["compartidos"], langs=None if c["lenguajes"] else [],
            proto=c["proto"], kit=c["kit"],
            kit_config=self.kit_config if c["kit"] else None, **proto)

    def generar_todo(self):
        """Un clic: el documento y todo lo palomeado, en <carpeta>/<titulo>/."""
        base = self.generar_carpeta.get().strip()
        if not base:
            messagebox.showerror("Falta la carpeta", "Escribe o elige una carpeta.")
            return
        nombre = nombre_de_archivo(self.titulo())
        carpeta = os.path.join(base, nombre)
        if os.path.isdir(carpeta) and os.listdir(carpeta):
            if not messagebox.askyesno(
                    "La carpeta ya existe",
                    f"{carpeta}\n\nya tiene archivos. Los que se generan se reemplazan; los "
                    "demas se quedan. Seguir?"):
                return
        tabla = self.app._current_table()
        escritos = []
        try:
            documento = build_report(tabla, self._opciones_documento())
            armado = (build_report(tabla, self._opciones_documento(solo_armado=True))
                      if self.contiene["armado_aparte"].get() else None)
            kit = (self.kit_config.armar(tabla, self._forma_unica())
                   if self.contiene["kit_carpeta"].get() else None)
        except ValueError as e:   # un chip, un pin o un nombre que no sirve
            messagebox.showerror("No se pudo generar", str(e))
            return

        os.makedirs(carpeta, exist_ok=True)
        save_report(documento, os.path.join(carpeta, nombre + ".html"))
        escritos.append(nombre + ".html")
        if armado is not None:
            save_report(armado, os.path.join(carpeta, nombre + "_armado.html"))
            escritos.append(nombre + "_armado.html")
        if kit is not None:
            hw_kit.escribir(kit, os.path.join(carpeta, "kit"))
            listos = sum(1 for _, estado, _ in kit.resumen if estado == "listo")
            escritos.append(f"kit/  ({listos} de {len(kit.resumen)} plataformas listas)")
        if self.contiene["proyecto"].get():
            ktio.save(self.app.serializar(), os.path.join(carpeta, nombre + ktio.EXT))
            escritos.append(nombre + ktio.EXT)

        self._carpeta_generada = carpeta
        self.generar_abrir.config(state="normal")
        _escribir_en(self.generar_resumen,
                     [f"Listo, en {carpeta}:", ""] + [f"  {e}" for e in escritos])

    # ------------------------------------------------------------ Protoboard
    def _pestana_protoboard(self):
        p = self._nueva_pestana("protoboard", "Protoboard")
        ttk.Label(p, text="Chips:").grid(row=0, column=0, sticky="w")
        self.proto_modo = tk.StringVar(value="fiel al diagrama")
        modo = ttk.Combobox(p, textvariable=self.proto_modo, state="readonly", width=26,
                            values=list(MODOS_PROTO))
        modo.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(p, text="Los que tengo:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.proto_chips = tk.StringVar()
        # solo cuenta en 'solo los chips que tengo': en los otros modos se apaga
        self._entrada_chips = ttk.Entry(p, textvariable=self.proto_chips, width=26,
                                        state="disabled")
        self._entrada_chips.grid(row=0, column=3, sticky="w", padx=4)
        con_ejemplo(self._entrada_chips, self.proto_chips, "Ej. 7400, 7404, 7486")
        modo.bind("<<ComboboxSelected>>", lambda _e: self._ajustar_entrada_chips())

        ttk.Label(p, text="En las salidas:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.proto_extremos = tk.StringVar(value="LED en cada salida")
        ttk.Combobox(p, textvariable=self.proto_extremos, state="readonly", width=26,
                     values=list(EXTREMOS)).grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(p, text="Color de salidas:").grid(row=1, column=2, sticky="w",
                                                    padx=(12, 0), pady=(6, 0))
        self.proto_color = tk.StringVar()
        color = ttk.Entry(p, textvariable=self.proto_color, width=26)
        color.grid(row=1, column=3, sticky="w", padx=4, pady=(6, 0))
        con_ejemplo(color, self.proto_color, "Ej. red o #1f77b4 (vacio: uno c/u)")

        self.proto_separado = tk.BooleanVar(value=False)
        ttk.Checkbutton(p, text="Una protoboard por salida", variable=self.proto_separado).grid(
            row=2, column=1, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(p, foreground=GRIS, text=(
            "Chips del catalogo: " + ", ".join(sorted(catalogo_chips.CHIPS)) + ".\n"
            "Beta: la lista de cables esta comprobada contra la tabla, pero aun no se "
            "arma en una mesa real.")).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

        acciones = ttk.Frame(p)
        acciones.grid(row=4, column=0, columnspan=4, sticky="we", pady=(10, 0))
        ttk.Button(acciones, text="Generar armado...", command=self.generar_armado).pack(side=tk.LEFT)
        self.proto_estado = ttk.Label(acciones, foreground=GRIS, text="")
        self.proto_estado.pack(side=tk.LEFT, padx=10)

    def _ajustar_entrada_chips(self):
        forzado = MODOS_PROTO[self.proto_modo.get()] == "forzado"
        self._entrada_chips.config(state="normal" if forzado else "disabled")
        self._entrada_chips.actualizar_ejemplo()

    def _forma_proto(self):
        """El armado necesita una sola realizacion de las que sabe armar."""
        forma = self.app.form.get()
        return forma if forma in ("sop", "pos", "nand", "nor") else "sop"

    def _opciones_proto(self):
        """Las opciones de la pestana Protoboard, validadas. ValueError si no."""
        modo = MODOS_PROTO[self.proto_modo.get()]
        chips = [c.strip() for c in self.proto_chips.get().replace(",", " ").split() if c.strip()]
        for c in chips:
            if c not in catalogo_chips.CHIPS:
                raise ValueError(f"el chip {c!r} no esta en el catalogo. Hay: "
                                 + ", ".join(sorted(catalogo_chips.CHIPS)))
        if modo == "forzado" and not chips:
            raise ValueError("'solo los chips que tengo' necesita la lista de chips")
        color = self.proto_color.get().strip() or None
        return {"proto_modo": modo, "proto_chips": chips or None,
                "proto_extremos": EXTREMOS[self.proto_extremos.get()],
                "proto_separado": self.proto_separado.get(),
                "proto_color_salidas": color}

    def generar_armado(self):
        """Un documento solo con la tabla y el armado: lo que se lleva a la mesa."""
        try:
            html = build_report(self.app._current_table(),
                                self._opciones_documento(solo_armado=True))
        except ValueError as e:
            messagebox.showerror("No se pudo generar el armado", str(e))
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".html", filetypes=[("HTML", "*.html")],
            initialfile=nombre_de_archivo(self.titulo()) + "_armado.html")
        if not ruta:
            return
        guardado = save_report(html, ruta, open_browser=True)
        self.proto_estado.config(text=f"Guardado en {guardado}  (abierto en el navegador)")

    # ------------------------------------------------------- Kit de hardware
    def _pestana_kit(self):
        """Resumen del kit y el boton a su ventana: elegir placas y pines en el
        dibujo del componente, cambiar los ajustes y revisar cada archivo."""
        p = self._nueva_pestana("kit", "Kit de hardware")
        self.kit_config = ConfigKit()
        izquierda = ttk.Frame(p)
        izquierda.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Button(izquierda, text="Configurar kit...", command=self.abrir_kit).pack(
            anchor="w")
        ttk.Button(izquierda, text="Escribir kit", command=self.escribir_kit).pack(
            anchor="w", pady=(6, 0))
        self.kit_abrir = ttk.Button(izquierda, text="Abrir carpeta", state="disabled",
                                    command=lambda: os.startfile(self.kit_config.carpeta))
        if hasattr(os, "startfile"):
            self.kit_abrir.pack(anchor="w", pady=(6, 0))
        caja = ttk.Frame(p, padding=(16, 0, 0, 0))
        caja.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.kit_resumen = _texto_con_barra(caja, height=7, width=60, font=("Consolas", 9),
                                            state="disabled")
        self._actualizar_resumen_kit()

    def abrir_kit(self):
        """La ventana del kit sobre la tabla de la ventana principal."""
        VentanaKit(self.app.root, self.kit_config, FuenteTabla(self.app),
                   al_cambiar=self._al_cambiar_kit)

    def _al_cambiar_kit(self):
        self._actualizar_resumen_kit()

    def _actualizar_resumen_kit(self, escritos=None):
        """Que placas se generan, con que pines y en que carpeta."""
        c = self.kit_config
        titulos = [hw_kit.TITULO_PLATAFORMA[p] for p in c.elegidas]
        lineas = ["Se genera para:" if titulos else "Ninguna plataforma marcada."]
        for p, titulo in zip(c.elegidas, titulos):
            pines = c.pines.get(p)
            nota = f"  ({len(pines)} pines fijos)" if pines else ""
            lineas.append(f"  {titulo}{nota}")
        lineas += ["", f"Carpeta: {c.carpeta}"]
        if c.editados:
            lineas.append(f"Archivos editados a mano: {len(c.editados)}")
        if escritos:
            lineas += [""] + escritos
        _escribir_en(self.kit_resumen, lineas)

    def _elegir_carpeta(self, variable):
        elegida = filedialog.askdirectory(title="Escoge la carpeta",
                                          initialdir=os.path.dirname(variable.get()))
        if elegida:
            variable.set(elegida)

    def escribir_kit(self):
        carpeta = self.kit_config.carpeta
        if not carpeta:
            messagebox.showerror("Falta la carpeta", "Elige la carpeta en Configurar kit.")
            return
        if os.path.isdir(carpeta) and os.listdir(carpeta):
            if not messagebox.askyesno(
                    "La carpeta ya tiene archivos",
                    f"{carpeta}\n\nya tiene archivos. Los del kit se reemplazan; los demas "
                    "se quedan. Seguir?"):
                return
        try:
            kit = self.kit_config.armar(self.app._current_table(), self._forma_unica())
        except ValueError as e:   # un pin o un nombre de salida que no sirve
            messagebox.showerror("No se pudo escribir el kit", str(e))
            return
        hw_kit.escribir(kit, carpeta)
        escritos = []
        for plataforma, estado, detalle in kit.resumen:
            escritos.append(f"ok  {plataforma}" if estado == "listo"
                            else f"--  {plataforma}: {detalle}")
        self._actualizar_resumen_kit(["Escrito:"] + escritos)
        self.kit_abrir.config(state="normal")

    # ------------------------------------------------- guardar en el proyecto
    def a_dict(self):
        """Todas las opciones del panel, para el proyecto (.ktool.json)."""
        return {
            "proyecto": self.datos_portada(),
            "generar": {"contiene": {c: v.get() for c, v in self.contiene.items()},
                        "carpeta": self.generar_carpeta.get()},
            "protoboard": {"modo": self.proto_modo.get(), "chips": self.proto_chips.get(),
                           "extremos": self.proto_extremos.get(),
                           "separado": self.proto_separado.get(),
                           "color": self.proto_color.get()},
            "kit": self.kit_config.a_dict(),
        }

    def desde_dict(self, fuente):
        """Lo contrario de a_dict. Lo que falte se queda como esta (archivos viejos)."""
        for clave, var in self.portada.items():
            var.set((fuente.get("proyecto") or {}).get(clave, ""))
        generar = fuente.get("generar") or {}
        for clave, valor in (generar.get("contiene") or {}).items():
            if clave in self.contiene:
                self.contiene[clave].set(bool(valor))
        if generar.get("carpeta"):
            self.generar_carpeta.set(generar["carpeta"])
        proto = fuente.get("protoboard") or {}
        if proto.get("modo") in MODOS_PROTO:
            self.proto_modo.set(proto["modo"])
        self.proto_chips.set(proto.get("chips", ""))
        if proto.get("extremos") in EXTREMOS:
            self.proto_extremos.set(proto["extremos"])
        self.proto_separado.set(bool(proto.get("separado", False)))
        self.proto_color.set(proto.get("color", ""))
        self._ajustar_entrada_chips()
        self.kit_config = ConfigKit.desde_dict(fuente.get("kit"))
        self._actualizar_resumen_kit()
