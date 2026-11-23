"""El panel de abajo de la ventana: todo lo que sale de la tabla, en un solo lugar.

Cuatro pestanas, cada una con sus opciones y UN boton de accion, y el resultado
dentro de la misma pestana (nada de ventanas sueltas):

    Ecuaciones        SOP, POS, NAND, NOR, XOR y la recomendada, al momento
    Documento         el HTML, con las secciones que se marquen (todas por omision)
    Protoboard        el armado fisico: chips, tablero y cables
    Kit de hardware   la carpeta con el codigo para cada placa

Todas leen la misma tabla y la misma *Forma* de la barra de arriba, asi que lo
que dice una pestana es lo que hacen las otras. Las opciones de Protoboard y de
Kit son tambien las que usa el Documento cuando incluye esas secciones.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ..core.simplify import solve_output, shared_terms
from ..render.report import Options, build_report, save_report
from ..proto import chips as catalogo_chips
from ..hw import kit as hw_kit, placas
from ..hw.modelo import leer_pines

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
SIN_PINES = "(ktool los elige)"
GRIS = "#777"


def _texto_con_barra(padre, **opciones):
    """Un tk.Text con su barra vertical, empacado a la izquierda de `padre`.
    Con muchas salidas, ni las ecuaciones ni el resumen del kit caben a la vista."""
    marco = ttk.Frame(padre)
    marco.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    texto = tk.Text(marco, wrap="none", **opciones)
    barra = ttk.Scrollbar(marco, orient="vertical", command=texto.yview)
    texto.configure(yscrollcommand=barra.set)
    barra.pack(side=tk.RIGHT, fill=tk.Y)
    texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return texto


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
        self._pestana_documento()
        self._pestana_protoboard()
        self._pestana_kit()
        # las ecuaciones se recalculan solas cada vez que se vuelve a su pestana
        self.notebook.bind("<<NotebookTabChanged>>", self._al_cambiar_pestana)

    def mostrar(self, nombre):
        """Abre una pestana por nombre: 'ecuaciones', 'documento', 'protoboard', 'kit'."""
        self.notebook.select(self.pestanas[nombre])

    def _nueva_pestana(self, nombre, titulo):
        marco = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(marco, text=titulo)
        self.pestanas[nombre] = marco
        return marco

    def _al_cambiar_pestana(self, _evento):
        """Lo que depende de la tabla se recalcula al entrar: la tabla pudo
        cambiar (valores, variables, nombres) mientras se veia otra pestana."""
        actual = self.notebook.select()
        if actual == str(self.pestanas["ecuaciones"]):
            self.actualizar_ecuaciones()
        elif actual == str(self.pestanas["kit"]):
            self._actualizar_pista()

    def _forma_unica(self):
        """La forma de la barra, para lo que necesita UNA sola realizacion.
        'both' es solo para el documento (SOP y POS lado a lado)."""
        forma = self.app.form.get()
        return forma if forma in ("sop", "pos", "nand", "nor") else "auto"

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
        lineas = [f"{tabla.nvars} variables: {', '.join(tabla.variables)}", ""]
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

    # ------------------------------------------------------------- Documento
    def _pestana_documento(self):
        p = self._nueva_pestana("documento", "Documento")
        ttk.Label(p, text="Titulo:").grid(row=0, column=0, sticky="w")
        self.doc_titulo = tk.StringVar(value="Resultados ktool")
        ttk.Entry(p, textvariable=self.doc_titulo, width=40).grid(
            row=0, column=1, columnspan=3, sticky="w", padx=4)

        ttk.Label(p, text="Incluir:").grid(row=1, column=0, sticky="nw", pady=(8, 0))
        # todo marcado de entrada: el documento trae todo, y se quita lo que sobre
        self.doc_secciones = {}
        secciones = [("tabla", "Tabla de verdad"), ("kmap", "Mapas de Karnaugh"),
                     ("circuito", "Circuitos"), ("compartidos", "Terminos compartidos"),
                     ("lenguajes", "Ecuaciones en lenguajes"),
                     ("proto", "Armado en protoboard"), ("kit", "Kit de hardware")]
        for i, (clave, texto) in enumerate(secciones):
            var = tk.BooleanVar(value=True)
            self.doc_secciones[clave] = var
            ttk.Checkbutton(p, text=texto, variable=var).grid(
                row=1 + i // 4, column=1 + i % 4, sticky="w", padx=4, pady=(8 if i < 4 else 2, 0))
        ttk.Label(p, foreground=GRIS, text=(
            "El armado y el kit usan las opciones de sus pestanas. "
            "La forma es la de la barra de arriba.")).grid(
            row=3, column=1, columnspan=4, sticky="w", padx=4, pady=(6, 0))

        acciones = ttk.Frame(p)
        acciones.grid(row=4, column=0, columnspan=5, sticky="we", pady=(10, 0))
        ttk.Button(acciones, text="Generar documento...",
                   command=self.generar_documento).pack(side=tk.LEFT)
        self.doc_estado = ttk.Label(acciones, foreground=GRIS, text="")
        self.doc_estado.pack(side=tk.LEFT, padx=10)

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

    def generar_documento(self):
        s = {clave: var.get() for clave, var in self.doc_secciones.items()}
        try:
            proto = self._opciones_proto() if s["proto"] else {}
            pines = self._pines_del_kit() if s["kit"] else {}
            opciones = Options(
                form=self.app.form.get(), title=self.doc_titulo.get().strip() or "Resultados ktool",
                table=s["tabla"], kmap=s["kmap"], circuit=s["circuito"],
                shared=s["compartidos"], langs=None if s["lenguajes"] else [],
                proto=s["proto"], kit=s["kit"], kit_pines=pines, **proto)
            html = build_report(self.app._current_table(), opciones)
        except ValueError as e:
            messagebox.showerror("No se pudo generar el documento", str(e))
            return
        self._guardar_html(html, "ktool_resultado.html", self.doc_estado)

    def _guardar_html(self, html, sugerido, estado):
        ruta = filedialog.asksaveasfilename(defaultextension=".html",
                                            filetypes=[("HTML", "*.html")],
                                            initialfile=sugerido)
        if not ruta:
            return
        guardado = save_report(html, ruta, open_browser=True)
        estado.config(text=f"Guardado en {guardado}  (abierto en el navegador)")

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
        chips = ttk.Entry(p, textvariable=self.proto_chips, width=24, state="disabled")
        chips.grid(row=0, column=3, sticky="w", padx=4)
        modo.bind("<<ComboboxSelected>>", lambda _e: chips.config(
            state="normal" if MODOS_PROTO[self.proto_modo.get()] == "forzado" else "disabled"))

        ttk.Label(p, text="En las salidas:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.proto_extremos = tk.StringVar(value="LED en cada salida")
        ttk.Combobox(p, textvariable=self.proto_extremos, state="readonly", width=26,
                     values=list(EXTREMOS)).grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(p, text="Color de salidas:").grid(row=1, column=2, sticky="w",
                                                    padx=(12, 0), pady=(6, 0))
        self.proto_color = tk.StringVar()
        ttk.Entry(p, textvariable=self.proto_color, width=24).grid(
            row=1, column=3, sticky="w", padx=4, pady=(6, 0))

        self.proto_separado = tk.BooleanVar(value=False)
        ttk.Checkbutton(p, text="Una protoboard por salida", variable=self.proto_separado).grid(
            row=2, column=1, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(p, foreground=GRIS, text=(
            "Chips del catalogo: " + ", ".join(sorted(catalogo_chips.CHIPS)) + ".  "
            "Color vacio = uno por salida.\nBeta: la lista de cables esta comprobada contra "
            "la tabla, pero aun no se arma en una mesa real.")).grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

        acciones = ttk.Frame(p)
        acciones.grid(row=4, column=0, columnspan=4, sticky="we", pady=(10, 0))
        ttk.Button(acciones, text="Generar armado...", command=self.generar_armado).pack(side=tk.LEFT)
        self.proto_estado = ttk.Label(acciones, foreground=GRIS, text="")
        self.proto_estado.pack(side=tk.LEFT, padx=10)

    def generar_armado(self):
        """Un documento solo con la tabla y el armado: lo que se lleva a la mesa."""
        forma = self.app.form.get()
        if forma not in ("sop", "pos", "nand", "nor"):
            forma = "sop"   # el armado necesita una sola realizacion
        try:
            opciones = Options(form=forma, title="Armado en protoboard", table=True,
                               kmap=False, circuit=False, shared=False, langs=[],
                               proto=True, **self._opciones_proto())
            html = build_report(self.app._current_table(), opciones)
        except ValueError as e:
            messagebox.showerror("No se pudo generar el armado", str(e))
            return
        self._guardar_html(html, "ktool_armado.html", self.proto_estado)

    # ------------------------------------------------------- Kit de hardware
    def _pestana_kit(self):
        p = self._nueva_pestana("kit", "Kit de hardware")
        ttk.Label(p, text="Carpeta:").grid(row=0, column=0, sticky="w")
        self.kit_carpeta = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Documents", "ktool_kit"))
        ttk.Entry(p, textvariable=self.kit_carpeta, width=48).grid(row=0, column=1, sticky="we", padx=4)
        ttk.Button(p, text="Elegir...", command=self._elegir_carpeta).grid(row=0, column=2, sticky="w")

        # Pines fijos para cualquier placa: se elige la placa y se escriben sus
        # pines; cada placa recuerda los suyos.
        ttk.Label(p, text="Pines fijos en:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.kit_placa = tk.StringVar(value=SIN_PINES)
        self._titulo_a_placa = {info["titulo"]: nombre
                                for nombre, info in placas.PLACAS_CON_PINES.items()}
        combo = ttk.Combobox(p, textvariable=self.kit_placa, state="readonly", width=46,
                             values=[SIN_PINES] + list(self._titulo_a_placa))
        combo.grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        combo.bind("<<ComboboxSelected>>", self._al_cambiar_placa)
        self._pines_texto = {}            # nombre de placa -> texto escrito
        self.kit_pines = tk.StringVar()
        self.kit_pines_entry = ttk.Entry(p, textvariable=self.kit_pines, width=48, state="disabled")
        self.kit_pines_entry.grid(row=2, column=1, sticky="we", padx=4, pady=(4, 0))
        self.kit_pines.trace_add("write", self._al_escribir_pines)
        # se llena al entrar a la pestana (_al_cambiar_pestana): aqui la tabla
        # todavia no existe
        self.kit_pista = ttk.Label(p, foreground=GRIS, text="")
        self.kit_pista.grid(row=3, column=1, columnspan=2, sticky="w", padx=4)

        acciones = ttk.Frame(p)
        acciones.grid(row=0, column=3, rowspan=4, sticky="nsew", padx=(16, 0))
        p.columnconfigure(3, weight=1)
        botones = ttk.Frame(acciones)
        botones.pack(fill=tk.X)
        ttk.Button(botones, text="Escribir kit...", command=self.escribir_kit).pack(side=tk.LEFT)
        self.kit_abrir = ttk.Button(botones, text="Abrir carpeta", command=self._abrir_carpeta,
                                    state="disabled")
        if hasattr(os, "startfile"):   # abrir una carpeta solo existe en Windows
            self.kit_abrir.pack(side=tk.LEFT, padx=6)
        caja = ttk.Frame(acciones)
        caja.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.kit_resumen = _texto_con_barra(caja, height=7, width=60, font=("Consolas", 9),
                                            state="disabled")

    def _elegir_carpeta(self):
        elegida = filedialog.askdirectory(title="Carpeta del kit",
                                          initialdir=os.path.dirname(self.kit_carpeta.get()))
        if elegida:
            self.kit_carpeta.set(elegida)

    def _al_cambiar_placa(self, _evento=None):
        nombre = self._titulo_a_placa.get(self.kit_placa.get())
        if nombre is None:
            self.kit_pines.set("")
            self.kit_pines_entry.config(state="disabled")
        else:
            self.kit_pines_entry.config(state="normal")
            self.kit_pines.set(self._pines_texto.get(nombre, ""))
        self._actualizar_pista()

    def _al_escribir_pines(self, *_):
        nombre = self._titulo_a_placa.get(self.kit_placa.get())
        if nombre is not None:
            self._pines_texto[nombre] = self.kit_pines.get()
            self._actualizar_pista()

    def _actualizar_pista(self):
        tabla = self.app._current_table()
        orden = ", ".join(tabla.variables) + "  y luego  " + ", ".join(tabla.outputs)
        con_pines = [placas.PLACAS_CON_PINES[n]["titulo"]
                     for n, t in self._pines_texto.items() if t.strip()]
        texto = f"En este orden: {orden}.  Vacio = ktool los elige."
        if con_pines:
            texto += "\nCon pines propios: " + "; ".join(con_pines)
        self.kit_pista.config(text=texto)

    def _pines_del_kit(self):
        """{placa: [pines]} de lo escrito. ValueError si un pin no es del tipo."""
        return {nombre: leer_pines(texto, placas.PLACAS_CON_PINES[nombre])
                for nombre, texto in self._pines_texto.items() if texto.strip()}

    def escribir_kit(self):
        carpeta = self.kit_carpeta.get().strip()
        if not carpeta:
            messagebox.showerror("Falta la carpeta", "Escribe o elige una carpeta.")
            return
        if os.path.isdir(carpeta) and os.listdir(carpeta):
            if not messagebox.askyesno(
                    "La carpeta ya tiene archivos",
                    f"{carpeta}\n\nya tiene archivos. Los del kit se reemplazan; los demas "
                    "se quedan. Seguir?"):
                return
        try:
            resumen = hw_kit.generar(self.app._current_table(), carpeta, self._forma_unica(),
                                     self._pines_del_kit())
        except ValueError as e:   # un pin o un nombre de salida que no sirve
            messagebox.showerror("No se pudo escribir el kit", str(e))
            return
        listos = sum(1 for _, estado, _ in resumen if estado == "listo")
        lineas = [f"{listos} de {len(resumen)} listos, en:", f"  {carpeta}", ""]
        for plataforma, estado, detalle in resumen:
            if estado == "listo":
                lineas.append(f"ok  {plataforma}")
            else:
                lineas.append(f"--  {plataforma}: {detalle}")
        lineas += ["", "Detalle en LEEME.md. Antes de grabar: python python/simular.py"]
        self.kit_resumen.config(state="normal")
        self.kit_resumen.delete("1.0", tk.END)
        self.kit_resumen.insert("1.0", "\n".join(lineas))
        self.kit_resumen.config(state="disabled")
        self.kit_abrir.config(state="normal")

    def _abrir_carpeta(self):
        os.startfile(self.kit_carpeta.get())
