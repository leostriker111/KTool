"""Frecuencias y retardos por hardware: divisores de reloj, el 555 y las esperas
de PIC y Arduino.

Lo usan la ventana "Calculadora de frecuencia", el generador de maquinas de
estados (contadores que avanzan a 1 Hz) y el documento HTML. Todo es calculo
puro: aqui no se abre ninguna ventana ni se escribe ningun archivo.

La idea de fondo es una sola: una onda cuadrada de frecuencia f dura T = 1/f, y
con ciclo de trabajo de 50 % pasa T/2 en alto y T/2 en bajo. Un reloj de
entrada de frecuencia F da un ciclo cada 1/F, asi que medio periodo son
N = F / (2 f) ciclos. Con N se arma todo lo demas:

    MAX II (VHDL)   un contador de 0 a N - 1 que al llegar al final invierte
                    la salida (tarjeta EPM240: F = 50 MHz)
    PIC18 (C/ASM)   __delay_ms, el Timer0 o lazos anidados que gastan N ciclos
                    de instruccion (un ciclo de instruccion = Fosc/4)
    Arduino         delay() o millis() sin bloquear

Unidades en texto: "us" para microsegundos (sin el simbolo micro, para no
romper consolas) y miles separados con un espacio normal: "25 000 000".
"""

from __future__ import annotations

import math
import re
import zlib

from .. import __version__
from .modelo import RESERVADAS


# ================================================================ formato

# Prefijos SI que se usan al mostrar tiempos, frecuencias y componentes.
PREFIJOS = [
    (1e9, "G"), (1e6, "M"), (1e3, "k"), (1.0, ""),
    (1e-3, "m"), (1e-6, "u"), (1e-9, "n"), (1e-12, "p"),
]

# Unidades que llevan prefijo (500 ms, 4.7 kOhm). Las demas (ciclos, bits, %)
# se escriben como numero con los miles separados.
UNIDADES_SI = ("s", "Hz", "F", "Ohm", "V", "A")


def _decimal(valor, cifras):
    """Un numero en notacion fija (nunca 4e-06) con `cifras` cifras significativas.

    Existe porque el formato '%g' de Python cambia a notacion cientifica con
    numeros chicos, y eso no se puede pegar en todas las calculadoras.
    """
    if valor == 0:
        return "0"
    exponente = math.floor(math.log10(abs(valor)))
    decimales = max(0, cifras - 1 - exponente)
    texto = f"{valor:.{decimales}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto


def _miles(valor):
    """Entero o decimal con los miles separados por espacio: 25 000 000, 8 333 333.333."""
    negativo = valor < 0
    valor = abs(valor)
    if float(valor).is_integer():
        texto = f"{int(valor):,}".replace(",", " ")
    elif valor >= 1:
        entero = int(valor)
        resto = f"{valor - entero:.3f}"
        if resto.startswith("1"):          # 0.9996 redondea a 1.000
            entero, resto = entero + 1, "0.000"
        decimales = resto[2:].rstrip("0")
        texto = f"{entero:,}".replace(",", " ") + (f".{decimales}" if decimales else "")
    else:
        texto = _decimal(valor, 3)
    return ("-" if negativo and texto != "0" else "") + texto


def formato(valor, unidad=""):
    """Un valor legible con su unidad, para la ventana y los comentarios.

    Con unidades SI escoge el prefijo y deja hasta 6 cifras significativas:
    formato(0.0005, "s") -> "500 us", formato(50e6, "Hz") -> "50 MHz".
    Con cualquier otra unidad separa los miles: formato(25000000, "ciclos")
    -> "25 000 000 ciclos"; formato(25000000, "") -> "25 000 000".
    """
    if unidad not in UNIDADES_SI:
        texto = _miles(valor)
        return f"{texto} {unidad}" if unidad else texto
    if valor == 0:
        return f"0 {unidad}"
    magnitud = abs(valor)
    if unidad == "Hz" and magnitud < 1:
        # "333.333 mHz" se lee como megahertz: abajo de 1 Hz, decimal sin prefijo
        return f"{_decimal(float(f'{valor:.6g}'), 6)} Hz"
    indice = len(PREFIJOS) - 1
    for k, (factor, _) in enumerate(PREFIJOS):
        if magnitud >= factor:
            indice = k
            break
    mantisa = float(f"{valor / PREFIJOS[indice][0]:.6g}")
    if abs(mantisa) >= 1000 and indice > 0:   # 999.9999 ms redondea a 1000 ms: mejor 1 s
        indice -= 1
        mantisa = float(f"{valor / PREFIJOS[indice][0]:.6g}")
    return f"{_decimal(mantisa, 6)} {PREFIJOS[indice][1]}{unidad}"


def _plano(valor):
    """El valor para copiar al portapapeles: sin unidades, sin espacios, sin exponente."""
    if isinstance(valor, int) or float(valor).is_integer():
        return str(int(valor))
    return _decimal(valor, 12)


def _error_pct(real, pedido):
    return (real - pedido) / pedido * 100.0


# ================================================================ divisor

