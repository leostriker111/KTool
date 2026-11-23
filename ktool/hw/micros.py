"""Codigo para microcontroladores: PIC (XC8), ESP32, Arduino, Blue Pill y Pico.

Todos hacen lo mismo, porque el circuito es combinacional: en un ciclo sin fin
leen las entradas, evaluan cada ecuacion y escriben las salidas. No hay retardos
ni interrupciones: la salida cambia unos microsegundos despues que la entrada.

Cada funcion devuelve el texto completo de un archivo; quien decide donde se
guarda es kit.py.
"""

from __future__ import annotations

from .. import __version__
from ..core.simplify import format_product, format_sum, literal_pairs
from . import ajustes, placas
from .modelo import ecuacion, tabla_de_pines


def _ecuaciones_comentadas(circuito, comentario):
    """Las ecuaciones minimizadas en notacion de clase, como comentario."""
    lineas = []
    for n in circuito.salidas:
        sol = circuito.elegidas[n]
        lineas.append(f"{comentario}   {n} = {sol.equation}   ({sol.form.upper()})")
    return "\n".join(lineas)


# ===================================================================== PIC

# Bits de configuracion, uno por chip. Los nombres son los de XC8 (se pueden
# consultar con `xc8-cc -mchip=<chip> -mprint-config`, o en MPLAB X en
# Window > Target Memory Views > Configuration Bits).
CONFIG_PIC = {
    "pic18f4550": """\
#pragma config PLLDIV = 1, CPUDIV = OSC1_PLL2, USBDIV = 1
#pragma config FOSC = INTOSCIO_EC   // oscilador interno, RA6 libre como I/O
#pragma config FCMEN = OFF, IESO = OFF
#pragma config PWRT = ON, BOR = ON, BORV = 3, VREGEN = OFF
#pragma config WDT = OFF            // sin perro guardian
#pragma config CCP2MX = ON, PBADEN = OFF, LPT1OSC = OFF
#pragma config MCLRE = ON           // la pata 1 es el reset (pon 10 kOhm a VDD)
#pragma config STVREN = ON, LVP = OFF, ICPRT = OFF, XINST = OFF""",

    "pic18f45k50": """\
#pragma config PLLSEL = PLL4X, CFGPLLEN = OFF, CPUDIV = NOCLKDIV, LS48MHZ = SYS24X4
#pragma config FOSC = INTOSCIO      // oscilador interno, RA6/RA7 libres como I/O
#pragma config PCLKEN = ON, FCMEN = OFF, IESO = OFF
#pragma config nPWRTEN = ON, BOREN = SBORDIS, BORV = 190, nLPBOR = ON
#pragma config WDTEN = OFF          // sin perro guardian
#pragma config CCP2MX = RC1, PBADEN = OFF, T3CMX = RC0, SDOMX = RB3
#pragma config MCLRE = ON           // la pata 1 es el reset (pon 10 kOhm a VDD)
#pragma config STVREN = ON, LVP = OFF, ICPRT = OFF, XINST = OFF""",

    "pic16f877a": """\
#pragma config FOSC = HS            // cristal de 20 MHz
#pragma config WDTE = OFF           // sin perro guardian
#pragma config PWRTE = ON, BOREN = ON
#pragma config LVP = OFF            // RB3 queda como I/O normal
#pragma config CPD = OFF, WRT = OFF, CP = OFF
// El 877A no tiene bit MCLRE: la pata 1 SIEMPRE es el reset (10 kOhm a VDD).""",

    "pic16f628a": """\
#pragma config FOSC = INTOSCIO      // oscilador interno, RA6/RA7 libres como I/O
#pragma config WDTE = OFF           // sin perro guardian
#pragma config PWRTE = ON, BOREN = ON
#pragma config MCLRE = ON           // la pata 4 es el reset (pon 10 kOhm a VDD)
#pragma config LVP = OFF            // RB4 queda como I/O normal
#pragma config CPD = OFF, CP = OFF""",

    "pic16f84a": """\
#pragma config FOSC = XT            // cristal de 4 MHz
#pragma config WDTE = OFF           // sin perro guardian
#pragma config PWRTE = ON, CP = OFF
// El 84A no tiene bits MCLRE ni LVP: la pata 4 SIEMPRE es el reset
// (10 kOhm a VDD) y no existe la programacion en bajo voltaje.""",
}

