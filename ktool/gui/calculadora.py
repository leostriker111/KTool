"""Herramientas > Calculadora de frecuencia.

Dos calculos de la practica de multivibradores, con la onda dibujada:

    Divisor digital   de un reloj (50 MHz de la MAX II, el oscilador del PIC...)
                      a la frecuencia o el periodo que se pide: cuantos ciclos
                      dura T/2, cuantos bits lleva el contador y el error.
    555 astable       R1, R2 y C (valores comerciales) para una frecuencia.

Cada dato tiene su boton de copiar (el valor sin unidades, listo para pegar), y
abajo esta el mismo calculo ya escrito como codigo para cada hardware: el
divisor en VHDL, el retardo en C y en ensamblador del PIC, y en Arduino.

Las cuentas son de hw/reloj.py; esta ventana solo lee, dibuja y copia. Con
`al_usar`, el boton "Usar en el kit" manda la frecuencia a los ajustes del kit.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..hw import reloj
from .copiar import boton_copiar
from .resultados import con_ejemplo

GRIS = "#777"
ROJO = "#a33"

# Relojes de entrada comunes, para no tener que recordarlos
RELOJES = {
    "50 MHz (tarjeta MAX II)": "50M",
    "16 MHz (PIC18F45K50, interno)": "16M",
    "8 MHz (PIC18F4550, interno)": "8M",
    "16 MHz (Arduino Uno)": "16M",
    "1 kHz": "1k",
}
PREFIJOS = {"G": 1e9, "M": 1e6, "k": 1e3, "K": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12}


def leer_numero(texto):
    """'50M', '50 MHz', '1.5k', '3 s', '100n' -> numero. ValueError si no se lee.

    Acepta el prefijo SI pegado o separado y descarta la unidad (Hz, s, F,
    Ohm): la ventana ya dice que unidad va en cada cuadro."""
    limpio = texto.strip().replace(",", ".")
    for unidad in ("Hz", "hz", "Ohm", "ohm", "s", "F"):
        if limpio.endswith(unidad):
            limpio = limpio[: -len(unidad)].strip()
            break
    factor = 1.0
    if limpio and limpio[-1] in PREFIJOS:
        factor = PREFIJOS[limpio[-1]]
        limpio = limpio[:-1].strip()
    try:
        return float(limpio) * factor
    except ValueError:
        raise ValueError(f"no se entiende {texto!r}") from None


def _trozos(partes, comentario, orden):
    """Los trozos de codigo de reloj.py, cada uno con un renglon que dice donde va."""
    bloques = []
    for clave, donde in orden:
        if partes.get(clave):
            bloques.append(f"{comentario} --- {donde}\n{partes[clave]}")
    return "\n\n".join(bloques)


class VentanaCalculadora:
    """Toplevel de la calculadora. `al_usar(f_salida, f_entrada)` es opcional."""

    def __init__(self, padre, f_entrada=50e6, f_salida=1.0, al_usar=None, destino=None):
        self.al_usar = al_usar
        self.calculo = None
        self.win = tk.Toplevel(padre)
        self.win.title("Calculadora de frecuencia - ktool")
        self.win.geometry("980x720")
        self.win.minsize(820, 600)
        cuerpo = ttk.Frame(self.win, padding=10)
        cuerpo.pack(fill=tk.BOTH, expand=True)

        self.modo = tk.StringVar(value="divisor")
        modos = ttk.Frame(cuerpo)
        modos.pack(fill=tk.X)
        ttk.Radiobutton(modos, text="Divisor digital (contador)", value="divisor",
                        variable=self.modo, command=self._cambiar_modo).pack(side=tk.LEFT)
        ttk.Radiobutton(modos, text="555 astable", value="555", variable=self.modo,
                        command=self._cambiar_modo).pack(side=tk.LEFT, padx=(16, 0))

        self.entradas = ttk.Frame(cuerpo)
        self.entradas.pack(fill=tk.X, pady=(8, 0))
        self._entradas_divisor(f_entrada, f_salida)
        self._entradas_555()

        self.lienzo = tk.Canvas(cuerpo, height=150, background="white",
                                highlightthickness=1, highlightbackground="#ccc")
        self.lienzo.pack(fill=tk.X, pady=(10, 0))
        self.lienzo.bind("<Configure>", lambda _e: self._dibujar_onda())

        abajo = ttk.Frame(cuerpo)
        abajo.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.datos = ttk.Frame(abajo)
        self.datos.pack(side=tk.LEFT, fill=tk.Y)
        self.codigo = ttk.Notebook(abajo)
        self.codigo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 0))
        self._textos_codigo = {}
        for nombre in ("VHDL (MAX II)", "C (XC8)", "Ensamblador (pic-as)", "Arduino"):
            self._textos_codigo[nombre] = self._pestana_codigo(nombre)

        pie = ttk.Frame(cuerpo)
        pie.pack(fill=tk.X, pady=(8, 0))
        self.estado = ttk.Label(pie, text="", foreground=GRIS)
        self.estado.pack(side=tk.LEFT)
        if al_usar is not None:
            self.boton_usar = ttk.Button(pie, text="Usar en el kit", command=self._usar)
            self.boton_usar.pack(side=tk.RIGHT)
            if destino:
                ttk.Label(pie, text=f"Destino: {destino}", foreground=GRIS).pack(
                    side=tk.RIGHT, padx=8)
        self._cambiar_modo()

    # ---------------------------------------------------------- entradas
    def _fila(self, marco, fila, etiqueta, variable, ejemplo, ancho=16):
        ttk.Label(marco, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=2)
        caja = ttk.Entry(marco, textvariable=variable, width=ancho)
        caja.grid(row=fila, column=1, sticky="w", padx=6, pady=2)
        con_ejemplo(caja, variable, ejemplo)
        variable.trace_add("write", lambda *_x: self.recalcular())
        return caja

    def _entradas_divisor(self, f_entrada, f_salida):
        m = self.marco_divisor = ttk.Frame(self.entradas)
        self.f_entrada = tk.StringVar(value=reloj.formato(f_entrada, "Hz").replace(" ", ""))
        self._fila(m, 0, "Reloj de entrada (Hz):", self.f_entrada, "Ej. 50M")
        rapido = ttk.Combobox(m, state="readonly", width=30, values=list(RELOJES))
        rapido.set("Relojes comunes")
        rapido.grid(row=0, column=2, sticky="w")
        rapido.bind("<<ComboboxSelected>>",
                    lambda _e: self.f_entrada.set(RELOJES[rapido.get()]))
        self.pedir = tk.StringVar(value="frecuencia")
        pedir = ttk.Frame(m)
        pedir.grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(pedir, text="Frecuencia (Hz)", value="frecuencia", variable=self.pedir,
                        command=self.recalcular).pack(side=tk.LEFT)
        ttk.Radiobutton(pedir, text="Periodo (s)", value="periodo", variable=self.pedir,
                        command=self.recalcular).pack(side=tk.LEFT, padx=(8, 0))
        self.valor = tk.StringVar(value=f"{f_salida:g}")
        caja = ttk.Entry(m, textvariable=self.valor, width=16)
        caja.grid(row=1, column=1, sticky="w", padx=6, pady=2)
        con_ejemplo(caja, self.valor, "Ej. 1, 0.5, 3")
        self.valor.trace_add("write", lambda *_x: self.recalcular())
        self.ciclo = tk.StringVar(value="50")
        self._fila(m, 2, "Ciclo de trabajo (%):", self.ciclo, "Ej. 50")

    def _entradas_555(self):
        m = self.marco_555 = ttk.Frame(self.entradas)
        self.f_555 = tk.StringVar(value="1")
        self._fila(m, 0, "Frecuencia (Hz):", self.f_555, "Ej. 1")
        self.ciclo_555 = tk.StringVar()
        self._fila(m, 1, "Ciclo de trabajo (%):", self.ciclo_555, "Opcional, de 51 a 99")
        self.c_555 = tk.StringVar()
        self._fila(m, 2, "Capacitor (F):", self.c_555, "Opcional, ej. 10u")

    def _cambiar_modo(self):
        divisor = self.modo.get() == "divisor"
        self.marco_555.pack_forget()
        self.marco_divisor.pack_forget()
        (self.marco_divisor if divisor else self.marco_555).pack(anchor="w")
        if divisor:
            self.codigo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 0))
        else:
            self.codigo.pack_forget()
        if self.al_usar is not None:
            self.boton_usar.config(state="normal" if divisor else "disabled")
        self.recalcular()

    # ------------------------------------------------------------ calculo
    def recalcular(self):
        """Lee los cuadros, calcula, y redibuja datos, onda y codigo.

        Un dato a medio escribir no es un error que interrumpa: se dice en la
        linea de abajo y todo lo demas se queda como estaba."""
        if not hasattr(self, "estado"):      # aun se esta armando la ventana
            return
        try:
            if self.modo.get() == "divisor":
                filas = self._calcular_divisor()
            else:
                filas = self._calcular_555()
        except ValueError as e:
            self.estado.config(text=str(e), foreground=ROJO)
            return
        self.estado.config(text="", foreground=GRIS)
        self._mostrar_datos(filas)
        self._dibujar_onda()

    def _calcular_divisor(self):
        f_entrada = leer_numero(self.f_entrada.get())
        valor = leer_numero(self.valor.get())
        ciclo = leer_numero(self.ciclo.get() or "50")
        if self.pedir.get() == "frecuencia":
            self.calculo = reloj.calcular(f_entrada, f_salida=valor, ciclo=ciclo)
        else:
            self.calculo = reloj.calcular(f_entrada, periodo=valor, ciclo=ciclo)
        self.onda = (self.calculo.t_alto, self.calculo.t_bajo)
        self._llenar_codigo()
        return self.calculo.renglones()

    def _calcular_555(self):
        f = leer_numero(self.f_555.get())
        ciclo = leer_numero(self.ciclo_555.get()) if self.ciclo_555.get().strip() else None
        c = leer_numero(self.c_555.get()) if self.c_555.get().strip() else None
        r = reloj.astable_555_para(f, ciclo=ciclo, c=c)
        self.calculo = None
        self.onda = (r["t_alto"], r["t_bajo"])
        fila = [("R1", reloj.formato(r["r1"], "Ohm"), f"{r['r1']:g}"),
                ("R2", reloj.formato(r["r2"], "Ohm"), f"{r['r2']:g}"),
                ("C", reloj.formato(r["c"], "F"), f"{r['c']:g}"),
                ("Frecuencia real", reloj.formato(r["f"], "Hz"), f"{r['f']:g}"),
                ("Error", reloj.formato(r["error_pct"], "%"), f"{r['error_pct']:g}"),
                ("Periodo (T)", reloj.formato(r["periodo"], "s"), f"{r['periodo']:g}"),
                ("Tiempo en alto", reloj.formato(r["t_alto"], "s"), f"{r['t_alto']:g}"),
                ("Tiempo en bajo", reloj.formato(r["t_bajo"], "s"), f"{r['t_bajo']:g}"),
                ("Ciclo de trabajo", reloj.formato(r["ciclo"], "%"), f"{r['ciclo']:g}")]
        return fila

    def _usar(self):
        if self.calculo is not None:
            self.al_usar(self.calculo.f_real, self.calculo.f_entrada)
            self.estado.config(text=f"Frecuencia de {reloj.formato(self.calculo.f_real, 'Hz')} "
                                    "puesta en el kit.", foreground=GRIS)

    # ------------------------------------------------------------- datos
    def _mostrar_datos(self, filas):
        """Una fila por dato: etiqueta, valor y el boton de copiar ese valor."""
        for hijo in self.datos.winfo_children():
            hijo.destroy()
        cabeza = ttk.Frame(self.datos)
        cabeza.grid(row=0, column=0, columnspan=3, sticky="we", pady=(0, 4))
        ttk.Label(cabeza, text="Datos", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        todo = "\n".join(f"{etiqueta}\t{copia}" for etiqueta, _v, copia in filas)
        boton_copiar(cabeza, lambda t=todo: t).pack(side=tk.RIGHT)
        ttk.Label(cabeza, text="todo", foreground=GRIS).pack(side=tk.RIGHT, padx=4)
        for k, (etiqueta, legible, copia) in enumerate(filas, start=1):
            ttk.Label(self.datos, text=etiqueta).grid(row=k, column=0, sticky="w", pady=1)
            ttk.Label(self.datos, text=legible, font=("Consolas", 10)).grid(
                row=k, column=1, sticky="e", padx=(12, 8), pady=1)
            boton_copiar(self.datos, lambda c=copia: c).grid(row=k, column=2, pady=1)

    # -------------------------------------------------------------- onda
    def _dibujar_onda(self):
        """Tres periodos de la onda cuadrada, con las cotas de T, t alto y t bajo."""
        c = self.lienzo
        c.delete("all")
        if not getattr(self, "onda", None):
            return
        alto_t, bajo_t = self.onda
        ancho = max(c.winfo_width(), 300)
        x0, x1, y_alto, y_bajo = 30, ancho - 20, 30, 90
        periodo = alto_t + bajo_t
        escala = (x1 - x0) / (3 * periodo)
        puntos = [x0, y_bajo]
        x = x0
        for _ in range(3):
            puntos += [x, y_alto, x + alto_t * escala, y_alto, x + alto_t * escala, y_bajo]
            x += periodo * escala
            puntos += [x, y_bajo]
        c.create_line(*puntos, width=2, fill="#222")
        c.create_text(x0 - 8, y_alto, text="1", fill=GRIS, font=("Segoe UI", 8))
        c.create_text(x0 - 8, y_bajo, text="0", fill=GRIS, font=("Segoe UI", 8))
        # cotas del primer periodo
        xa = x0 + alto_t * escala
        xb = x0 + periodo * escala
        self._cota(x0, xa, y_alto - 14, "t alto " + reloj.formato(alto_t, "s"))
        self._cota(xa, xb, y_bajo + 14, "t bajo " + reloj.formato(bajo_t, "s"))
        self._cota(x0, xb, y_bajo + 38, "T = " + reloj.formato(periodo, "s")
                   + "   f = " + reloj.formato(1 / periodo, "Hz"))

    def _cota(self, xa, xb, y, texto):
        c = self.lienzo
        c.create_line(xa, y, xb, y, arrow=tk.BOTH, fill=GRIS)
        c.create_text((xa + xb) / 2, y - 8, text=texto, fill="#333", font=("Segoe UI", 8))

    # ------------------------------------------------------------ codigo
    def _pestana_codigo(self, nombre):
        marco = ttk.Frame(self.codigo, padding=4)
        self.codigo.add(marco, text=nombre)
        texto = tk.Text(marco, wrap="none", font=("Consolas", 9), height=14)
        barra = ttk.Scrollbar(marco, orient="vertical", command=texto.yview)
        texto.configure(yscrollcommand=barra.set)
        boton_copiar(marco, lambda: texto.get("1.0", "end-1c")).pack(side=tk.TOP, anchor="e")
        barra.pack(side=tk.RIGHT, fill=tk.Y)
        texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return texto

    def _llenar_codigo(self):
        """El calculo de arriba ya escrito para cada hardware. Lo que no aplica
        (una frecuencia que un PIC no alcanza a contar) lo dice en su pestana."""
        k = self.calculo
        trozos = {}
        try:
            trozos["VHDL (MAX II)"] = reloj.vhdl_divisor(k.f_entrada, k.f_real)
        except ValueError as e:
            trozos["VHDL (MAX II)"] = f"-- {e}"
        try:
            c = reloj.c_pic18_retardo(k.f_entrada, k.f_real)
            trozos["C (XC8)"] = _trozos(c, "//", [("definiciones", "arriba del archivo"),
                                                  ("configurar", "en configurar()"),
                                                  ("esperar_medio_periodo", "en el ciclo")])
        except ValueError as e:
            trozos["C (XC8)"] = f"// {e}"
        try:
            trozos["Ensamblador (pic-as)"] = reloj.asm_pic18_retardo(k.f_entrada, k.t_alto)
        except ValueError as e:
            trozos["Ensamblador (pic-as)"] = f"; {e}"
        try:
            a = reloj.arduino_retardo(k.f_real)
            trozos["Arduino"] = _trozos(a, "//", [("variables", "arriba del sketch"),
                                                 ("setup", "en setup()"),
                                                 ("en_loop", "en loop()")])
        except ValueError as e:
            trozos["Arduino"] = f"// {e}"
        for nombre, texto in self._textos_codigo.items():
            texto.config(state="normal")
            texto.delete("1.0", tk.END)
            texto.insert("1.0", trozos[nombre])