class Calculo:
    """El resultado de dividir un reloj: lo que se pidio, lo que sale y las cuentas.

    f_entrada             frecuencia del reloj de entrada (Hz)
    f_pedida              frecuencia que se pidio (Hz)
    f_real                la que sale con cuentas enteras (Hz)
    error_pct             (f_real - f_pedida) / f_pedida x 100
    periodo               T real (s)
    t_alto, t_bajo        tiempo en alto y en bajo (s)
    ciclo_pct             ciclo de trabajo real (%)
    ciclo_pedido          ciclo de trabajo que se pidio (%)
    cuenta_alto           ciclos de f_entrada que la salida pasa en alto
    cuenta_bajo           ciclos de f_entrada que pasa en bajo
    cuenta_periodo        cuenta_alto + cuenta_bajo
    cuenta_medio_periodo  con ciclo de 50 %, los ciclos que dura T/2 (la N del
                          divisor). Con otro ciclo no hay medio periodo: vale
                          cuenta_alto, y lo correcto es leer cuenta_alto y
                          cuenta_bajo.
    cuenta_ideal          la cuenta sin redondear (N con decimales)
    bits_contador         bits del contador que va de 0 a la cuenta - 1
    """

    def __init__(self, f_entrada, f_pedida, ciclo_pedido, cuenta_alto, cuenta_bajo,
                 cuenta_ideal):
        self.f_entrada = f_entrada
        self.f_pedida = f_pedida
        self.ciclo_pedido = ciclo_pedido
        self.cuenta_alto = cuenta_alto
        self.cuenta_bajo = cuenta_bajo
        self.cuenta_periodo = cuenta_alto + cuenta_bajo
        self.cuenta_ideal = cuenta_ideal
        self.cuenta_medio_periodo = cuenta_alto
        self.periodo = self.cuenta_periodo / f_entrada
        self.f_real = f_entrada / self.cuenta_periodo
        self.t_alto = cuenta_alto / f_entrada
        self.t_bajo = cuenta_bajo / f_entrada
        self.ciclo_pct = cuenta_alto / self.cuenta_periodo * 100.0
        self.error_pct = _error_pct(self.f_real, f_pedida)
        if self.es_simetrico():
            mayor = cuenta_alto - 1          # el contador va de 0 a N - 1 y se reinicia
        else:
            mayor = self.cuenta_periodo - 1  # un solo contador recorre todo el periodo
        self.bits_contador = max(1, mayor.bit_length())

    def es_simetrico(self):
        """True si se pidio 50 %: un contador de T/2 que invierte la salida."""
        return self.ciclo_pedido == 50

    def renglones(self):
        """Los datos para la ventana: (etiqueta, valor con unidades, valor para copiar).

        El valor para copiar va sin unidades ni espacios, listo para pegar en
        una calculadora, en el VHDL o en una hoja de calculo.
        """
        filas = [
            ("Frecuencia de entrada", formato(self.f_entrada, "Hz"), _plano(self.f_entrada)),
            ("Frecuencia pedida", formato(self.f_pedida, "Hz"), _plano(self.f_pedida)),
            ("Frecuencia real", formato(self.f_real, "Hz"), _plano(self.f_real)),
            ("Error", formato(self.error_pct, "%"), _plano(self.error_pct)),
            ("Periodo (T)", formato(self.periodo, "s"), _plano(self.periodo)),
        ]
        if self.es_simetrico():
            n = self.cuenta_medio_periodo
            filas += [
                ("Medio periodo (T/2)", formato(self.t_alto, "s"), _plano(self.t_alto)),
                ("Ciclo de trabajo", formato(self.ciclo_pct, "%"), _plano(self.ciclo_pct)),
                ("Cuenta del divisor", formato(n, "ciclos"), _plano(n)),
                ("Rango del contador", f"0 a {formato(n - 1)}", _plano(n - 1)),
            ]
        else:
            filas += [
                ("Tiempo en alto", formato(self.t_alto, "s"), _plano(self.t_alto)),
                ("Tiempo en bajo", formato(self.t_bajo, "s"), _plano(self.t_bajo)),
                ("Ciclo de trabajo", formato(self.ciclo_pct, "%"), _plano(self.ciclo_pct)),
                ("Cuenta en alto", formato(self.cuenta_alto, "ciclos"), _plano(self.cuenta_alto)),
                ("Cuenta en bajo", formato(self.cuenta_bajo, "ciclos"), _plano(self.cuenta_bajo)),
                ("Rango del contador", f"0 a {formato(self.cuenta_periodo - 1)}",
                 _plano(self.cuenta_periodo - 1)),
            ]
        filas.append(("Bits del contador", formato(self.bits_contador, "bits"),
                      _plano(self.bits_contador)))
        return filas

    def __repr__(self):
        return (f"Calculo({formato(self.f_entrada, 'Hz')} -> {formato(self.f_real, 'Hz')}, "
                f"alto {self.cuenta_alto}, bajo {self.cuenta_bajo})")


def _positivo(valor, que):
    if valor is None or not isinstance(valor, (int, float)) or not valor > 0 \
            or math.isinf(valor):
        raise ValueError(f"{que} debe ser un numero mayor que cero (se dio {valor!r})")


def calcular(f_entrada, f_salida=None, periodo=None, ciclo=50):
    """Divide f_entrada para sacar f_salida (o el periodo en segundos).

    Se da f_salida o periodo, no los dos. Con ciclo = 50 la cuenta es
    N = f_entrada / (2 f_salida) redondeada: un contador de N ciclos invierte la
    salida. Con otro ciclo la cuenta es el periodo completo, P = f_entrada /
    f_salida, repartido en alto y bajo. Devuelve un Calculo; lanza ValueError
    si la frecuencia no cabe (mas de f_entrada/2) o el ciclo no se puede.
    """
    _positivo(f_entrada, "La frecuencia de entrada")
    if (f_salida is None) == (periodo is None):
        raise ValueError("Se da la frecuencia de salida o el periodo, uno de los dos.")
    if periodo is not None:
        _positivo(periodo, "El periodo")
        f_pedida = 1.0 / periodo
    else:
        _positivo(f_salida, "La frecuencia de salida")
        f_pedida = f_salida
    if not isinstance(ciclo, (int, float)) or not 0 < ciclo < 100:
        raise ValueError(f"El ciclo de trabajo va entre 0 y 100 % sin incluirlos (se dio {ciclo!r}).")
    if f_pedida > f_entrada / 2:
        raise ValueError(
            f"La frecuencia pedida ({formato(f_pedida, 'Hz')}) no cabe: con un reloj de "
            f"{formato(f_entrada, 'Hz')} lo mas rapido que sale es f/2 = "
            f"{formato(f_entrada / 2, 'Hz')} (un ciclo en alto y uno en bajo).")

    if ciclo == 50:
        ideal = f_entrada / (2 * f_pedida)
        n = max(1, int(round(ideal)))
        return Calculo(f_entrada, f_pedida, 50, n, n, ideal)

    ideal = f_entrada / f_pedida
    total = max(2, int(round(ideal)))
    alto = int(round(total * ciclo / 100.0))
    if alto < 1 or alto > total - 1:
        raise ValueError(
            f"Con {formato(total)} ciclos por periodo el ciclo de trabajo va de "
            f"{_decimal(100.0 / total, 4)} % a {_decimal(100.0 - 100.0 / total, 4)} %; "
            f"{_decimal(ciclo, 4)} % no se puede.")
    return Calculo(f_entrada, f_pedida, ciclo, alto, total - alto, ideal)


# ================================================================ 555

def astable_555(r1, r2, c):
    """El 555 astable basico (R1 de VCC a la descarga, R2 de la descarga al umbral).

    Formulas de la hoja de datos: t_alto = 0.693 (R1 + R2) C, t_bajo = 0.693 R2 C.
    Devuelve {"f", "periodo", "t_alto", "t_bajo", "ciclo", "r1", "r2", "c"} en
    Hz, s y %. El ciclo siempre pasa de 50 % porque t_alto incluye a R1.
    """
    _positivo(r1, "R1")
    _positivo(r2, "R2")
    _positivo(c, "C")
    t_alto = 0.693 * (r1 + r2) * c
    t_bajo = 0.693 * r2 * c
    periodo = t_alto + t_bajo
    return {"f": 1.0 / periodo, "periodo": periodo, "t_alto": t_alto, "t_bajo": t_bajo,
            "ciclo": t_alto / periodo * 100.0, "r1": r1, "r2": r2, "c": c}


# Serie E24 (resistencias de 5 %) y serie E6 (capacitores comunes), una decada.
SERIE_E24 = (1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
             3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1)
SERIE_E6 = (1.0, 1.5, 2.2, 3.3, 4.7, 6.8)

# Rango sensato de resistencias para el 555: con menos de 1 kOhm la descarga
# (pata 7) se calienta; con mas de 1 MOhm las corrientes de fuga pesan.
R_MINIMA = 1e3
R_MAXIMA = 1e6