# Lo que apaga lo analogico de cada chip, para que las patas lean 0 y 1.
# Sin esto, en el 18F4550 una pata AN configurada como entrada siempre lee 0.
ANALOGICO_PIC = {
    "pic18f4550": """\
    ADCON1 = 0x0F;      // PCFG = 1111: todas las patas AN son digitales
    CMCON  = 0x07;      // comparadores apagados""",
    "pic18f45k50": """\
    ANSELA = 0x00;      // en el K50 cada puerto tiene su registro ANSEL
    ANSELB = 0x00;
    ANSELC = 0x00;
    ANSELD = 0x00;
    ANSELE = 0x00;
    CM1CON0 = 0x00;     // comparadores apagados
    CM2CON0 = 0x00;""",
    "pic16f877a": """\
    ADCON1 = 0x06;      // PCFG = 011x: PORTA y PORTE digitales (OJO: en el 877A
                        // es 0x06, no 0x0F; 0x0F deja AN0 como analogica)
    CMCON  = 0x07;      // comparadores apagados""",
    "pic16f628a": """\
    CMCON  = 0x07;      // comparadores apagados: PORTA queda digital""",
    "pic16f84a": """\
    // el 84A no tiene convertidor ni comparadores: nada que apagar""",
}

OSCILADOR_PIC = {
    "pic18f4550": "    OSCCON = 0x72;      // IRCF = 111 (8 MHz), SCS = 1x (oscilador interno)",
    "pic18f45k50": "    OSCCON = 0x70;      // IRCF = 111 (16 MHz con el HFINTOSC)",
    "pic16f877a": "    // el reloj lo da el cristal: no hay nada que configurar",
    "pic16f628a": "    PCONbits.OSCF = 1;  // oscilador interno a 4 MHz (no a 48 kHz)",
    "pic16f84a": "    // el reloj lo da el cristal: no hay nada que configurar",
}


# Bits IRCF de OSCCON (bits 6-4) para cada frecuencia del oscilador interno.
# Hojas de datos: PIC18F45K50 registro 3-1 (HFINTOSC) y PIC18F4550 registro 2-2
# (INTOSC). En el 4550 SCS = 10 elige el oscilador interno; en el K50 basta con
# SCS = 00, porque la palabra de configuracion ya dice FOSC = INTOSCIO.
IRCF_PIC18 = {
    "pic18f45k50": {16000000: 7, 8000000: 6, 4000000: 5, 2000000: 4, 1000000: 3,
                    500000: 2, 250000: 1, 31000: 0},
    "pic18f4550": {8000000: 7, 4000000: 6, 2000000: 5, 1000000: 4, 500000: 3,
                   250000: 2, 125000: 1, 31000: 0},
}


def osccon_pic18(chip, frecuencia):
    """La linea de C que pone el oscilador interno a `frecuencia` (en Hz)."""
    ircf = IRCF_PIC18[chip][frecuencia]
    scs = 0b10 if chip == "pic18f4550" else 0b00
    valor = (ircf << 4) | scs
    return (f"    OSCCON = 0x{valor:02X};      // IRCF = {ircf:03b}: oscilador interno a "
            f"{ajustes.hz_texto(frecuencia)}")


def _puerto(pin):
    """'RB3' -> ('B', 3)"""
    return pin[1], int(pin[2])


def palabras_estimadas(circuito):
    """Cuanta memoria de programa pide el .c del PIC, en palabras de instruccion.

    Medido con XC8 v3.10 gratuito (-O1) en el 16F84A y el 16F628A: el
    arranque y la escritura de puertos son unas 40 palabras y cada termino
    comparado con su mascara cuesta entre 8.7 y 9.3. Se cuentan 10 por termino
    para dejar margen. Con eso, un 16F84A recibe ~95 terminos en total: 4
    paridades de 6 variables en NAND (128 terminos) ya no caben, y se bloquea en
    vez de entregar un archivo que el compilador va a rechazar.
    """
    terminos = 0
    for s in circuito.salidas:
        sol = circuito.elegidas[s]
        if sol.const is not None:
            continue
        terminos += 1 if sol.form == "xor" else len(sol.patterns)
    return 45 + 10 * terminos, terminos


