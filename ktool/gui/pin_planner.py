"""Planificador de pines al estilo del Pin Planner de Quartus.

En vez de escribir "26, 28, 33" a mano, se ve el componente real (el chip con
sus patas o la tarjeta con sus cabezales) y se le da clic a cada pata:

    1. clic en una senal de la lista (queda "en la mano");
    2. clic en una pata libre: la senal queda ahi y pasa a la siguiente;
    3. clic en una pata ocupada: la suelta.

Tambien se puede arrastrar una senal de la lista a la pata. Las patas que no
llevan senal (VDD, GND, JTAG, la flash del ESP32...) se ven en gris y no
responden. Todo aviso va en la barra de estado de abajo, sin ventanas
emergentes: una salida en un pin que solo es entrada se rechaza con el motivo,
y un pin de reserva se acepta con su aviso.

Las reglas (que pin acepta que senal) viven en hw/encapsulados.puede_ir y el
dibujo en hw/encapsulados.geometria: esta ventana solo los pinta y responde.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..hw import encapsulados, placas
from ..hw.modelo import Bloqueo, asignar_pines
from .. import theme

FUENTE = ("Segoe UI", 9)
GRIS = "#777"

# Colores de las senales: azules para las entradas, ocres y rojizos para las
# salidas; asi se distingue de un vistazo que va a cada lado. Cada senal toma
# el siguiente tono de su familia.
COLORES_ENTRADA = ["#1f5fa8", "#2a7f9e", "#3a4f9a", "#1b6f6a", "#4b72b8", "#22568a"]
COLORES_SALIDA = ["#b35900", "#a63d2a", "#8c6a00", "#c0502d", "#8f3b1b", "#a8741f"]
COLOR_RELOJ = "#6b3fa0"
COLOR_RESET = "#8b2252"

# Tonos del dibujo
FONDO_LIENZO = "#ffffff"
CUERPO_CHIP = "#fbfbfb"
CUERPO_PLACA = "#eef0f2"
TINTA = "#222222"
PATA_LIBRE = "#ffffff"
PATA_FUERA = "#d4d4d4"
TEXTO_FUERA = "#9a9a9a"

NOMBRE_DIRECCION = {"entrada": "entrada", "salida": "salida", "reloj": "reloj", "reset": "reset"}

ZOOM_MINIMO = 0.7
ZOOM_MAXIMO = 1.5


class _Reparto:
    """Lo minimo que modelo.asignar_pines lee de un Circuito: los nombres de
    las entradas y de las salidas. Existe para pedirle a ktool un reparto sin
    armar una tabla de verdad."""

    def __init__(self, entradas, salidas):
        self.entradas = list(entradas)
        self.salidas = list(salidas)

    @property
    def n_entradas(self):
        return len(self.entradas)

    @property
    def n_salidas(self):
        return len(self.salidas)


class PinPlanner(ttk.Frame):
    """El planificador completo: lista de senales, dibujo y barra de estado.

    placa       nombre corto de placas.PLACAS_CON_PINES ("max2", "uno_nano"...)
    senales     [(nombre, direccion)], direccion "entrada", "salida", "reloj"
                o "reset"
    asignacion  {senal: id del pin} inicial (opcional)
    al_cambiar  funcion que recibe {senal: id} en cada cambio (opcional)
    """

    def __init__(self, padre, placa, senales, asignacion=None, al_cambiar=None):
        super().__init__(padre)
        self.placa = placa
        self.senales = list(senales)
        self.al_cambiar = al_cambiar
        self.asignacion = {}
        self.armada = None
        self.dibujo = encapsulados.dibujo_de(placa)
        self.zoom = 1.0
        self._desplazamiento = (0.0, 0.0)
        self._zonas = []            # (x0, y0, x1, y1, numero) ya en pixeles del lienzo
        self._mensaje = ""
        self._arrastrada = None
        self._colores = self._repartir_colores()

        self._armar_lista()
        self._armar_dibujo()
        self.estado = ttk.Label(self, text="", font=FUENTE, foreground=GRIS, anchor="w")
        self.estado.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 3))
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        descartadas = []
        for senal, pin in (asignacion or {}).items():
            direccion = self._direccion(senal)
            if direccion is None:
                descartadas.append(senal)
                continue
            puede, _aviso = encapsulados.puede_ir(placa, pin, direccion)
            if puede and pin not in self.asignacion.values():
                self.asignacion[senal] = pin
            else:
                descartadas.append(senal)
        self._refrescar_lista()
        self._armar_siguiente()
        if descartadas:
            self._avisar("Se descartaron pines que no sirven en esta placa: "
                         + ", ".join(descartadas) + ".")
        else:
            self._avisar("Elija una senal de la lista y luego la pata donde va.")

    # ------------------------------------------------------------ armado

    def _armar_lista(self):
        """La columna izquierda: las senales con su pata y los dos botones."""
        caja = ttk.Frame(self)
        caja.grid(row=0, column=0, sticky="ns", padx=(4, 6), pady=4)
        ttk.Label(caja, text="Senales", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.lista = ttk.Treeview(caja, columns=("senal", "direccion", "pata"),
                                  show="headings", selectmode="browse", height=14)
        self.lista.heading("senal", text="Senal")
        self.lista.heading("direccion", text="Tipo")
        self.lista.heading("pata", text="Pata")
        self.lista.column("senal", width=90, stretch=False)
        self.lista.column("direccion", width=58, stretch=False)
        self.lista.column("pata", width=120, stretch=False)
        self.lista.pack(fill=tk.Y, expand=True)
        for nombre, direccion in self.senales:
            self.lista.insert("", "end", iid=nombre, tags=(nombre,))
            self.lista.tag_configure(nombre, foreground=self._colores[nombre])
        self.lista.bind("<<TreeviewSelect>>", self._al_elegir_senal)
        self.lista.bind("<ButtonPress-1>", self._al_tomar_senal, add="+")
        self.lista.bind("<ButtonRelease-1>", self._al_soltar_senal, add="+")
        botones = ttk.Frame(caja)
        botones.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(botones, text="Que ktool las elija",
                   command=self.elegir_automatico).pack(fill=tk.X)
        ttk.Button(botones, text="Soltar todas", command=self.soltar_todas).pack(fill=tk.X,
                                                                                pady=(4, 0))

    def _armar_dibujo(self):
        """La columna derecha: la vista (si la placa tiene dos) y el lienzo con
        sus barras."""
        caja = ttk.Frame(self)
        caja.grid(row=0, column=1, sticky="nsew", pady=4, padx=(0, 4))
        caja.columnconfigure(0, weight=1)
        caja.rowconfigure(1, weight=1)
        dibujos = encapsulados.DIBUJOS_DE_PLACA[self.placa]
        if len(dibujos) > 1:
            barra = ttk.Frame(caja)
            barra.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))
            ttk.Label(barra, text="Vista:", font=FUENTE).pack(side=tk.LEFT)
            self._titulos_vista = {encapsulados.ENCAPSULADOS[d]["titulo"]: d for d in dibujos}
            self.vista = tk.StringVar(value=encapsulados.ENCAPSULADOS[self.dibujo]["titulo"])
            combo = ttk.Combobox(barra, textvariable=self.vista, state="readonly", width=34,
                                 values=list(self._titulos_vista))
            combo.pack(side=tk.LEFT, padx=(4, 0))
            combo.bind("<<ComboboxSelected>>", self._al_cambiar_vista)
        self.lienzo = tk.Canvas(caja, background=FONDO_LIENZO, highlightthickness=1,
                                highlightbackground="#c8c8c8", width=560, height=440)
        vertical = ttk.Scrollbar(caja, orient="vertical", command=self.lienzo.yview)
        horizontal = ttk.Scrollbar(caja, orient="horizontal", command=self.lienzo.xview)
        self.lienzo.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.lienzo.grid(row=1, column=0, sticky="nsew")
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal.grid(row=2, column=0, sticky="ew")
        self.lienzo.bind("<Configure>", self._al_cambiar_tamano)
        self.lienzo.bind("<Motion>", self._al_mover)
        self.lienzo.bind("<Leave>", lambda _e: self._mostrar(self._mensaje))
        self.lienzo.bind("<Button-1>", self._al_clic)
        self.lienzo.bind("<MouseWheel>", self._al_rueda)

    def _repartir_colores(self):
        """Un color por senal, por familia: la n-esima entrada toma el n-esimo
        azul y la n-esima salida el n-esimo ocre."""
        colores = {}
        cuenta_entradas = cuenta_salidas = 0
        for nombre, direccion in self.senales:
            if direccion == "salida":
                colores[nombre] = COLORES_SALIDA[cuenta_salidas % len(COLORES_SALIDA)]
                cuenta_salidas += 1
            elif direccion == "reloj":
                colores[nombre] = COLOR_RELOJ
            elif direccion == "reset":
                colores[nombre] = COLOR_RESET
            else:
                colores[nombre] = COLORES_ENTRADA[cuenta_entradas % len(COLORES_ENTRADA)]
                cuenta_entradas += 1
        return colores

    # ------------------------------------------------------- lo publico

    def obtener(self):
        """{senal: id del pin} de las senales que ya tienen pata, en el orden de
        la lista."""
        return {nombre: self.asignacion[nombre] for nombre, _d in self.senales
                if nombre in self.asignacion}

    def soltar_todas(self):
        """Deja todas las senales sin pata."""
        self.asignacion.clear()
        self._cambio("Se soltaron todas las senales.")
        self._armar_siguiente()

    def elegir_automatico(self):
        """Reparte todas las senales como lo haria ktool sin pines del usuario
        (modelo.asignar_pines). El reloj y el reset van primero a los pines
        reservados para ellos, si la placa los tiene (GCLK y DEV_CLRn de la
        MAX II); en las demas placas cuentan como entradas."""
        info = placas.PLACAS_CON_PINES[self.placa]
        usables = encapsulados.asignables(self.placa)
        principal = encapsulados.ENCAPSULADOS[encapsulados.dibujo_de(self.placa)]
        preferidos = principal.get("preferidos", {})
        nueva = {}
        resto = []
        for nombre, direccion in self.senales:
            if direccion in ("reloj", "reset"):
                libres = [pin for pin in preferidos.get(direccion, [])
                          if pin in usables and pin not in nueva.values()]
                if libres:
                    nueva[nombre] = libres[0]
                    continue
            resto.append((nombre, direccion))
        entradas = [nombre for nombre, direccion in resto if direccion != "salida"]
        salidas = [nombre for nombre, direccion in resto if direccion == "salida"]
        sin_especiales = dict(info)
        sin_especiales["entradas"] = [p for p in info["entradas"] if p not in nueva.values()]
        sin_especiales["salidas"] = [p for p in info["salidas"] if p not in nueva.values()]
        try:
            renglones = asignar_pines(_Reparto(entradas, salidas), sin_especiales)
        except Bloqueo as error:
            self._avisar(f"No alcanzan los pines: {error}.")
            return
        avisos = []
        for renglon in renglones:
            nueva[renglon["senal"]] = renglon["pin"]
            if renglon["aviso"]:
                avisos.append(f"{renglon['pin']} {renglon['aviso']}")
        self.asignacion = nueva
        texto = f"ktool eligio {len(nueva)} pines."
        if avisos:
            texto += " Aviso: " + "; ".join(avisos) + "."
        self._cambio(texto)
        self._armar_siguiente()

    def actualizar_senales(self, senales):
        """Cambia la lista de senales (la tabla cambio) y conserva la pata de
        las que siguen con el mismo nombre y tipo."""
        anteriores = dict(self.senales)
        self.senales = list(senales)
        self._colores = self._repartir_colores()
        conservada = {}
        for nombre, direccion in self.senales:
            if nombre in self.asignacion and anteriores.get(nombre) == direccion:
                conservada[nombre] = self.asignacion[nombre]
        self.asignacion = conservada
        for iid in self.lista.get_children():
            self.lista.delete(iid)
        for nombre, _direccion in self.senales:
            self.lista.insert("", "end", iid=nombre, tags=(nombre,))
            self.lista.tag_configure(nombre, foreground=self._colores[nombre])
        self.armada = None
        self._cambio("")
        self._armar_siguiente()

    # ---------------------------------------------------- las acciones

    def asignar(self, senal, numero):
        """Pone `senal` en la pata `numero` del dibujo actual si las reglas lo
        permiten. Devuelve True si quedo. Es lo que hacen el clic y el
        arrastre, y lo que usan las pruebas."""
        enc = encapsulados.ENCAPSULADOS[self.dibujo]
        pata = enc["patas"][numero]
        lugar = encapsulados.posicion(self.dibujo, numero)
        if not self._usable(pata):
            self._avisar(f"{pata.etiqueta} ({lugar}) es "
                         f"{encapsulados.NOMBRE_TIPO[pata.tipo]}: no lleva senal.")
            return False
        ocupante = self._ocupante(pata.id)
        if ocupante is not None and ocupante != senal:
            self._avisar(f"{pata.etiqueta} ({lugar}) ya tiene {ocupante}: sueltela primero.")
            return False
        puede, texto = encapsulados.puede_ir(self.placa, pata.id, self._direccion(senal))
        if not puede:
            self._avisar(f"{senal} no puede ir en {pata.etiqueta} ({lugar}). {texto}")
            return False
        self.asignacion[senal] = pata.id
        mensaje = f"{senal} quedo en {pata.etiqueta} ({lugar})."
        if texto:
            mensaje += f" Aviso: {texto}."
        self._cambio(mensaje)
        return True

    def soltar(self, numero):
        """Quita la senal que tenga la pata `numero`. Devuelve la senal o None."""
        pata = encapsulados.ENCAPSULADOS[self.dibujo]["patas"][numero]
        ocupante = self._ocupante(pata.id) if pata.id is not None else None
        if ocupante is None:
            return None
        del self.asignacion[ocupante]
        self._cambio(f"Se solto {ocupante} de {pata.etiqueta} "
                     f"({encapsulados.posicion(self.dibujo, numero)}).")
        return ocupante

    def _al_clic(self, evento):
        """Clic en el lienzo: suelta una pata ocupada o pone la senal en mano."""
        numero = self._pata_en(evento.x, evento.y)
        if numero is None:
            return
        pata = encapsulados.ENCAPSULADOS[self.dibujo]["patas"][numero]
        if not self._usable(pata):
            self._avisar(f"{pata.etiqueta} ({encapsulados.posicion(self.dibujo, numero)}) es "
                         f"{encapsulados.NOMBRE_TIPO[pata.tipo]}: no lleva senal.")
            return
        if self._ocupante(pata.id) is not None:
            self.soltar(numero)
            self._armar_siguiente()
            return
        if self.armada is None:
            self._avisar("Elija primero una senal de la lista.")
            return
        if self.asignar(self.armada, numero):
            self._armar_siguiente()

    def _al_tomar_senal(self, evento):
        """Empieza un posible arrastre desde la lista."""
        fila = self.lista.identify_row(evento.y)
        self._arrastrada = fila or None

    def _al_soltar_senal(self, evento):
        """Si el arrastre termina sobre una pata, la senal queda ahi."""
        senal, self._arrastrada = self._arrastrada, None
        if not senal:
            return
        debajo = self.winfo_containing(evento.x_root, evento.y_root)
        if debajo is not self.lienzo:
            return
        x = evento.x_root - self.lienzo.winfo_rootx()
        y = evento.y_root - self.lienzo.winfo_rooty()
        numero = self._pata_en(x, y)
        if numero is not None and self.asignar(senal, numero):
            self._armar_siguiente()

    def _al_elegir_senal(self, _evento=None):
        """La senal elegida en la lista queda en la mano."""
        elegida = self.lista.selection()
        nueva = elegida[0] if elegida else None
        if nueva == self.armada:
            # la eligio _armar_siguiente: el mensaje del ultimo cambio se queda
            return
        self.armada = nueva
        if nueva is not None:
            self._avisar(f"{nueva} en la mano: de clic en la pata donde va.")
        self._dibujar()

    def _al_mover(self, evento):
        """Al pasar por una pata, la barra dice que es."""
        numero = self._pata_en(evento.x, evento.y)
        self.lienzo.delete("encima")
        if numero is None:
            self._mostrar(self._mensaje)
            self.lienzo.configure(cursor="")
            return
        pata = encapsulados.ENCAPSULADOS[self.dibujo]["patas"][numero]
        for x0, y0, x1, y1, n in self._zonas:
            if n == numero:
                self.lienzo.create_rectangle(x0, y0, x1, y1, outline=theme.SEL_BG,
                                             tags=("encima",))
        self.lienzo.configure(cursor="hand2" if self._usable(pata) else "")
        self._mostrar(self._descripcion(numero))

    def _al_cambiar_vista(self, _evento=None):
        """Cambia entre los dibujos de la misma placa (Uno y Nano)."""
        self.dibujo = self._titulos_vista[self.vista.get()]
        self._refrescar_lista()
        self._ajustar_zoom(forzar=True)

    def _al_cambiar_tamano(self, _evento=None):
        self._ajustar_zoom()

    def _al_rueda(self, evento):
        """La rueda desplaza en vertical; con Shift, en horizontal."""
        pasos = -1 if evento.delta > 0 else 1
        if evento.state & 0x0001:
            self.lienzo.xview_scroll(pasos, "units")
        else:
            self.lienzo.yview_scroll(pasos, "units")

    # ------------------------------------------------------- el dibujo

    def _ajustar_zoom(self, forzar=False):
        """Escala el dibujo para que quepa en el lienzo, entre ZOOM_MINIMO y
        ZOOM_MAXIMO; si ni al minimo cabe, quedan las barras."""
        geo = encapsulados.geometria(self.dibujo)
        ancho = max(self.lienzo.winfo_width(), 50)
        alto = max(self.lienzo.winfo_height(), 50)
        ajuste = min((ancho - 4) / geo["ancho"], (alto - 4) / geo["alto"])
        ajuste = max(ZOOM_MINIMO, min(ZOOM_MAXIMO, ajuste))
        if forzar or abs(ajuste - self.zoom) > 0.02 or not self._zonas:
            self.zoom = ajuste
        self._dibujar()

    def _dibujar(self):
        """Pinta el componente completo con la asignacion actual."""
        lienzo = self.lienzo
        lienzo.delete("all")
        nombre = self.dibujo
        enc = encapsulados.ENCAPSULADOS[nombre]
        geo = encapsulados.geometria(nombre)
        z = self.zoom
        dx = max(0.0, (lienzo.winfo_width() - geo["ancho"] * z) / 2.0)
        dy = max(0.0, (lienzo.winfo_height() - geo["alto"] * z) / 2.0)
        self._desplazamiento = (dx, dy)

        def punto(x, y):
            return dx + x * z, dy + y * z

        def caja(rect):
            a, b = punto(rect[0], rect[1])
            c, d = punto(rect[2], rect[3])
            return a, b, c, d

        def fuente(tamano, negrita=False):
            pixeles = -max(7, int(round(tamano * z)))
            return ("Segoe UI", pixeles, "bold") if negrita else ("Segoe UI", pixeles)

        def texto(contenido, lugar, tamano, color, negrita=False):
            x, y, ancla, vertical = lugar
            px, py = punto(x, y)
            if ancla == "inicio":
                anchor = "w"
            elif ancla == "fin":
                anchor = "e"
            else:
                anchor = "center"
            lienzo.create_text(px, py, text=str(contenido), anchor=anchor,
                               angle=90 if vertical else 0, fill=color,
                               font=fuente(tamano, negrita))

        x0, y0, x1, y1 = geo["cuerpo"]
        texto(enc["titulo"], (geo["ancho"] / 2.0, encapsulados.ALTO_TITULO / 2.0, "medio", False),
              13, TINTA, negrita=True)
        es_placa = enc["forma"] == "placa"
        lienzo.create_rectangle(*caja(geo["cuerpo"]), outline=TINTA,
                                fill=CUERPO_PLACA if es_placa else CUERPO_CHIP)
        tipo, rect, rotulo = encapsulados.marca_de_orientacion(nombre, geo)
        if tipo == "muesca":
            lienzo.create_arc(*caja(rect), start=180, extent=180, style="arc", outline=TINTA)
        elif tipo == "punto":
            lienzo.create_oval(*caja(rect), fill=TINTA, outline="")
        elif tipo == "conector":
            lienzo.create_rectangle(*caja(rect), fill="#d9d9d9", outline=TINTA)
            texto(rotulo, ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2, "medio", False),
                  9, TINTA)
        texto(enc["titulo"].split(" (")[0],
              ((x0 + x1) / 2, (y0 + y1) / 2, "medio", enc["forma"] == "dip"), 12, "#b0b0b0")

        por_pin = {pin: senal for senal, pin in self.asignacion.items()}
        en_mano = self.asignacion.get(self.armada) if self.armada else None
        self._zonas = []
        for numero in sorted(geo["patas"]):
            lugar = geo["patas"][numero]
            pata = enc["patas"][numero]
            usable = self._usable(pata)
            senal = por_pin.get(pata.id) if pata.id is not None else None
            if senal is not None:
                relleno, borde = self._colores[senal], self._colores[senal]
            elif usable:
                relleno, borde = PATA_LIBRE, TINTA
            else:
                relleno, borde = PATA_FUERA, TEXTO_FUERA
            grosor = 2 if (en_mano is not None and pata.id == en_mano) else 1
            lienzo.create_rectangle(*caja(lugar["pata"]), fill=relleno, outline=borde,
                                    width=grosor)
            texto(pata.etiqueta, lugar["etiqueta"], 11, TINTA if usable else TEXTO_FUERA)
            if lugar["numero"] is not None:
                texto(numero, lugar["numero"], 9, GRIS)
            if senal is not None:
                texto(senal, lugar["senal"], 11, self._colores[senal], negrita=True)
            self._zonas.append(caja(lugar["zona"]) + (numero,))

        lienzo.configure(scrollregion=(0, 0, dx * 2 + geo["ancho"] * z, dy * 2 + geo["alto"] * z))

    # ---------------------------------------------------------- apoyo

    def _pata_en(self, x, y):
        """La pata bajo un punto de la ventana del lienzo, o None."""
        cx = self.lienzo.canvasx(x)
        cy = self.lienzo.canvasy(y)
        for x0, y0, x1, y1, numero in self._zonas:
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                return numero
        return None

    def _usable(self, pata):
        """Si la pata puede llevar una senal en esta placa."""
        return pata.id is not None and pata.id in encapsulados.asignables(self.placa)

    def _ocupante(self, pin):
        """La senal que tiene el pin, o None."""
        for senal, asignado in self.asignacion.items():
            if asignado == pin:
                return senal
        return None

    def _direccion(self, senal):
        for nombre, direccion in self.senales:
            if nombre == senal:
                return direccion
        return None

    def _descripcion(self, numero):
        """El texto de la barra al pasar por una pata."""
        pata = encapsulados.ENCAPSULADOS[self.dibujo]["patas"][numero]
        lugar = encapsulados.posicion(self.dibujo, numero)
        tipo = encapsulados.NOMBRE_TIPO[pata.tipo]
        partes = [f"{lugar[0].upper()}{lugar[1:]}: {pata.funciones}."]
        if not self._usable(pata):
            partes.append(f"{tipo[0].upper()}{tipo[1:]}, no lleva senal.")
        else:
            datos = encapsulados.asignables(self.placa)[pata.id]
            partes.append(f"Pin {pata.id}.")
            if datos["solo_entrada"]:
                partes.append("Solo entrada.")
            if datos["solo_para"]:
                partes.append(f"Solo para {datos['solo_para']}.")
            if datos["aviso"] and not datos["solo_para"]:
                partes.append(f"Aviso: {datos['aviso']}.")
            ocupante = self._ocupante(pata.id)
            if ocupante is not None:
                partes.append(f"Tiene {ocupante}; clic para soltarla.")
        return " ".join(partes)

    def _armar_siguiente(self):
        """Deja en la mano la primera senal que no tiene pata, para asignar
        varias seguidas sin volver a la lista."""
        siguiente = None
        for nombre, _direccion in self.senales:
            if nombre not in self.asignacion:
                siguiente = nombre
                break
        if siguiente is None:
            self.lista.selection_remove(self.lista.selection())
            self.armada = None
            self._dibujar()
            return
        self.lista.selection_set(siguiente)
        self.lista.see(siguiente)
        self.armada = siguiente
        self._dibujar()

    def _refrescar_lista(self):
        """Pone en la lista la pata de cada senal."""
        for nombre, direccion in self.senales:
            pin = self.asignacion.get(nombre)
            if pin is None:
                pata = "sin pata"
            else:
                encontrada = encapsulados.pata_de(self.placa, pin, self.dibujo)
                if encontrada is None:
                    pata = str(pin)
                else:
                    lugar = encapsulados.posicion(self.dibujo, encontrada.numero)
                    pata = f"{encontrada.etiqueta} ({lugar})"
            self.lista.item(nombre, values=(nombre, NOMBRE_DIRECCION.get(direccion, direccion),
                                            pata))

    def _cambio(self, mensaje):
        """Despues de cada cambio: lista, dibujo, barra y aviso a quien escucha."""
        self._refrescar_lista()
        self._dibujar()
        if mensaje:
            self._avisar(mensaje)
        if self.al_cambiar is not None:
            self.al_cambiar(self.obtener())

    def _avisar(self, mensaje):
        """Un mensaje que se queda en la barra hasta el siguiente."""
        self._mensaje = mensaje
        self._mostrar(mensaje)

    def _mostrar(self, texto):
        self.estado.configure(text=texto)