def _e24_vecinos(valor):
    """Los dos valores E24 que encierran a `valor` (el de abajo y el de arriba)."""
    decada = 10.0 ** math.floor(math.log10(valor))
    lista = [round(m * d, 12) for d in (decada / 10, decada, decada * 10) for m in SERIE_E24]
    abajo = max(v for v in lista if v <= valor * (1 + 1e-9))
    arriba = min(v for v in lista if v >= valor * (1 - 1e-9))
    return sorted({abajo, arriba})


def _capacitores():
    """Capacitores E6 de 100 pF a 1000 uF, del mas chico al mas grande."""
    valores = []
    for exponente in range(-10, -2):
        for m in SERIE_E6:
            valores.append(round(m * 10.0 ** exponente, 16))
    return valores + [1e-3]


def astable_555_para(f, ciclo=None, c=None):
    """Propone R1, R2 (E24) y C para que el 555 astable de f Hz.

    ciclo  ciclo de trabajo deseado en %, mayor que 50 y menor que 100. Si no
           se da, R1 queda en 1 kOhm (lo minimo sensato) y el ciclo sale lo mas
           cerca de 50 % que se pueda.
    c      capacitor fijo (F). Si no se da, se prueban los E6 de 100 pF a 1000 uF.
    Devuelve el dict de astable_555 con los valores propuestos, mas
    "f_pedida", "ciclo_pedido" (None si no se dio) y "error_pct" de la frecuencia.
    """
    _positivo(f, "La frecuencia")
    if ciclo is not None:
        if not isinstance(ciclo, (int, float)) or not 50 < ciclo < 100:
            raise ValueError(
                "En el 555 astable basico t_alto = 0.693 (R1 + R2) C siempre es mayor "
                "que t_bajo = 0.693 R2 C: el ciclo de trabajo va de 50 % a 100 % sin "
                "incluirlos. Para 50 % o menos hace falta un diodo en paralelo con R2.")
    if c is not None:
        _positivo(c, "C")
        capacitores = [c]
    else:
        capacitores = _capacitores()

    # Primero se busca con R2 en el rango comodo (10 kOhm a 470 kOhm: corrientes
    # chicas y capacitores de tamano normal); si ahi no hay nada, en todo el rango.
    mejor = _buscar_555(f, ciclo, capacitores, 10e3, 470e3)
    if mejor is None:
        mejor = _buscar_555(f, ciclo, capacitores, R_MINIMA, R_MAXIMA)
    if mejor is None:
        raise ValueError(
            f"No hay valores razonables para {formato(f, 'Hz')}: con R1 y R2 entre "
            f"1 kOhm y 1 MOhm{' y el C dado' if c is not None else ' y C de 100 pF a 1000 uF'} "
            "la frecuencia no se alcanza.")
    mejor["f_pedida"] = f
    mejor["ciclo_pedido"] = ciclo
    mejor["error_pct"] = _error_pct(mejor["f"], f)
    return mejor


def _buscar_555(f, ciclo, capacitores, r2_minima, r2_maxima):
    """La combinacion E24/E6 con menos error (frecuencia mas ciclo) dentro del rango de R2."""
    periodo = 1.0 / f
    mejor = None
    mejor_clave = None
    for cap in capacitores:
        if ciclo is None:
            opciones_r1 = [R_MINIMA]
            r2_ideal = (periodo / (0.693 * cap) - R_MINIMA) / 2
        else:
            t_alto = periodo * ciclo / 100.0
            t_bajo = periodo - t_alto
            r2_ideal = t_bajo / (0.693 * cap)
            r1_ideal = t_alto / (0.693 * cap) - r2_ideal
            if r1_ideal <= 0:
                continue
            opciones_r1 = _e24_vecinos(r1_ideal)
        if r2_ideal <= 0:
            continue
        for r1 in opciones_r1:
            for r2 in _e24_vecinos(r2_ideal):
                if not (R_MINIMA <= r1 <= R_MAXIMA and r2_minima <= r2 <= r2_maxima):
                    continue
                datos = astable_555(r1, r2, cap)
                error = abs(_error_pct(datos["f"], f))
                desvio_ciclo = abs(datos["ciclo"] - ciclo) if ciclo is not None else 0.0
                # a igual error gana el capacitor mas chico (el primero que se prueba)
                clave = error + desvio_ciclo
                if mejor_clave is None or clave < mejor_clave - 1e-9:
                    mejor, mejor_clave = datos, clave
    return mejor


# ================================================================ PIC18F45K50

# IRCF<2:0> de OSCCON en el PIC18F45K50 (hoja de datos PIC18(L)F2X/45K50,
# registro OSCCON). 000 da 31 kHz: del LFINTOSC o HFINTOSC/512 segun OSCCON2.INTSRC.
IRCF_PIC18F45K50 = {
    16000000: 0b111, 8000000: 0b110, 4000000: 0b101, 2000000: 0b100,
    1000000: 0b011, 500000: 0b010, 250000: 0b001, 31000: 0b000,
}


def osccon_pic18f45k50(f_hz):
    """El valor de OSCCON para correr el PIC18F45K50 con su oscilador interno.

    Devuelve (valor, comentario). SCS = 10 escoge el bloque interno sin importar
    lo que diga FOSC en los bits de configuracion. Acepta 31 000 o 31 250 Hz
    para IRCF = 000. ValueError si f_hz no es una de las frecuencias de IRCF.
    """
    clave = 31000 if f_hz in (31000, 31250) else f_hz
    if clave not in IRCF_PIC18F45K50:
        validas = ", ".join(formato(v, "Hz") for v in IRCF_PIC18F45K50)
        raise ValueError(
            f"El oscilador interno del PIC18F45K50 no da {formato(f_hz, 'Hz')}; "
            f"IRCF solo da {validas}.")
    ircf = IRCF_PIC18F45K50[clave]
    valor = (ircf << 4) | 0b10
    if clave == 31000:
        fuente = "31 kHz del LFINTOSC si OSCCON2.INTSRC = 0, el valor de arranque"
    else:
        fuente = f"{formato(clave, 'Hz')} del HFINTOSC"
    comentario = (f"IRCF = {ircf:03b} ({fuente}), SCS = 10 (oscilador interno); "
                  f"ciclo de instruccion = Fosc/4 = {formato(clave / 4, 'Hz')}")
    return valor, comentario


# Lo mas que acepta _delay() de XC8 en un PIC18 (medido con XC8 v3.10:
# "delay exceeds maximum limit of 50463240 cycles").
LIMITE_DELAY_XC8 = 50463240

PRESCALAS_TMR0 = (1, 2, 4, 8, 16, 32, 64, 128, 256)