def _pasos_pic(circuito, salida):
    """Una salida del PIC como comparaciones de mascara, un termino por renglon.

    Por que no la ecuacion tal cual (como en Arduino): XC8 gratuito traduce
    cada `&` y cada `!` a varias instrucciones, y un circuito de 6 entradas y 7
    salidas ya no cabe en las 1024 palabras del 16F84A. Un termino como A'BC
    solo pregunta "A, B y C valen 0, 1 y 1": `(fila__ & 0b111000) == 0b011000`,
    unas cinco instrucciones sin importar cuantas letras tenga.

      SOP y solo NAND  la salida vale 1 si coincide alguno de sus terminos
      POS y solo NOR   la salida vale 0 si coincide alguno de los terminos del
                       complemento (los grupos de ceros del mapa)
      XOR              paridad de las variables que entran
    """
    sol = circuito.elegidas[salida]
    variables = circuito.entradas
    n = len(variables)
    destino = f"out_{salida}"

    def bit(v):
        return 1 << (n - 1 - variables.index(v))

    if sol.const is not None:
        return [f"uint8_t {destino} = {sol.const};   // {salida} es constante"]

    if sol.form == "xor":
        mascara = sum(bit(v) for v in sol.xor_vars)
        return [f"// {salida} = {sol.equation}: paridad de los bits de la mascara",
                f"uint8_t {destino} = {1 if sol.xnor else 0};",
                f"for (uint8_t m__ = (uint8_t)(fila__ & 0x{mascara:02X}); m__ != 0; m__ &= (uint8_t)(m__ - 1)) {{",
                f"    {destino} ^= 1;",
                "}"]

    suma_de_productos = sol.form in ("sop", "nand")
    if suma_de_productos:
        lineas = [f"// {salida} = {sol.equation}: vale 1 si coincide alguno de sus terminos",
                  f"uint8_t {destino} = 0;"]
    else:  # pos, nor: cada factor (A + B') vale 0 justo cuando A = 0 y B = 1
        lineas = [f"// {salida} = {sol.equation}: vale 0 si algun factor vale 0",
                  f"uint8_t {destino} = 1;"]
    for patron in sol.patterns:
        # el patron ('10-1') dice que valor pide cada variable; '-' no la mira
        mascara = valor = 0
        for v, negada in literal_pairs(patron, variables):
            mascara |= bit(v)
            if not negada:
                valor |= bit(v)
        if suma_de_productos:
            prueba, comentario = f"{destino} = 1;", format_product(patron, variables)
        else:
            prueba, comentario = f"{destino} = 0;", f"{format_sum(patron, variables)} vale 0"
        lineas.append(f"if ((fila__ & 0x{mascara:02X}) == 0x{valor:02X}) {prueba}   // {comentario}")
    return lineas


def reloj_pic(chip, valores):
    """(frecuencia en Hz, texto del reloj, linea de OSCCON) segun los ajustes.

    Los PIC 18F eligen su oscilador interno en la ventana del kit; los demas
    usan el de placas.py (cristal o interno fijo)."""
    info = placas.PIC[chip]
    if chip in IRCF_PIC18 and "oscilador" in valores:
        frecuencia = ajustes.hz(valores["oscilador"])
        texto = f"oscilador interno a {valores['oscilador']} (no hace falta cristal)"
        return frecuencia, texto, osccon_pic18(chip, frecuencia)
    return info["xtal"], info["reloj"], OSCILADOR_PIC[chip]


def config_pic(chip, valores):
    """Los bits de configuracion, con MCLR como entrada si asi se pidio."""
    texto = CONFIG_PIC[chip]
    if valores.get("mclr") == "entrada RE3":
        texto = texto.replace(
            "#pragma config MCLRE = ON           // la pata 1 es el reset (pon 10 kOhm a VDD)",
            "#pragma config MCLRE = OFF          // la pata 1 es la entrada RE3 (sin reset externo)")
    return texto


def pullups_pic(chip, entradas):
    """Las lineas que encienden las pull-up internas de PORTB, si hay entradas ahi.

    Solo PORTB las tiene. Con entradas activas en bajo, un boton a GND en RB0-RB7
    no necesita resistencia; en otro puerto si (10 kOhm a VDD)."""
    mascara = 0
    for r in entradas:
        p, bit = _puerto(r["pin"])
        if p == "B":
            mascara |= 1 << bit
    if not mascara:
        return []
    if chip == "pic18f45k50":
        return [f"    WPUB = 0x{mascara:02X};        // pull-up interna solo en las entradas de PORTB",
                "    INTCON2bits.nRBPU = 0;  // habilita las pull-up de PORTB"]
    return ["    INTCON2bits.RBPU = 0;   // habilita las pull-up de PORTB (todas)"]


