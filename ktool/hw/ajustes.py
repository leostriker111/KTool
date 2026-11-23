"""Los ajustes de cada placa: lo que cambia el codigo sin cambiar el circuito.

El circuito (la tabla o la maquina) dice QUE se calcula. Los ajustes dicen COMO
lo arma cada placa: el oscilador del PIC, si los botones de la tarjeta de la
MAX II son activos en bajo, si el Arduino usa INPUT_PULLUP, a que frecuencia
avanza un contador... Cada placa tiene los suyos, y la ventana del kit los
dibuja a partir de esta lista: un ajuste con `opciones` es una lista
desplegable; uno sin opciones es un numero.

Solo estan los ajustes que el generador de verdad respeta. Una placa sin
ajustes (las ESP32, la Blue Pill, la Pico, los PIC de 16 bits) se genera con
los valores de su hoja de datos, como siempre.

Los valores se guardan tal como se ven en pantalla (el texto de la opcion), y
asi el proyecto .ktool.json se lee sin tablas de traduccion.
"""

from __future__ import annotations


class Ajuste:
    """Un ajuste de una placa.

    clave       nombre interno ('oscilador'), el que leen los generadores
    etiqueta    lo que dice la ventana ('Oscilador')
    opciones    textos de la lista desplegable; None si es un numero
    omision     el valor de entrada
    ayuda       una linea que explica para que sirve
    secuencial  True si solo importa en maquinas de estado (la frecuencia,
                el metodo de retardo...): la ventana los apaga en una tabla
    """

    def __init__(self, clave, etiqueta, opciones, omision, ayuda, secuencial=False):
        self.clave = clave
        self.etiqueta = etiqueta
        self.opciones = opciones
        self.omision = omision
        self.ayuda = ayuda
        self.secuencial = secuencial


# ------------------------------------------------------------- comunes

def _entradas(alto, bajo):
    return Ajuste("entradas", "Entradas", [alto, bajo], alto,
                  "Como se conecta cada boton o interruptor. Activas en bajo invierte "
                  "la lectura: el boton presionado vale 1 en la tabla.")


def _salidas():
    return Ajuste("salidas", "Salidas", ["activas en alto", "activas en bajo"],
                  "activas en alto",
                  "Activas en bajo invierte cada salida: para LEDs conectados a VCC "
                  "(como los de muchas tarjetas de practica).")


def _frecuencia():
    return Ajuste("frecuencia_hz", "Frecuencia de la maquina (Hz)", None, 1.0,
                  "Cuantos estados avanza por segundo. 1 Hz se ve a simple vista. "
                  "La calculadora de frecuencia la puede llenar.", secuencial=True)


# --------------------------------------------------------------- PIC 18F

# Frecuencias del HFINTOSC que se eligen con los bits IRCF de OSCCON. El 18F4550
# solo llega a 8 MHz con su oscilador interno.
OSCILADOR_45K50 = ["16 MHz", "8 MHz", "4 MHz", "2 MHz", "1 MHz", "500 kHz", "250 kHz", "31 kHz"]
OSCILADOR_4550 = ["8 MHz", "4 MHz", "2 MHz", "1 MHz", "500 kHz", "250 kHz", "125 kHz", "31 kHz"]

LENGUAJES_PIC = ["C (XC8)", "Ensamblador (pic-as)", "C y ensamblador"]
RETARDOS_PIC = ["por instrucciones (__delay_ms / subrutina)", "Timer0"]


def _pic18(osciladores):
    return [
        Ajuste("lenguaje", "Lenguaje", LENGUAJES_PIC, "C y ensamblador",
               "C se compila con XC8; el ensamblador, con pic-as (los dos vienen en "
               "MPLAB X)."),
        Ajuste("oscilador", "Oscilador interno", osciladores, osciladores[0],
               "La frecuencia del oscilador interno (bits IRCF de OSCCON). Un ciclo "
               "de instruccion dura 4 periodos del oscilador."),
        Ajuste("mclr", "Pata 1", ["MCLR (reset)", "entrada RE3"], "MCLR (reset)",
               "Con MCLR la pata 1 reinicia el PIC y necesita 10 kOhm a VDD."),
        _entradas("activas en alto (10 kOhm a GND)", "activas en bajo (boton a GND)"),
        _salidas(),
        Ajuste("retardo", "Retardo", RETARDOS_PIC, RETARDOS_PIC[0],
               "Como espera medio periodo: contando instrucciones o con el Timer0.",
               secuencial=True),
        _frecuencia(),
    ]


# ------------------------------------------------------------- MAX II

METODOS_VHDL = ["ecuaciones (flip-flops D)", "ecuaciones (flip-flops JK)",
                "ecuaciones (flip-flops T)", "ecuaciones (flip-flops SR)",
                "tabla de estados", "diagrama de estados"]