def _plan_timer0(ciclos):
    """Preescala, cuentas y vueltas del Timer0 (16 bits) para gastar `ciclos`.

    Escoge el menor numero de vueltas que alcanza y, en esas vueltas, la
    preescala con menos error (a igual error, la mas chica: mas resolucion).
    Devuelve (prescala, cuentas, vueltas).
    """
    if ciclos < 100:
        raise ValueError(
            f"Medio periodo de {formato(ciclos)} ciclos de instruccion es muy poco para el "
            "Timer0: lo que tarda en recargarse pesa mas que la cuenta. Usa __delay_us.")
    vueltas = max(1, math.ceil(ciclos / (256 * 65536)))
    mejor = None
    for prescala in PRESCALAS_TMR0:
        cuentas = int(round(ciclos / (vueltas * prescala)))
        if not 1 <= cuentas <= 65536:
            continue
        error = abs(vueltas * prescala * cuentas - ciclos)
        if mejor is None or error < mejor[0]:
            mejor = (error, prescala, cuentas)
    return mejor[1], mejor[2], vueltas


def _t0con(prescala):
    """T0CON para el Timer0 de 16 bits con reloj Fosc/4 y la preescala dada."""
    if prescala == 1:
        return 0b10001000   # TMR0ON, 16 bits, Fosc/4, PSA = 1 (sin preescala)
    return 0b10000000 | (int(math.log2(prescala)) - 1)


def _texto_t0con(prescala):
    if prescala == 1:
        return "TMR0ON = 1, T08BIT = 0 (16 bits), T0CS = 0 (Fosc/4), PSA = 1 (sin preescala)"
    return (f"TMR0ON = 1, T08BIT = 0 (16 bits), T0CS = 0 (Fosc/4), PSA = 0, "
            f"T0PS = {int(math.log2(prescala)) - 1:03b} (1:{prescala})")


def c_pic18_retardo(fosc, f_salida, metodo="delay"):
    """Trozos de C (XC8, PIC18) para esperar medio periodo de f_salida.

    metodo "delay"   __delay_ms/__delay_us; necesitan _XTAL_FREQ, que se define
                     aqui con el mismo formato que micros.py ("16000000UL").
    metodo "timer0"  Timer0 de 16 bits con preescala y precarga calculadas; la
                     espera revisa TMR0IF (sin interrupciones).
    Devuelve {"definiciones", "configurar", "esperar_medio_periodo", "f_real",
    "error_pct"}: los tres primeros son texto para pegar (definiciones a nivel
    de archivo, los otros dos con sangria de 4 espacios dentro de una funcion).
    """
    _positivo(fosc, "Fosc")
    _positivo(f_salida, "La frecuencia de salida")
    fcy = fosc / 4.0
    medio = 1.0 / (2 * f_salida)
    if metodo == "delay":
        micros_totales = int(round(medio * 1e6))
        if micros_totales < 1:
            raise ValueError("El medio periodo dura menos de 1 us: __delay_us no llega.")
        ms, us = divmod(micros_totales, 1000)
        # los macros de XC8 truncan: __delay_ms(x) = _delay((unsigned long)(x * Fosc/4000))
        lineas = []
        ciclos_reales = 0
        if ms and ms * fosc / 4000.0 > LIMITE_DELAY_XC8:
            # _delay() no acepta tantos ciclos de una vez: se repite 1 s
            segundos, ms = divmod(ms, 1000)
            lineas.append(f"    for (uint16_t s__ = 0; s__ < {segundos}u; s__++) {{")
            lineas.append("        __delay_ms(1000);   // XC8 no acepta mas de 50 463 240 ciclos por llamada")
            lineas.append("    }")
            ciclos_reales += segundos * int(1000 * fosc / 4000.0)
        if ms:
            ciclos = int(ms * fosc / 4000.0)
            lineas.append(f"    __delay_ms({ms});")
            ciclos_reales += ciclos
        if us:
            ciclos = int(us * fosc / 4000000.0)
            if ciclos > 0:
                lineas.append(f"    __delay_us({us});")
                ciclos_reales += ciclos
        if ciclos_reales == 0:
            raise ValueError(
                f"A Fosc = {formato(fosc, 'Hz')} un ciclo de instruccion dura "
                f"{formato(1 / fcy, 's')}: el medio periodo no alcanza ni un ciclo.")
        t_real = ciclos_reales / fcy
        f_real = 1.0 / (2 * t_real)
        error = _error_pct(f_real, f_salida)
        definiciones = (
            f"#define _XTAL_FREQ {int(round(fosc))}UL   // Fosc: lo usan __delay_ms y __delay_us")
        configurar = ("    // __delay_ms no necesita configurar nada: cuenta ciclos de instruccion "
                      "(Fosc/4)")
        lineas.insert(0, f"    // T/2 = {formato(medio, 's')} = {formato(ciclos_reales)} ciclos de "
                         f"{formato(1 / fcy, 's')} (f real {formato(f_real, 'Hz')}, error "
                         f"{formato(error, '%')}, sin contar el resto del ciclo)")
        return {"definiciones": definiciones, "configurar": configurar,
                "esperar_medio_periodo": "\n".join(lineas),
                "f_real": f_real, "error_pct": error}

    if metodo == "timer0":
        ciclos = medio * fcy
        prescala, cuentas, vueltas = _plan_timer0(ciclos)
        precarga = 65536 - cuentas
        if precarga == 65536:
            precarga = 0
        ciclos_reales = vueltas * prescala * cuentas
        t_real = ciclos_reales / fcy
        f_real = 1.0 / (2 * t_real)
        error = _error_pct(f_real, f_salida)
        definiciones = "\n".join([
            f"// Timer0: Fosc = {formato(fosc, 'Hz')}, cuenta a Fosc/4 = {formato(fcy, 'Hz')} "
            f"con preescala 1:{prescala} ({formato(prescala / fcy, 's')} por cuenta).",
            f"// T/2 = {formato(medio, 's')} = {formato(cuentas)} cuentas x {vueltas} "
            f"vuelta{'s' if vueltas > 1 else ''} (f real {formato(f_real, 'Hz')}, error "
            f"{formato(error, '%')}).",
            f"#define PRECARGA_TMR0 {precarga}u   // 65536 - {cuentas}",
            f"#define VUELTAS_TMR0 {vueltas}u",
        ])
        configurar = f"    T0CON = 0x{_t0con(prescala):02X};   // {_texto_t0con(prescala)}"
        tipo = "uint8_t" if vueltas <= 255 else "uint16_t"
        esperar = "\n".join([
            f"    for ({tipo} v__ = 0; v__ < VUELTAS_TMR0; v__++) {{",
            "        TMR0H = (uint8_t)(PRECARGA_TMR0 >> 8);    // primero la parte alta (queda en un buffer)",
            "        TMR0L = (uint8_t)(PRECARGA_TMR0 & 0xFFu); // al escribir la baja se cargan los 16 bits",
            "        INTCONbits.TMR0IF = 0;",
            "        while (!INTCONbits.TMR0IF) {",
            "            // espera el desborde de 0xFFFF a 0x0000",
            "        }",
            "    }",
        ])
        return {"definiciones": definiciones, "configurar": configurar,
                "esperar_medio_periodo": esperar, "f_real": f_real, "error_pct": error}

    raise ValueError(f"Metodo desconocido {metodo!r}: usa 'delay' o 'timer0'.")