def pic(circuito, chip, renglones, valores=None):
    """Archivo .c completo para XC8.

    `valores`: los ajustes de la placa (hw/ajustes.py), ya completos. Sin ellos
    sale como siempre: entradas y salidas activas en alto y el reloj de placas.py.
    """
    valores = valores or {}
    info = placas.PIC[chip]
    pic18 = info["familia"] == 18
    puertos = ["A", "B"] if info["patas"] is placas.PATAS_PIC_18 else ["A", "B", "C", "D", "E"]
    frecuencia, texto_reloj, linea_oscilador = reloj_pic(chip, valores)
    entradas_en_bajo = ajustes.entradas_invertidas(valores)
    salidas_en_bajo = ajustes.salidas_invertidas(valores)

    def pata(pin):
        return f"{pin} (pata {info['patas'][pin]})"

    entradas = [r for r in renglones if r["direccion"] == "entrada"]
    salidas = [r for r in renglones if r["direccion"] == "salida"]

    # Que bits de cada puerto son entrada (TRIS = 1). Todo lo demas queda de
    # salida en bajo: una pata al aire configurada como entrada consume y
    # mete ruido.
    tris = {p: 0 for p in puertos}
    for r in entradas:
        p, bit = _puerto(r["pin"])
        tris[p] |= 1 << bit

    escritura = "LAT" if pic18 else "PORT"
    salidas_por_puerto = {}
    for r in salidas:
        p, bit = _puerto(r["pin"])
        salidas_por_puerto.setdefault(p, []).append((bit, r["senal"]))

    if entradas_en_bajo:
        nota_entradas = (" * Entradas activas en bajo: cada boton va de la pata a GND. En PORTB\n"
                         " * se usa la pull-up interna; en otro puerto, 10 kOhm a VDD.")
    else:
        nota_entradas = (" * Cada entrada necesita su resistencia de 10 kOhm a GND (pull-down) para no\n"
                         " * quedar flotando cuando el interruptor esta abierto.")
    if salidas_en_bajo:
        nota_entradas += ("\n * Salidas activas en bajo: el LED va de VDD a la pata (con su resistencia)\n"
                          " * y enciende cuando la ecuacion vale 1.")

    lineas = [f"""\
/*
 * {circuito.nombre} en {info['titulo']} -- generado por ktool {__version__}
 * Compilador: MPLAB XC8 (proyecto de MPLAB X para {info['titulo']}).
 * Reloj: {texto_reloj}.
 *
 * Ecuaciones:
{_ecuaciones_comentadas(circuito, ' *')}
 *
 * Mapeo de pines:
{tabla_de_pines(renglones, ' *', pata)}
 *
{nota_entradas}
 */

#include <xc.h>
#include <stdint.h>

{config_pic(chip, valores)}

#define _XTAL_FREQ {frecuencia}UL

// Explicito antes de entrar al ciclo: reloj, lo analogico apagado y la
// direccion de cada pata.
static void configurar(void)
{{
{linea_oscilador}
{ANALOGICO_PIC[chip]}
"""]
    for p in puertos:
        lineas.append(f"    {escritura}{p} = 0x00;"
                      + ("        // salidas en bajo antes de habilitarlas" if p == puertos[0] else ""))
    for p in puertos:
        nota = "  // 1 = entrada, 0 = salida" if p == puertos[0] else ""
        lineas.append(f"    TRIS{p} = 0x{tris[p]:02X};{nota}")
    if entradas_en_bajo and pic18:
        lineas.extend(pullups_pic(chip, entradas))
    lineas.append("}\n")

    n = circuito.n_entradas
    lineas.append("void main(void)\n{\n    configurar();\n\n    while (1) {")
    lineas.append(f"        // 1. leer las entradas en un byte: {circuito.entradas[0]} es el bit "
                  f"{n - 1} y {circuito.entradas[-1]} el bit 0,")
    lineas.append("        //    igual que el numero de fila de la tabla de verdad")
    # "fila__" con doble guion bajo: ningun nombre de senal puede tenerlo
    # (validar_nombres lo prohibe), asi que nunca choca con una entrada X.
    lineas.append("        uint8_t fila__ = 0;")
    if entradas_en_bajo:
        lineas.append("        // activas en bajo: la pata en 0 (boton presionado) cuenta como 1")
    negar = "!" if entradas_en_bajo else ""
    for k, r in enumerate(entradas):
        p, bit = _puerto(r["pin"])
        lineas.append(f"        if ({negar}PORT{p}bits.R{p}{bit}) fila__ |= 0x{1 << (n - 1 - k):02X};"
                      f"   // {r['senal']}")
    lineas.append("\n        // 2. evaluar: cada termino minimizado es una mascara (que variables")
    lineas.append("        //    mira) y un valor (como deben estar). Es la misma ecuacion de")
    lineas.append("        //    arriba, pero cabe en la memoria de los PIC chicos.")
    for s in circuito.salidas:
        lineas.extend("        " + paso for paso in _pasos_pic(circuito, s))
    lineas.append("\n        // 3. escribir cada puerto de un golpe (sin leer-modificar-escribir)")
    if salidas_en_bajo:
        lineas.append("        //    activas en bajo: se escribe el complemento de cada salida")
    for p in puertos:
        if p not in salidas_por_puerto:
            continue
        if salidas_en_bajo:
            partes = " | ".join(f"((out_{s} ^ 1u) << {bit})" for bit, s in salidas_por_puerto[p])
        else:
            partes = " | ".join(f"(out_{s} << {bit})" for bit, s in salidas_por_puerto[p])
        lineas.append(f"        {escritura}{p} = (uint8_t)({partes});")
    lineas.append("    }\n}\n")
    return "\n".join(lineas)