MAX2 = [
    Ajuste("reloj_hz", "Reloj de la tarjeta (Hz)", None, 50000000.0,
           "El oscilador que trae la tarjeta, conectado a una pata GCLK.",
           secuencial=True),
    _frecuencia(),
    Ajuste("metodo", "Metodo VHDL", METODOS_VHDL, METODOS_VHDL[0],
           "Los tres metodos de la practica de circuitos secuenciales. Con "
           "ecuaciones se elige el flip-flop.", secuencial=True),
    Ajuste("reset", "Reset", ["boton activo en bajo", "activo en alto", "sin reset"],
           "boton activo en bajo",
           "El reset lleva la maquina a su estado inicial sin esperar al reloj.",
           secuencial=True),
    _entradas("activas en alto", "activas en bajo (botones de la tarjeta)"),
    _salidas(),
]

# ------------------------------------------------------------- Arduino

ARDUINO = [
    _entradas("INPUT (10 kOhm a GND)", "INPUT_PULLUP (boton a GND)"),
    _salidas(),
    Ajuste("tiempo", "Retardo", ["delay()", "millis()"], "delay()",
           "delay() detiene todo; millis() deja leer las entradas mientras espera.",
           secuencial=True),
    _frecuencia(),
    Ajuste("serial", "Monitor serie", ["no", "si (9600 baudios)"], "no",
           "Imprime el estado en cada paso, para revisar la secuencia en la "
           "computadora.", secuencial=True),
]

AJUSTES = {
    "pic18f45k50": _pic18(OSCILADOR_45K50),
    "pic18f4550": _pic18(OSCILADOR_4550),
    "max2": MAX2,
    "uno_nano": ARDUINO,
    "mega2560": ARDUINO,
}


def de(placa):
    """La lista de ajustes de una placa ([] si no tiene)."""
    return AJUSTES.get(placa, [])


def con_omision(placa, valores=None):
    """{clave: valor} completo: lo que dio el usuario y, lo que falte, de omision.

    Un valor que ya no esta entre las opciones (un proyecto viejo) se cambia por
    el de omision en vez de llegar al generador. Un numero que no se puede leer
    es un ValueError con el nombre del ajuste.
    """
    valores = valores or {}
    completos = {}
    for a in de(placa):
        valor = valores.get(a.clave, a.omision)
        if a.opciones is None:
            try:
                valor = float(str(valor).replace(",", "."))
            except ValueError:
                raise ValueError(f"{a.etiqueta}: {valor!r} no es un numero") from None
            if valor <= 0:
                raise ValueError(f"{a.etiqueta}: tiene que ser mayor que cero")
        elif valor not in a.opciones:
            valor = a.omision
        completos[a.clave] = valor
    return completos


def hz(texto):
    """'16 MHz' -> 16000000, '500 kHz' -> 500000: el oscilador como numero."""
    numero, unidad = texto.split()
    factor = {"Hz": 1, "kHz": 1000, "MHz": 1000000}[unidad]
    return int(float(numero) * factor)


def hz_texto(frecuencia):
    """16000000 -> '16 MHz': lo contrario de `hz`, para los comentarios."""
    for factor, unidad in ((1000000, "MHz"), (1000, "kHz")):
        if frecuencia >= factor:
            return f"{frecuencia / factor:g} {unidad}"
    return f"{frecuencia:g} Hz"


def entradas_invertidas(valores):
    """True si las entradas son activas en bajo (el boton presionado lee 0)."""
    return "bajo" in valores.get("entradas", "") or "PULLUP" in valores.get("entradas", "")


def salidas_invertidas(valores):
    return valores.get("salidas") == "activas en bajo"


def lenguajes_pic(valores):
    """('c', 'asm'), ('c',) o ('asm',) segun el ajuste de lenguaje."""
    texto = valores.get("lenguaje", "C (XC8)")
    if texto.startswith("C y"):
        return ("c", "asm")
    return ("asm",) if texto.startswith("Ensamblador") else ("c",)


def numero_legible(valor):
    """50000000.0 -> '50 000 000', 2.5 -> '2.5': sin notacion cientifica."""
    if float(valor).is_integer():
        return f"{int(valor):,}".replace(",", " ")
    return f"{valor:g}"


def resumen(placa, valores, secuencial=False):
    """[(etiqueta, valor)] para la tabla de configuracion del documento.

    Los ajustes que solo usan las maquinas de estado (frecuencia, retardo,
    metodo VHDL, reset) no salen en el documento de una tabla: ahi no hacen
    nada y confundirian al que lo lee."""
    completos = con_omision(placa, valores)
    renglones = []
    for a in de(placa):
        if a.secuencial and not secuencial:
            continue
        valor = completos[a.clave]
        if a.opciones is None:
            valor = numero_legible(valor)
        renglones.append((a.etiqueta, valor))
    return renglones
