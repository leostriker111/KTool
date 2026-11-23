"""La ventana del kit de hardware: placas, pines, ajustes y archivos.

    +-------------+-------------------------------------------------+
    | Plataformas | [Pines] [Ajustes] [Archivos]                    |
    |  [x] PIC... |                                                 |
    |  [x] MAX II |   el componente dibujado, sus ajustes o la      |
    |  [ ] ESP32  |   vista previa editable de cada archivo         |
    |  ...        |                                                 |
    +-------------+-------------------------------------------------+
    | Carpeta: [............] [Elegir...]  [Escribir kit]  estado   |
    +---------------------------------------------------------------+

La lista de la izquierda dice que se genera (la columna Usar) y cual se esta
viendo (el renglon seleccionado). Todo lo que se cambia aqui vive en un
ConfigKit (hw/configuracion.py) que es del panel de Resultados: cerrar la
ventana no pierde nada, Generar todo lo usa, el documento lo describe y el
proyecto (.ktool.json) lo guarda.

La ventana no sabe si el circuito es una tabla o una maquina de estados: recibe
una `fuente` con dos funciones, `senales()` y `armar(config)`.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ..hw import ajustes as hw_ajustes, kit as hw_kit, placas
from .copiar import boton_copiar

GRIS = "#777"
USAR, NO_USAR = "[x]", "[ ]"


def _numero(valor):
    """50000000.0 -> '50000000', 2.5 -> '2.5': sin notacion cientifica."""
    return str(int(valor)) if float(valor).is_integer() else f"{valor:g}"


class FuenteTabla:
    """El circuito combinacional de la ventana principal, visto por el kit."""

    def __init__(self, app):
        self.app = app

    def titulo(self):
        return "tabla de verdad"

    def senales(self, placa=None):
        """Las entradas y salidas de la tabla; ninguna placa pide reloj."""
        tabla = self.app._current_table()
        return ([(e, "entrada") for e in tabla.variables]
                + [(s, "salida") for s in tabla.outputs])

    def armar(self, config):
        forma = self.app.form.get()
        forma = forma if forma in ("sop", "pos", "nand", "nor") else "auto"
        return config.armar(self.app._current_table(), forma)


class FuenteMaquina:
    """La maquina del editor de estados (gui/fsm_view.py), vista por el kit.

    Pide su reloj y su reset solo en la MAX II: ahi son patas de la tarjeta; en
    el PIC y el Arduino el reloj es un retardo del programa (hw/kit_fsm.py)."""

    def __init__(self, vista):
        self.vista = vista

    def senales(self, placa=None):
        from ..hw import kit_fsm
        return kit_fsm.senales(self.vista._to_dict(), placa)

    def armar(self, config):
        from ..hw import kit_fsm
        kit = kit_fsm.armar(self.vista._to_dict(), config)
        config.anotar(kit, secuencial=True)
        return kit


class VentanaKit:
    """Toplevel del kit. `config` es el ConfigKit del panel; `al_cambiar` se llama
    cuando algo de la configuracion cambia (el proyecto queda con cambios)."""

    def __init__(self, padre, config, fuente, al_cambiar=None):
        self.config = config
        self.fuente = fuente
        self.al_cambiar = al_cambiar or (lambda: None)
        self.kit = None                 # el ultimo Kit armado (para la vista previa)
        self.placa = None               # la plataforma que se esta viendo

        self.win = tk.Toplevel(padre)
        self.win.title("Kit de hardware - ktool")
        self.win.geometry("1180x760")
        self.win.minsize(900, 560)

        self._barra_inferior()
        cuerpo = ttk.Frame(self.win, padding=(8, 8, 8, 0))
        cuerpo.pack(fill=tk.BOTH, expand=True)
        self._lista_de_plataformas(cuerpo)
        self.notebook = ttk.Notebook(cuerpo)
        self.notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        self.tab_pines = ttk.Frame(self.notebook, padding=6)
        self.tab_ajustes = ttk.Frame(self.notebook, padding=10)
        self.tab_archivos = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.tab_pines, text="Pines")
        self.notebook.add(self.tab_ajustes, text="Ajustes")
        self.notebook.add(self.tab_archivos, text="Archivos")
        self._armar_tab_archivos()
        self.notebook.bind("<<NotebookTabChanged>>", lambda _e: self._al_cambiar_pestana())

        primera = self.config.elegidas[0] if self.config.elegidas else hw_kit.PLATAFORMAS[0][0]
        self.arbol.selection_set(primera)
        self.arbol.see(primera)

    # ----------------------------------------------------------- izquierda
    def _lista_de_plataformas(self, padre):
        marco = ttk.Frame(padre)
        marco.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(marco, text="Plataformas").pack(anchor="w")
        self.arbol = ttk.Treeview(marco, columns=("usar", "estado"), show="tree headings",
                                  height=20, selectmode="browse")
        self.arbol.heading("#0", text="Placa o salida")
        self.arbol.heading("usar", text="Usar")
        self.arbol.heading("estado", text="Estado")
        self.arbol.column("#0", width=215)
        self.arbol.column("usar", width=40, anchor="center")
        self.arbol.column("estado", width=62, anchor="center")
        for clave, titulo in hw_kit.PLATAFORMAS:
            marca = USAR if clave in self.config.elegidas else NO_USAR
            self.arbol.insert("", tk.END, iid=clave, text=titulo, values=(marca, ""))
        self.arbol.pack(fill=tk.Y, expand=True, pady=(4, 0))
        self.arbol.bind("<<TreeviewSelect>>", lambda _e: self._al_seleccionar())
        self.arbol.bind("<Button-1>", self._al_clic_en_lista, add="+")
        self.arbol.bind("<space>", lambda _e: self._alternar(self.placa))
        ttk.Label(marco, foreground=GRIS, justify=tk.LEFT, text=(
            "Clic en Usar (o la barra espaciadora)\n"
            "para generar esa plataforma.")).pack(anchor="w", pady=(6, 0))

    def _al_clic_en_lista(self, evento):
        """Un clic en la columna Usar palomea o despalomea ese renglon."""
        if self.arbol.identify_column(evento.x) != "#1":
            return None
        renglon = self.arbol.identify_row(evento.y)
        if renglon:
            self._alternar(renglon)
        return None

    def _alternar(self, placa):
        if placa is None:
            return
        usar = placa not in self.config.elegidas
        self.config.elegir(placa, usar)
        self.arbol.set(placa, "usar", USAR if usar else NO_USAR)
        self.al_cambiar()
        self._rearmar()

    def _al_seleccionar(self):
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        self.placa = seleccion[0]
        self._mostrar_pines()
        self._mostrar_ajustes()
        self._rearmar()

    def _al_cambiar_pestana(self):
        if self.notebook.select() == str(self.tab_archivos):
            self._rearmar()

    # ---------------------------------------------------------------- Pines
    def _mostrar_pines(self):
        for hijo in self.tab_pines.winfo_children():
            hijo.destroy()
        self.planificador = None
        if self.placa not in placas.PLACAS_CON_PINES:
            ttk.Label(self.tab_pines, foreground=GRIS, text=(
                "Esta salida no tiene pines que elegir: no se graba en una placa.")).pack(
                anchor="w")
            return
        from .pin_planner import PinPlanner
        senales = self.fuente.senales(self.placa)
        asignados = self.config.pines.get(self.placa)
        if isinstance(asignados, list):     # lista de --pines o de un proyecto viejo
            asignados = dict(zip([s for s, _d in senales], asignados))
        self.planificador = PinPlanner(self.tab_pines, self.placa, senales,
                                       asignacion=asignados or {},
                                       al_cambiar=self._al_cambiar_pines)
        self.planificador.pack(fill=tk.BOTH, expand=True)
        if not asignados:
            # sin pines fijos el kit usa los de ktool: se muestran desde el
            # principio, para que el dibujo diga donde va cada senal
            self.planificador.elegir_automatico()

    def _al_cambiar_pines(self, asignacion):
        self.config.pines[self.placa] = dict(asignacion)
        self.al_cambiar()
        self._rearmar()

    # -------------------------------------------------------------- Ajustes
    def _mostrar_ajustes(self):
        for hijo in self.tab_ajustes.winfo_children():
            hijo.destroy()
        lista = hw_ajustes.de(self.placa)
        if not lista:
            ttk.Label(self.tab_ajustes, foreground=GRIS, text=(
                "Esta plataforma no tiene ajustes: se genera con los valores de su hoja "
                "de datos.")).grid(row=0, column=0, sticky="w")
            return
        actuales = self.config.valores(self.placa)
        for fila, a in enumerate(lista):
            ttk.Label(self.tab_ajustes, text=a.etiqueta + ":").grid(
                row=2 * fila, column=0, sticky="w", pady=(6, 0))
            var = tk.StringVar(value=(_numero(actuales[a.clave]) if a.opciones is None
                                      else actuales[a.clave]))
            celda = ttk.Frame(self.tab_ajustes)
            celda.grid(row=2 * fila, column=1, sticky="w", padx=6, pady=(6, 0))
            if a.opciones is None:
                ttk.Entry(celda, textvariable=var, width=18).pack(side=tk.LEFT)
            else:
                ttk.Combobox(celda, textvariable=var, state="readonly",
                             values=a.opciones, width=44).pack(side=tk.LEFT)
            var.trace_add("write", lambda *_x, clave=a.clave, v=var: self._al_cambiar_ajuste(
                clave, v.get()))
            if a.clave == "frecuencia_hz":
                ttk.Button(celda, text="Calculadora...",
                           command=self._abrir_calculadora).pack(side=tk.LEFT, padx=6)
            ttk.Label(self.tab_ajustes, text=a.ayuda + (" Solo en maquinas de estado."
                                                        if a.secuencial else ""),
                      foreground=GRIS, wraplength=560, justify=tk.LEFT).grid(
                row=2 * fila + 1, column=1, sticky="w", padx=6)
        self.ajustes_estado = ttk.Label(self.tab_ajustes, foreground="#a33", text="")
        self.ajustes_estado.grid(row=2 * len(lista), column=0, columnspan=3, sticky="w",
                                 pady=(10, 0))

    def _al_cambiar_ajuste(self, clave, valor):
        propios = self.config.ajustes.setdefault(self.placa, {})
        propios[clave] = valor
        try:
            hw_ajustes.con_omision(self.placa, propios)
            self.ajustes_estado.config(text="")
        except ValueError as e:
            self.ajustes_estado.config(text=str(e))
            return
        self.al_cambiar()

    def _abrir_calculadora(self):
        """La calculadora con el reloj de esta placa; 'Usar en el kit' llena la
        frecuencia (y en la MAX II, el reloj de la tarjeta)."""
        from .calculadora import VentanaCalculadora
        valores = self.config.valores(self.placa)
        if "reloj_hz" in valores:
            entrada = valores["reloj_hz"]
        elif "oscilador" in valores:
            entrada = hw_ajustes.hz(valores["oscilador"])
        else:
            entrada = 16000000
        placa = self.placa

        def usar(f_salida, f_entrada):
            propios = self.config.ajustes.setdefault(placa, {})
            propios["frecuencia_hz"] = f"{f_salida:g}"
            if "reloj_hz" in valores:
                propios["reloj_hz"] = f"{f_entrada:g}"
            self.al_cambiar()
            if self.placa == placa:
                self._mostrar_ajustes()

        VentanaCalculadora(self.win, f_entrada=entrada,
                           f_salida=valores.get("frecuencia_hz", 1.0), al_usar=usar,
                           destino=hw_kit.TITULO_PLATAFORMA[placa])

    # ------------------------------------------------------------- Archivos
    def _armar_tab_archivos(self):
        izquierda = ttk.Frame(self.tab_archivos)
        izquierda.pack(side=tk.LEFT, fill=tk.Y)
        self.lista_archivos = tk.Listbox(izquierda, width=28, exportselection=False,
                                         font=("Consolas", 9), activestyle="none")
        self.lista_archivos.pack(fill=tk.Y, expand=True)
        self.lista_archivos.bind("<<ListboxSelect>>", lambda _e: self._ver_archivo())
        self.archivo_motivo = ttk.Label(izquierda, foreground=GRIS, wraplength=240,
                                        justify=tk.LEFT, text="")
        self.archivo_motivo.pack(anchor="w", pady=(6, 0))

        derecha = ttk.Frame(self.tab_archivos)
        derecha.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        cabeza = ttk.Frame(derecha)
        cabeza.pack(fill=tk.X)
        self.archivo_titulo = ttk.Label(cabeza, text="", font=("Consolas", 10, "bold"))
        self.archivo_titulo.pack(side=tk.LEFT)
        self.archivo_estado = ttk.Label(cabeza, text="", foreground=GRIS)
        self.archivo_estado.pack(side=tk.LEFT, padx=8)
        ttk.Button(cabeza, text="Restaurar el generado",
                   command=self._restaurar_archivo).pack(side=tk.RIGHT)
        ttk.Button(cabeza, text="Guardar cambios",
                   command=self._guardar_archivo).pack(side=tk.RIGHT, padx=6)
        boton_copiar(cabeza, lambda: self.texto.get("1.0", "end-1c")).pack(side=tk.RIGHT)

        caja = ttk.Frame(derecha)
        caja.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.texto = tk.Text(caja, wrap="none", font=("Consolas", 10), undo=True)
        barra_v = ttk.Scrollbar(caja, orient="vertical", command=self.texto.yview)
        barra_h = ttk.Scrollbar(caja, orient="horizontal", command=self.texto.xview)
        self.texto.configure(yscrollcommand=barra_v.set, xscrollcommand=barra_h.set)
        barra_v.pack(side=tk.RIGHT, fill=tk.Y)
        barra_h.pack(side=tk.BOTTOM, fill=tk.X)
        self.texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rutas_listadas = []

    def _rearmar(self):
        """Vuelve a armar el kit en memoria y refresca el estado y los archivos."""
        try:
            self.kit = self.fuente.armar(self.config)
        except ValueError as e:
            self.kit = None
            self.estado.config(text=str(e), foreground="#a33")
            self._llenar_archivos()
            return
        estados = {plataforma: estado for plataforma, estado, _d in self.kit.resumen}
        for clave, titulo in hw_kit.PLATAFORMAS:
            if clave not in self.config.elegidas:
                texto = ""
            else:
                texto = {"listo": "listo", "bloqueado": "no cabe"}.get(estados.get(titulo), "")
            self.arbol.set(clave, "estado", texto)
        listos = sum(1 for _p, e, _d in self.kit.resumen if e == "listo")
        self.estado.config(foreground=GRIS, text=(
            f"{listos} de {len(self.kit.resumen)} plataformas listas"
            + (f"; {len(self.kit.editados)} archivo(s) editados a mano" if self.kit.editados
               else "")))
        self._llenar_archivos()

    def _llenar_archivos(self):
        """Los archivos de la plataforma que se esta viendo."""
        anterior = self._ruta_actual()
        self.lista_archivos.delete(0, tk.END)
        self._rutas_listadas = []
        self.archivo_motivo.config(text="")
        if self.kit is None or self.placa is None:
            return
        titulo = hw_kit.TITULO_PLATAFORMA[self.placa]
        if self.placa not in self.config.elegidas:
            self.archivo_motivo.config(text="Esta plataforma no esta marcada en Usar.")
        for plataforma, estado, detalle in self.kit.resumen:
            if plataforma == titulo and estado == "bloqueado":
                self.archivo_motivo.config(text=detalle)
        for ruta in self.kit.archivos_de.get(titulo, []):
            marca = "  (editado)" if ruta in self.kit.editados else ""
            self.lista_archivos.insert(tk.END, ruta + marca)
            self._rutas_listadas.append(ruta)
        if anterior in self._rutas_listadas:
            indice = self._rutas_listadas.index(anterior)
        else:
            indice = 0 if self._rutas_listadas else None
        if indice is not None:
            self.lista_archivos.selection_set(indice)
        self._ver_archivo()

    def _ruta_actual(self):
        seleccion = self.lista_archivos.curselection()
        return self._rutas_listadas[seleccion[0]] if seleccion else None

    def _ver_archivo(self):
        ruta = self._ruta_actual()
        self.texto.delete("1.0", tk.END)
        if ruta is None:
            self.archivo_titulo.config(text="")
            self.archivo_estado.config(text="")
            return
        self.texto.insert("1.0", self.kit.archivos[ruta])
        self.texto.edit_reset()
        self.archivo_titulo.config(text=ruta)
        self.archivo_estado.config(text=("editado a mano: se conserva al regenerar"
                                         if ruta in self.kit.editados else "generado"))

    def _guardar_archivo(self):
        ruta = self._ruta_actual()
        if ruta is None:
            return
        self.config.editados[ruta] = self.texto.get("1.0", "end-1c")
        self.al_cambiar()
        self._rearmar()

    def _restaurar_archivo(self):
        ruta = self._ruta_actual()
        if ruta is None or ruta not in self.config.editados:
            return
        if not messagebox.askyesno("Restaurar", f"Se pierden los cambios a mano de\n{ruta}.\n"
                                   "Seguir?", parent=self.win):
            return
        del self.config.editados[ruta]
        self.al_cambiar()
        self._rearmar()

    # ------------------------------------------------------- barra de abajo
    def _barra_inferior(self):
        barra = ttk.Frame(self.win, padding=8)
        barra.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(barra, text="Carpeta:").pack(side=tk.LEFT)
        self.carpeta = tk.StringVar(value=self.config.carpeta)
        ttk.Entry(barra, textvariable=self.carpeta, width=56).pack(side=tk.LEFT, padx=4)
        self.carpeta.trace_add("write", lambda *_x: self._al_cambiar_carpeta())
        ttk.Button(barra, text="Elegir...", command=self._elegir_carpeta).pack(side=tk.LEFT)
        ttk.Button(barra, text="Escribir kit", command=self.escribir).pack(side=tk.LEFT, padx=(12, 0))
        self.abrir = ttk.Button(barra, text="Abrir carpeta", state="disabled",
                                command=lambda: os.startfile(self.config.carpeta))
        if hasattr(os, "startfile"):
            self.abrir.pack(side=tk.LEFT, padx=6)
        self.estado = ttk.Label(barra, foreground=GRIS, text="")
        self.estado.pack(side=tk.LEFT, padx=8)

    def _al_cambiar_carpeta(self):
        self.config.carpeta = self.carpeta.get().strip()
        self.al_cambiar()

    def _elegir_carpeta(self):
        elegida = filedialog.askdirectory(title="Carpeta del kit", parent=self.win,
                                          initialdir=os.path.dirname(self.config.carpeta))
        if elegida:
            self.carpeta.set(elegida)

    def escribir(self):
        """Escribe los archivos de las plataformas marcadas en la carpeta."""
        carpeta = self.config.carpeta
        if not carpeta:
            messagebox.showerror("Falta la carpeta", "Escribe o elige una carpeta.",
                                 parent=self.win)
            return
        if os.path.isdir(carpeta) and os.listdir(carpeta):
            if not messagebox.askyesno(
                    "La carpeta ya tiene archivos",
                    f"{carpeta}\n\nya tiene archivos. Los del kit se reemplazan; los demas "
                    "se quedan. Seguir?", parent=self.win):
                return
        self._rearmar()
        if self.kit is None:
            return
        hw_kit.escribir(self.kit, carpeta)
        self.abrir.config(state="normal")
        listos = sum(1 for _p, e, _d in self.kit.resumen if e == "listo")
        self.estado.config(foreground=GRIS, text=(
            f"Escritos {len(self.kit.archivos)} archivos ({listos} plataformas) en {carpeta}"))