# ========================================================= estilo Arduino

def arduino(circuito, renglones, titulo, nucleo, constante, modo_entrada, notas,
            entradas_en_bajo=False, salidas_en_bajo=False):
    """Sketch .ino para cualquier nucleo de Arduino (AVR, ESP32, STM32duino).

    constante(pin)     como se escribe el pin en C++ ('13', 'A0', 'PB12')
    modo_entrada(pin)  'INPUT_PULLDOWN', 'INPUT' o 'INPUT_PULLUP'
    notas              renglones extra para el encabezado
    entradas_en_bajo   el boton presionado lee LOW y cuenta como 1
    salidas_en_bajo    un 1 de la ecuacion se escribe LOW (LED a VCC)
    """
    entradas = [r for r in renglones if r["direccion"] == "entrada"]
    salidas = [r for r in renglones if r["direccion"] == "salida"]
    tipo = "uint32_t" if nucleo == "STM32duino" else "uint8_t"
    texto_notas = "\n".join(f"// {n}" for n in notas)

    lineas = [f"""\
// {circuito.nombre} en {titulo} -- generado por ktool {__version__}
// Nucleo: {nucleo}
//
// Ecuaciones:
{_ecuaciones_comentadas(circuito, '//')}
//
// Mapeo de pines:
{tabla_de_pines(renglones, '//')}
//
{texto_notas}
"""]
    for r in renglones:
        lineas.append(f"const {tipo} PIN_{r['senal']} = {constante(r['pin'])};")
    lineas.append("\nvoid setup() {")
    for r in entradas:
        lineas.append(f"  pinMode(PIN_{r['senal']}, {modo_entrada(r['pin'])});")
    for r in salidas:
        lineas.append(f"  pinMode(PIN_{r['senal']}, OUTPUT);")
    lineas.append("}\n")
    lineas.append("// Combinacional: leer, evaluar y escribir, sin pausa.")
    lineas.append("void loop() {")
    activo, inactivo = ("LOW", "HIGH") if salidas_en_bajo else ("HIGH", "LOW")
    for r in entradas:
        lineas.append(f"  uint8_t in_{r['senal']} = digitalRead(PIN_{r['senal']}) == "
                      f"{'LOW' if entradas_en_bajo else 'HIGH'};")
    lineas.append("")
    for n in circuito.salidas:
        lineas.append(f"  uint8_t out_{n} = {ecuacion(circuito.arboles[n], 'c', 'in_')};")
    lineas.append("")
    for r in salidas:
        lineas.append(f"  digitalWrite(PIN_{r['senal']}, out_{r['senal']} ? {activo} : {inactivo});")
    lineas.append("}\n")
    return "\n".join(lineas)


def esp32_arduino(circuito, variante, renglones):
    info = placas.ESP32[variante]
    sin_pd = set(info["sin_pulldown"])
    return arduino(
        circuito, renglones, info["titulo"], "Arduino-ESP32 (esp32 de Espressif)",
        constante=str,
        modo_entrada=lambda pin: "INPUT" if pin in sin_pd else "INPUT_PULLDOWN",
        notas=["Las entradas usan la resistencia pull-down interna (INPUT_PULLDOWN),",
               "salvo los GPIO 34-39, que no la tienen. GPIO6-11 son de la flash y",
               "nunca se usan. Logica de 3.3 V: no metas 5 V a ninguna entrada."])