_ETIQUETA_ASM = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Cuantos ciclos gasta un bloque de lazos anidados segun cuantos niveles tenga
# (a es la cuenta del lazo interno, b la del de en medio, c la del externo).
FORMULAS_BLOQUE = {
    1: "3a + 1",
    2: "b*(3a + 4) + 1",
    3: "c*(b*(3a + 4) + 4) + 1",
}

# Mas bloques que esto ya no es una subrutina razonable: mejor el Timer0.
BLOQUES_MAXIMOS = 8


def ciclos_bloque_pic18(cuentas):
    """Ciclos de un bloque de lazos anidados, desde el primer movlw hasta el ultimo bra.

    cuentas = [a] o [a, b] o [a, b, c], del lazo interno al externo (1 a 255).
    Cuenta de un PIC18: movlw y movwf 1 ciclo; decfsz 1 (2 cuando salta); bra 2.
      lazo interno      movlw + movwf + (a - 1) x (decfsz + bra) + decfsz que salta
                        = 2 + 3(a - 1) + 2 = 3a + 1
      cada nivel extra  c x (lo de adentro) + 2 + 3(c - 1) + 2 = c x (adentro + 3) + 1
    """
    total = 3 * cuentas[0] + 1
    for c in cuentas[1:]:
        total = c * (total + 3) + 1
    return total


def ciclos_lazos_pic18(bloques, nops=0):
    """Ciclos que tarda `call retardo` de asm_pic18_retardo (metodo "subrutina").

    bloques = lista de cuentas de cada bloque en serie, ej. [[230, 95, 91]].
    Total = suma de los bloques + nops + 4 (call y return, 2 ciclos cada uno).
    Existe aparte para que las pruebas revisen la formula contra un simulador.
    """
    return sum(ciclos_bloque_pic18(cuentas) for cuentas in bloques) + nops + 4