def avr(circuito, variante, renglones, valores=None):
    """Sketch del Uno/Nano o del Mega, con los ajustes de entradas y salidas."""
    valores = valores or {}
    info = placas.ARDUINO[variante]
    en_bajo = ajustes.entradas_invertidas(valores)
    if en_bajo:
        notas = ["Entradas con INPUT_PULLUP: cada boton va de la pata a GND y, presionado,",
                 "cuenta como 1. D0/D1 quedan libres para el Serial (el USB)."]
    else:
        notas = ["El ATmega no tiene pull-down interno: pon 10 kOhm de cada entrada",
                 "a GND. D0/D1 quedan libres para el Serial (el USB)."]
    if ajustes.salidas_invertidas(valores):
        notas.append("Salidas activas en bajo: el LED va de 5 V a la pata, con su resistencia.")
    return arduino(
        circuito, renglones, info["titulo"], "Arduino AVR (arduino:avr)",
        constante=str,
        modo_entrada=lambda pin: "INPUT_PULLUP" if en_bajo else "INPUT",
        notas=notas, entradas_en_bajo=en_bajo,
        salidas_en_bajo=ajustes.salidas_invertidas(valores))


def bluepill(circuito, renglones):
    return arduino(
        circuito, renglones, placas.BLUEPILL["titulo"], "STM32duino (STMicroelectronics:stm32)",
        constante=str,
        modo_entrada=lambda pin: "INPUT_PULLDOWN",
        notas=["Las entradas estan en pines tolerantes a 5 V (FT) y usan el pull-down",
               "interno. Las salidas dan 3.3 V: alcanza como 1 para TTL (VIH = 2 V).",
               "PC13 (el LED) no se usa: solo aguanta 3 mA."])


# ============================================================ MicroPython

def micropython(circuito, renglones, titulo, sin_pulldown=()):
    """main.py para MicroPython (ESP32 y Pico).

    El ciclo va dentro de `if __name__ == "__main__"`: MicroPython corre main.py
    como __main__, y asi el archivo tambien se puede importar para probarlo en
    la computadora sin que se quede atorado.
    """
    entradas = [r for r in renglones if r["direccion"] == "entrada"]
    salidas = [r for r in renglones if r["direccion"] == "salida"]
    lineas = [f'''\
# {circuito.nombre} en {titulo} -- generado por ktool {__version__}
# MicroPython: copialo a la placa como main.py (Thonny o mpremote).
#
# Ecuaciones:
{_ecuaciones_comentadas(circuito, '#')}
#
# Mapeo de pines:
{tabla_de_pines(renglones, '#')}
#
# Las entradas usan la resistencia pull-down interna para no quedar flotando
# en la protoboard.

from machine import Pin
''']
    for r in entradas:
        if r["pin"] in sin_pulldown:
            lineas.append(f"pin_{r['senal']} = Pin({r['pin']}, Pin.IN)  "
                          "# sin pull-down interno: 10 kOhm a GND")
        else:
            lineas.append(f"pin_{r['senal']} = Pin({r['pin']}, Pin.IN, Pin.PULL_DOWN)")
    for r in salidas:
        lineas.append(f"pin_{r['senal']} = Pin({r['pin']}, Pin.OUT)")
    lineas.append("\n\ndef evaluar():")
    lineas.append('    """Una pasada: leer, evaluar y escribir."""')
    for r in entradas:
        lineas.append(f"    in_{r['senal']} = pin_{r['senal']}.value()")
    for n in circuito.salidas:
        lineas.append(f"    out_{n} = {ecuacion(circuito.arboles[n], 'python', 'in_')}")
    for r in salidas:
        lineas.append(f"    pin_{r['senal']}.value(out_{r['senal']})")
    lineas.append('\n\nif __name__ == "__main__":')
    lineas.append("    while True:")
    lineas.append("        evaluar()\n")
    return "\n".join(lineas)


def esp32_micropython(circuito, variante, renglones):
    info = placas.ESP32[variante]
    return micropython(circuito, renglones, info["titulo"], set(info["sin_pulldown"]))


def pico(circuito, renglones):
    return micropython(circuito, renglones, placas.PICO["titulo"])