def _mejor_bloque(ciclos):
    """El bloque de 1, 2 o 3 lazos que mas se acerca a `ciclos` sin pasarse."""
    if ciclos <= ciclos_bloque_pic18([255]):
        return [(ciclos - 1) // 3]
    if ciclos <= ciclos_bloque_pic18([255, 255]):
        mejor = None
        for b in range(1, 256):
            a = ((ciclos - 1) // b - 4) // 3
            if not 1 <= a <= 255:
                continue
            sobra = ciclos - ciclos_bloque_pic18([a, b])
            if mejor is None or sobra < mejor[0]:
                mejor = (sobra, [a, b])
        return mejor[1]
    if ciclos <= ciclos_bloque_pic18([255, 255, 255]):
        mejor = None
        for c in range(1, 256):
            # c*(b*(3a + 4) + 4) + 1 <= ciclos  ->  b*(3a + 4) <= (ciclos - 1)//c - 4
            adentro = (ciclos - 1) // c - 4
            for b in range(1, 256):
                a = (adentro // b - 4) // 3
                if not 1 <= a <= 255:
                    continue
                sobra = ciclos - ciclos_bloque_pic18([a, b, c])
                if sobra >= 0 and (mejor is None or sobra < mejor[0]):
                    mejor = (sobra, [a, b, c])
                    if sobra == 0:
                        return mejor[1]
        return mejor[1]
    return [255, 255, 255]


def _plan_lazos(ciclos):
    """Los bloques de lazos (en serie) y los nops que suman exactamente `ciclos`.

    `ciclos` incluye el call y el return. Casi siempre sale un solo bloque; si
    el mejor bloque deja un sobrante de 4 ciclos o mas, otro bloque mas chico
    se lo come, y los ultimos 0 a 3 ciclos son nops. Devuelve (bloques, nops).
    """
    if ciclos < 4 + ciclos_bloque_pic18([1]):
        raise ValueError(
            f"{formato(ciclos)} ciclos es menos de lo que tarda la subrutina mas corta "
            f"({4 + ciclos_bloque_pic18([1])} ciclos con call y return).")
    bloques = []
    falta = ciclos - 4
    while falta >= ciclos_bloque_pic18([1]):
        if len(bloques) == BLOQUES_MAXIMOS:
            raise ValueError(
                f"{formato(ciclos)} ciclos piden mas de {BLOQUES_MAXIMOS} bloques de lazos: "
                "usa el metodo 'timer0' o llama la subrutina varias veces.")
        cuentas = _mejor_bloque(falta)
        bloques.append(cuentas)
        falta -= ciclos_bloque_pic18(cuentas)
    return bloques, falta


def _sustitucion(cuentas):
    """La formula del bloque con los numeros puestos, para el comentario."""
    if len(cuentas) == 1:
        return f"3*{cuentas[0]} + 1"
    if len(cuentas) == 2:
        return f"{cuentas[1]}*(3*{cuentas[0]} + 4) + 1"
    return f"{cuentas[2]}*({cuentas[1]}*(3*{cuentas[0]} + 4) + 4) + 1"


def asm_pic18_retardo(fosc, segundos, metodo="subrutina", etiqueta="retardo"):
    """Subrutina de retardo para pic-as (PIC18) que tarda `segundos` con `call`.

    metodo "subrutina"  lazos anidados (1 a 3 niveles) con decfsz/bra; las
                        cuentas se calculan para el total exacto de ciclos y el
                        comentario trae la formula, el total y el error.
    metodo "timer0"     configura T0CON, carga la precarga y espera TMR0IF.
    Devuelve el texto para pegar en un .S (con preprocesador: extension .S
    mayuscula) que ya tenga PROCESSOR y #include <xc.inc>: un PSECT udata_acs
    con las variables (access bank) y un PSECT code con la subrutina. Usa W y
    no toca otros registros.
    """
    _positivo(fosc, "Fosc")
    _positivo(segundos, "El tiempo")
    if not _ETIQUETA_ASM.match(etiqueta):
        raise ValueError(f"La etiqueta {etiqueta!r} no sirve en ensamblador: letras, numeros y '_'.")
    fcy = fosc / 4.0
    ciclos = int(round(segundos * fcy))
    encabezado = [
        f"; {etiqueta}: espera {formato(segundos, 's')} con Fosc = {formato(fosc, 'Hz')} "
        f"(Fcy = Fosc/4 = {formato(fcy, 'Hz')}, {formato(1 / fcy, 's')} por ciclo).",
        f"; Generado por ktool {__version__}. Se usa con: call {etiqueta}",
    ]

    if metodo == "subrutina":
        bloques, nops = _plan_lazos(ciclos)
        total = ciclos_lazos_pic18(bloques, nops)
        t_real = total / fcy
        error = _error_pct(t_real, segundos)
        niveles = max(len(cuentas) for cuentas in bloques)
        lineas = list(encabezado)
        lineas.append("; Lazos anidados (a = lazo interno, b = de en medio, c = externo).")
        lineas.append("; Ciclos: movlw, movwf y nop 1; decfsz 1 (2 cuando salta); bra, call y return 2.")
        for j, cuentas in enumerate(bloques):
            valores = ", ".join(f"{letra} = {v}" for letra, v in zip("abc", cuentas))
            lineas.append(
                f"; Bloque {j + 1}: {FORMULAS_BLOQUE[len(cuentas)]} con {valores}"
                f" = {_sustitucion(cuentas)} = {formato(ciclos_bloque_pic18(cuentas))} ciclos")
        lineas.append(
            "; Total = bloques" + (f" + {nops} nop" if nops else "") + " + 4 (call y return) = "
            f"{formato(total)} ciclos = {formato(t_real, 's')} (error {formato(error, '%')}).")
        lineas.append(f"; Usa W y {', '.join(f'{etiqueta}_c{k + 1}' for k in range(niveles))} "
                      "(access bank).")
        lineas += ["", "PSECT udata_acs"]
        for k in range(niveles):
            lineas.append(f"{etiqueta}_c{k + 1}: DS 1")
        lineas += ["", "PSECT code", f"{etiqueta}:"]
        for j, cuentas in enumerate(bloques):
            # bloque 1: retardo_l1, retardo_l2...; bloque 2: retardo_l1b, retardo_l2b...
            sufijo = "" if j == 0 else "bcdefghij"[j - 1]
            if len(bloques) > 1:
                lineas.append(f"    ; bloque {j + 1}")
            for nivel in range(len(cuentas), 0, -1):
                letra = "abc"[nivel - 1]
                lineas.append(f"    movlw   {cuentas[nivel - 1]:<15d} ; {letra}")
                lineas.append(f"    movwf   {etiqueta}_c{nivel}, a")
                lineas.append(f"{etiqueta}_l{nivel}{sufijo}:")
            for nivel in range(1, len(cuentas) + 1):
                lineas.append(f"    decfsz  {etiqueta}_c{nivel}, f, a")
                lineas.append(f"    bra     {etiqueta}_l{nivel}{sufijo}")
        for _ in range(nops):
            lineas.append("    nop                     ; ajuste fino: 1 ciclo")
        lineas.append("    return")
        return "\n".join(lineas) + "\n"

    if metodo == "timer0":
        prescala, cuentas, vueltas = _plan_timer0(ciclos)
        if vueltas > 255:
            raise ValueError(
                f"{formato(segundos, 's')} pide {vueltas} vueltas del Timer0 y el contador "
                "de vueltas es de 8 bits (255): divide el tiempo en varias llamadas.")
        precarga = 65536 - cuentas
        if precarga == 65536:
            precarga = 0
        total = vueltas * prescala * cuentas
        t_real = total / fcy
        error = _error_pct(t_real, segundos)
        lineas = encabezado + [
            f"; Timer0 de 16 bits, preescala 1:{prescala}: cada cuenta dura "
            f"{formato(prescala / fcy, 's')}.",
            f"; {formato(cuentas)} cuentas x {vueltas} vuelta{'s' if vueltas > 1 else ''} "
            f"x {prescala} = {formato(total)} ciclos = {formato(t_real, 's')} "
            f"(error {formato(error, '%')}, mas unos ciclos de recarga).",
            f"; Precarga = 65536 - {cuentas} = {precarga} (0x{precarga:04X}).",
            f"; Usa W y {etiqueta}_v (access bank). Deja el Timer0 encendido.",
            "",
            "PSECT udata_acs",
            f"{etiqueta}_v: DS 1",
            "",
            "PSECT code",
            f"{etiqueta}:",
            f"    movlw   0x{_t0con(prescala):02X}            ; T0CON: {_texto_t0con(prescala)}",
            "    movwf   T0CON, a",
            f"    movlw   {vueltas:<15d} ; vueltas del Timer0",
            f"    movwf   {etiqueta}_v, a",
            f"{etiqueta}_vuelta:",
            f"    movlw   high({precarga})",
            "    movwf   TMR0H, a        ; primero la parte alta: queda en un buffer",
            f"    movlw   low({precarga})",
            "    movwf   TMR0L, a        ; al escribir TMR0L se cargan los 16 bits",
            "    bcf     INTCON, INTCON_TMR0IF_POSN, a",
            f"{etiqueta}_espera:",
            "    btfss   INTCON, INTCON_TMR0IF_POSN, a   ; TMR0IF = 1 al desbordar",
            f"    bra     {etiqueta}_espera",
            f"    decfsz  {etiqueta}_v, f, a",
            f"    bra     {etiqueta}_vuelta",
            "    return",
        ]
        return "\n".join(lineas) + "\n"

    raise ValueError(f"Metodo desconocido {metodo!r}: usa 'subrutina' o 'timer0'.")


# ================================================================ Arduino

# Por debajo de esto el propio loop() (digitalWrite, la comparacion) tarda lo
# mismo que la espera y el resultado ya no es la frecuencia pedida.
MEDIO_PERIODO_MINIMO_ARDUINO = 20e-6


def arduino_retardo(f_salida, metodo="delay", accion=None):
    """Trozos de sketch para que algo pase cada medio periodo de f_salida.

    metodo "delay"   accion y luego delay() (+ delayMicroseconds() si T/2 no es
                     un numero entero de ms). Bloquea: el loop no hace nada mas.
    metodo "millis"  sin bloquear: compara millis() (o micros(), si T/2 no es
                     un numero entero de ms) contra la ultima vez.
    accion           renglones de C++ que se ejecutan cada medio periodo (sin
                     sangria); por omision, un comentario.
    Devuelve {"variables", "setup", "en_loop", "f_real", "error_pct"}; los
    trozos de setup y en_loop llevan sangria de 2 espacios.
    """
    _positivo(f_salida, "La frecuencia de salida")
    medio = 1.0 / (2 * f_salida)
    if medio < MEDIO_PERIODO_MINIMO_ARDUINO:
        raise ValueError(
            f"T/2 = {formato(medio, 's')} es demasiado corto para un loop() de Arduino "
            f"(minimo {formato(MEDIO_PERIODO_MINIMO_ARDUINO, 's')}); usa un timer por hardware.")
    if accion is None:
        accion = "// aqui va lo que pasa cada medio periodo (ej. invertir la salida)"
    micros_totales = int(round(medio * 1e6))
    t_real = micros_totales / 1e6
    f_real = 1.0 / (2 * t_real)
    error = _error_pct(f_real, f_salida)
    resumen = (f"// T/2 = {formato(medio, 's')} (f real {formato(f_real, 'Hz')}, "
               f"error {formato(error, '%')})")
    ms, us = divmod(micros_totales, 1000)

    if metodo == "delay":
        lineas = [f"  {renglon}" for renglon in accion.splitlines()]
        if ms:
            lineas.append(f"  delay({ms});")
        if us:
            lineas.append(f"  delayMicroseconds({us});")
        lineas.insert(0, f"  {resumen}")
        return {"variables": "// delay() no necesita variables", "setup": "",
                "en_loop": "\n".join(lineas), "f_real": f_real, "error_pct": error}

    if metodo == "millis":
        if us == 0:
            reloj, nombre, unidad, valor = "millis", "MEDIO_PERIODO_MS", "ms", ms
            ultimo = "ultimo_ms"
        else:
            reloj, nombre, unidad, valor = "micros", "MEDIO_PERIODO_US", "us", micros_totales
            ultimo = "ultimo_us"
        variables = "\n".join([
            resumen,
            f"const unsigned long {nombre} = {valor}UL;   // en {unidad}",
            f"unsigned long {ultimo} = 0;   // cuando paso el ultimo medio periodo",
        ])
        setup = f"  {ultimo} = {reloj}();"
        lineas = [
            f"  if ({reloj}() - {ultimo} >= {nombre}) {{   // la resta sin signo aguanta el desborde",
            f"    {ultimo} += {nombre};   // sumar, no copiar {reloj}(): asi el error no se acumula",
        ]
        lineas += [f"    {renglon}" for renglon in accion.splitlines()]
        lineas.append("  }")
        return {"variables": variables, "setup": setup, "en_loop": "\n".join(lineas),
                "f_real": f_real, "error_pct": error}

    raise ValueError(f"Metodo desconocido {metodo!r}: usa 'delay' o 'millis'.")


# ================================================================ VHDL

_IDENTIFICADOR_VHDL = re.compile(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)*$")

# Lo mas grande que cabe en un integer de VHDL (32 bits con signo garantizados).
ENTERO_MAXIMO_VHDL = 2147483647


def _validar_nombre_vhdl(nombre, que):
    if not isinstance(nombre, str) or not _IDENTIFICADOR_VHDL.match(nombre):
        raise ValueError(
            f"{que} {nombre!r} no sirve en VHDL: letras, numeros y '_' sueltos, "
            "empezando con letra.")
    if nombre.lower() in RESERVADAS:
        raise ValueError(f"{que} {nombre!r} es una palabra reservada; usa otro nombre.")


def _miles_o_decimal(valor):
    """Una frecuencia dentro de la formula: 1/3 sale 0.333333 y no 0.333."""
    if float(valor).is_integer():
        return formato(valor)
    return _decimal(valor, 6)


def _comentario_cuenta(calculo, nombre_salida):
    """Los renglones de comentario que explican la cuenta de un divisor."""
    n = calculo.cuenta_medio_periodo
    lineas = [
        f"-- {nombre_salida}: {formato(calculo.f_entrada, 'Hz')} -> "
        f"{formato(calculo.f_pedida, 'Hz')} (T = {formato(1 / calculo.f_pedida, 's')})",
        f"--   T/2 = {formato(1 / (2 * calculo.f_pedida), 's')}; N = f_entrada / (2 f_salida) = "
        f"{formato(calculo.f_entrada)} / (2 x {_miles_o_decimal(calculo.f_pedida)})"
        + (f" = {formato(n)} ciclos" if float(calculo.cuenta_ideal).is_integer()
           else f" = {formato(calculo.cuenta_ideal)}, redondeado a {formato(n)} ciclos"),
        f"--   el contador va de 0 a {formato(n - 1)} ({calculo.bits_contador} bits) y al "
        "llegar al final invierte la salida",
    ]
    if calculo.error_pct != 0:
        lineas.append(f"--   f real = {formato(calculo.f_real, 'Hz')} "
                      f"(error {formato(calculo.error_pct, '%')})")
    return lineas


def _calculo_vhdl(f_entrada, f_salida, que):
    calculo = calcular(f_entrada, f_salida)
    if calculo.cuenta_medio_periodo - 1 > ENTERO_MAXIMO_VHDL:
        raise ValueError(
            f"{que}: la cuenta ({formato(calculo.cuenta_medio_periodo)}) no cabe en un "
            "integer de VHDL (2 147 483 647); usa una frecuencia mas alta o divide en dos etapas.")
    return calculo


def _proceso_divisor(constante, cuenta, estado, etiqueta):
    """El process de un divisor: contador entero con reset asincrono y salida que se invierte."""
    return f"""\
    {etiqueta} : process (clk_in, rst)
    begin
        if rst = '1' then
            {cuenta} <= 0;
            {estado} <= '0';
        elsif rising_edge(clk_in) then
            if {cuenta} = {constante} - 1 then
                {cuenta} <= 0;
                {estado} <= not {estado};
            else
                {cuenta} <= {cuenta} + 1;
            end if;
        end if;
    end process {etiqueta};"""


def vhdl_divisor(f_entrada, f_salida, nombre="divisor"):
    """Entidad VHDL-93 completa que divide clk_in hasta f_salida con ciclo de 50 %.

    Puertos: clk_in, rst (asincrono, activo en alto, deja la salida en '0') y
    clk_out. Un contador entero con rango exacto (0 a N - 1) invierte la salida
    cada N ciclos. El comentario trae la cuenta: T/2 = N ciclos. ValueError si
    la frecuencia no cabe o la cuenta no cabe en un integer.
    """
    _validar_nombre_vhdl(nombre, "El nombre de la entidad")
    calculo = _calculo_vhdl(f_entrada, f_salida, nombre)
    n = calculo.cuenta_medio_periodo
    comentario = "\n".join(_comentario_cuenta(calculo, "clk_out"))
    return f"""\
-- {nombre}: divisor de reloj, generado por ktool {__version__}.
{comentario}
-- Reset asincrono (rst = '1'): contador en 0 y clk_out en '0'.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity {nombre} is
    port (
        clk_in  : in  std_logic;
        rst     : in  std_logic;
        clk_out : out std_logic
    );
end entity {nombre};

architecture contador of {nombre} is
    constant N : integer := {n};   -- ciclos de clk_in en medio periodo
    signal cuenta : integer range 0 to N - 1;
    signal estado : std_logic;      -- copia interna: un puerto out no se lee en VHDL-93
begin
{_proceso_divisor("N", "cuenta", "estado", "dividir")}

    clk_out <= estado;
end architecture contador;
"""


def vhdl_divisores(f_entrada, salidas, nombre="divisores"):
    """Una entidad con varias salidas divididas del mismo clk_in (ej. 1 Hz, 2 Hz, 1/3 Hz).

    salidas = {"hz1": 1, "hz2": 2, "s3": 1/3}: el nombre de cada puerto y su
    frecuencia en Hz. Cada salida lleva su propio contador y su propio process;
    todas comparten clk_in y rst (asincrono, activo en alto).
    """
    _validar_nombre_vhdl(nombre, "El nombre de la entidad")
    if not salidas:
        raise ValueError("Hace falta al menos una salida.")
    usados = {"clk_in": "clk_in", "rst": "rst", nombre.lower(): nombre}
    calculos = []
    for puerto, f in salidas.items():
        _validar_nombre_vhdl(puerto, "La salida")
        internos = [puerto, f"n_{puerto}", f"cuenta_{puerto}", f"estado_{puerto}",
                    f"dividir_{puerto}"]
        for interno in internos:
            clave = interno.lower()
            if clave in usados:
                raise ValueError(
                    f"La salida {puerto!r} choca con {usados[clave]!r}: VHDL no distingue "
                    "mayusculas y el nombre ya se usa en la entidad.")
            usados[clave] = interno
        calculos.append((puerto, _calculo_vhdl(f_entrada, f, puerto)))

    comentarios = []
    for puerto, calculo in calculos:
        comentarios += _comentario_cuenta(calculo, puerto)
    puertos = ["        clk_in : in  std_logic", "        rst    : in  std_logic"]
    puertos += [f"        {puerto} : out std_logic" for puerto, _ in calculos]
    declaraciones = []
    procesos = []
    asignaciones = []
    for puerto, calculo in calculos:
        declaraciones += [
            f"    constant n_{puerto} : integer := {calculo.cuenta_medio_periodo};"
            f"   -- T/2 de {puerto} en ciclos de clk_in",
            f"    signal cuenta_{puerto} : integer range 0 to n_{puerto} - 1;",
            f"    signal estado_{puerto} : std_logic;",
        ]
        procesos.append(_proceso_divisor(f"n_{puerto}", f"cuenta_{puerto}",
                                         f"estado_{puerto}", f"dividir_{puerto}"))
        asignaciones.append(f"    {puerto} <= estado_{puerto};")
    return f"""\
-- {nombre}: divisores de reloj, generado por ktool {__version__}.
{chr(10).join(comentarios)}
-- Reset asincrono (rst = '1'): contadores en 0 y salidas en '0'.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity {nombre} is
    port (
{(";" + chr(10)).join(puertos)}
    );
end entity {nombre};

architecture contadores of {nombre} is
{chr(10).join(declaraciones)}
begin
{(chr(10) + chr(10)).join(procesos)}

{chr(10).join(asignaciones)}
end architecture contadores;
"""


# ================================================================ SVG

def onda_svg(calculo, ancho=520, alto=120):
    """La onda cuadrada (2 periodos) con cotas de t_alto, t_bajo y T, en SVG.

    Acepta un Calculo o el dict de astable_555 / astable_555_para. Negro y
    gris, sin rellenos de color, para que se imprima bien. Devuelve el texto
    del elemento <svg>.
    """
    if isinstance(calculo, dict):
        t_alto, t_bajo = calculo["t_alto"], calculo["t_bajo"]
    else:
        t_alto, t_bajo = calculo.t_alto, calculo.t_bajo
    periodo = t_alto + t_bajo

    margen = 12
    entrada = 24                       # tramo en bajo antes del primer flanco
    ancho_periodo = (ancho - 2 * margen - entrada) / 2.0
    ancho_alto = ancho_periodo * t_alto / periodo
    y_cota_arriba = 22
    y_alto = 34
    y_bajo = alto - 40
    y_cota_abajo = alto - 22

    x = margen
    puntos = [(x, y_bajo)]
    x += entrada
    flancos = []
    for _ in range(2):
        flancos.append(x)
        puntos += [(x, y_bajo), (x, y_alto), (x + ancho_alto, y_alto), (x + ancho_alto, y_bajo)]
        x += ancho_periodo
    puntos.append((x, y_bajo))
    flancos.append(x)

    def n(v):
        return f"{v:.1f}".rstrip("0").rstrip(".")

    x0 = flancos[0]
    x_baja = x0 + ancho_alto
    x1 = flancos[1]
    texto_alto = f"t alto = {formato(t_alto, 's')}"
    texto_bajo = f"t bajo = {formato(t_bajo, 's')}"
    texto_t = f"T = {formato(periodo, 's')}"

    # Donde va el centro de cada texto de arriba. Con ciclo de trabajo extremo un
    # tramo es angosto y los dos textos chocarian: se separan a los lados del
    # flanco de bajada y se recorren para no salirse del dibujo.
    ancho_letra = 6.2                     # aproximado para 11 px sans-serif
    mitad_alto = ancho_letra * len(texto_alto) / 2
    mitad_bajo = ancho_letra * len(texto_bajo) / 2
    centro_alto = (x0 + x_baja) / 2
    centro_bajo = (x_baja + x1) / 2
    if centro_alto + mitad_alto + 6 > centro_bajo - mitad_bajo:
        centro_alto = x_baja - 6 - mitad_alto
        centro_bajo = x_baja + 6 + mitad_bajo
    centro_alto = max(centro_alto, 2 + mitad_alto)
    centro_bajo = max(centro_bajo, centro_alto + mitad_alto + 12 + mitad_bajo)
    centro_bajo = min(centro_bajo, ancho - 2 - mitad_bajo)

    # id del marcador distinto por onda: un HTML con varias ondas no repite ids
    flecha = f"flecha{zlib.crc32((texto_t + texto_alto + texto_bajo).encode('ascii')):08x}"

    def cota(xa, xb, y, texto, x_texto, y_texto):
        return [
            f'<line x1="{n(xa)}" y1="{n(y)}" x2="{n(xb)}" y2="{n(y)}" stroke="#555" '
            f'stroke-width="1" marker-start="url(#{flecha})" marker-end="url(#{flecha})"/>',
            f'<text x="{n(x_texto)}" y="{n(y_texto)}" text-anchor="middle">{texto}</text>',
        ]

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
        f'viewBox="0 0 {ancho} {alto}" font-family="sans-serif" font-size="11" fill="#222">',
        f"<title>Onda cuadrada: {texto_t}, {texto_alto}, {texto_bajo}</title>",
        "<defs>",
        f'<marker id="{flecha}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
        'markerHeight="6" orient="auto-start-reverse">',
        '<path d="M0,1 L9,5 L0,9" fill="none" stroke="#555" stroke-width="1.5"/>',
        "</marker>",
        "</defs>",
    ]
    # lineas de referencia punteadas en los flancos que limitan las cotas
    for xr in (x0, x_baja, x1):
        partes.append(f'<line x1="{n(xr)}" y1="{n(y_cota_arriba - 4)}" x2="{n(xr)}" '
                      f'y2="{n(y_cota_abajo + 4)}" stroke="#999" stroke-width="0.8" '
                      'stroke-dasharray="3,3"/>')
    partes.append('<polyline fill="none" stroke="#000" stroke-width="2" points="'
                  + " ".join(f"{n(px)},{n(py)}" for px, py in puntos) + '"/>')
    partes += cota(x0, x_baja, y_cota_arriba, texto_alto, centro_alto, y_cota_arriba - 6)
    partes += cota(x_baja, x1, y_cota_arriba, texto_bajo, centro_bajo, y_cota_arriba - 6)
    partes += cota(x0, x1, y_cota_abajo, texto_t, (x0 + x1) / 2, y_cota_abajo + 14)
    partes.append("</svg>")
    return "\n".join(partes)
