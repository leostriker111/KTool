"""El dibujo real de cada placa: su encapsulado o la tarjeta con sus cabezales.

placas.py dice QUE pines se pueden usar; este archivo dice DONDE estan. Con los
dos se dibuja el componente como en el Pin Planner de Quartus: cada pata en su
lugar, con su nombre, y las que reciben una senal con el nombre de la senal.

Igual que placas.py, aqui casi todo son DATOS. Cada encapsulado es un dict:

    titulo   lo que se escribe arriba del dibujo
    forma    "dip" (dos filas de patas), "qfp" (cuatro lados) o "placa"
             (la tarjeta con sus cabezales)
    lados    el orden de dibujo en cada lado: "izquierda" y "derecha" de arriba
             abajo, "arriba" y "abajo" de izquierda a derecha. Un None deja el
             hueco de una pata (la separacion entre dos cabezales). El lado
             "doble_derecha" es el cabezal doble del Mega: renglones
             (pata interior, pata exterior) de arriba abajo.
    patas    {numero: Pata}
    cabezales  (solo placas) [(nombre, [numeros en el orden de su serigrafia])],
             para decir "J3-5" en vez de "pata 24"
    conector (solo placas) (lado, texto): donde va el USB
    preferidos  (opcional) {"reloj": [ids], "reset": [ids]}: los pines
             especiales a donde "Que ktool las elija" manda esas senales
    nota     orientacion y aclaraciones

Cada Pata es (numero, etiqueta, id, funciones, tipo):
    numero    la pata del encapsulado, o la posicion corrida en los cabezales
    etiqueta  lo que se dibuja junto a la pata ("RB0", "GND", "D13", "IO32")
    id        el identificador del pin en placas.py ("RB0", 26, "PB12", "13",
              "A0"), o None si ktool no lo ofrece para senales
    funciones el nombre completo de la hoja de datos, para la barra de estado
    tipo      uno de TIPOS

Fuera de los datos estan `asignables`, `pata_de`, `puede_ir`, `geometria` (las
coordenadas que comparten el SVG y la ventana) y `svg`.
"""

from __future__ import annotations

from collections import namedtuple
from xml.sax.saxutils import escape

from . import placas

Pata = namedtuple("Pata", "numero etiqueta id funciones tipo")

TIPOS = ("io", "vdd", "gnd", "reloj", "reset", "prog", "jtag", "usb", "flash", "nc", "otro")

# Tipos de pata que nunca llevan una senal del usuario: si alguno tuviera un id
# que placas.py ofrece, el dibujo y el catalogo se contradirian.
TIPOS_SIN_SENAL = ("vdd", "gnd", "jtag", "flash", "usb", "nc")

# Texto del tipo para la barra de estado
NOMBRE_TIPO = {
    "io": "entrada/salida", "vdd": "alimentacion", "gnd": "tierra",
    "reloj": "reloj", "reset": "reset", "prog": "programacion",
    "jtag": "JTAG", "usb": "USB", "flash": "memoria flash", "nc": "sin conexion",
    "otro": "uso especial",
}


def _patas(*lista):
    """Las patas como {numero: Pata}. Existe para escribir cada pata en un solo
    renglon legible, sin repetir el numero como llave."""
    return {pata.numero: pata for pata in lista}


# ===================================================================== PIC 40

# Fuente: Microchip, PIC18F2455/2550/4455/4550 Data Sheet, DS39632E, figura
# "40-Pin PDIP" de "Pin Diagrams".
PIC18F4550 = {
    "titulo": "PIC18F4550 (PDIP-40)",
    "forma": "dip",
    "lados": {"izquierda": list(range(1, 21)), "derecha": list(range(40, 20, -1))},
    "patas": _patas(
        Pata(1, "MCLR", None, "MCLR/VPP/RE3", "reset"),
        Pata(2, "RA0", "RA0", "RA0/AN0", "io"),
        Pata(3, "RA1", "RA1", "RA1/AN1", "io"),
        Pata(4, "RA2", "RA2", "RA2/AN2/VREF-/CVREF", "io"),
        Pata(5, "RA3", "RA3", "RA3/AN3/VREF+", "io"),
        Pata(6, "RA4", None, "RA4/T0CKI/C1OUT/RCV (drenador abierto)", "io"),
        Pata(7, "RA5", "RA5", "RA5/AN4/SS/HLVDIN/C2OUT", "io"),
        Pata(8, "RE0", "RE0", "RE0/AN5/CK1SPP", "io"),
        Pata(9, "RE1", "RE1", "RE1/AN6/CK2SPP", "io"),
        Pata(10, "RE2", "RE2", "RE2/AN7/OESPP", "io"),
        Pata(11, "VDD", None, "VDD", "vdd"),
        Pata(12, "VSS", None, "VSS", "gnd"),
        Pata(13, "OSC1", None, "OSC1/CLKI", "reloj"),
        Pata(14, "OSC2", None, "OSC2/CLKO/RA6", "reloj"),
        Pata(15, "RC0", "RC0", "RC0/T1OSO/T13CKI", "io"),
        Pata(16, "RC1", "RC1", "RC1/T1OSI/CCP2/UOE", "io"),
        Pata(17, "RC2", "RC2", "RC2/CCP1/P1A", "io"),
        Pata(18, "VUSB", None, "VUSB (regulador interno del USB, capacitor a GND)", "usb"),
        Pata(19, "RD0", "RD0", "RD0/SPP0", "io"),
        Pata(20, "RD1", "RD1", "RD1/SPP1", "io"),
        Pata(21, "RD2", "RD2", "RD2/SPP2", "io"),
        Pata(22, "RD3", "RD3", "RD3/SPP3", "io"),
        Pata(23, "RC4", None, "RC4/D-/VM (USB; como pin, solo entrada)", "usb"),
        Pata(24, "RC5", None, "RC5/D+/VP (USB; como pin, solo entrada)", "usb"),
        Pata(25, "RC6", "RC6", "RC6/TX/CK", "io"),
        Pata(26, "RC7", "RC7", "RC7/RX/DT/SDO", "io"),
        Pata(27, "RD4", "RD4", "RD4/SPP4", "io"),
        Pata(28, "RD5", "RD5", "RD5/SPP5/P1B", "io"),
        Pata(29, "RD6", "RD6", "RD6/SPP6/P1C", "io"),
        Pata(30, "RD7", "RD7", "RD7/SPP7/P1D", "io"),
        Pata(31, "VSS", None, "VSS", "gnd"),
        Pata(32, "VDD", None, "VDD", "vdd"),
        Pata(33, "RB0", "RB0", "RB0/AN12/INT0/FLT0/SDI/SDA", "io"),
        Pata(34, "RB1", "RB1", "RB1/AN10/INT1/SCK/SCL", "io"),
        Pata(35, "RB2", "RB2", "RB2/AN8/INT2/VMO", "io"),
        Pata(36, "RB3", "RB3", "RB3/AN9/CCP2/VPO", "io"),
        Pata(37, "RB4", "RB4", "RB4/AN11/KBI0/CSSPP", "io"),
        Pata(38, "RB5", "RB5", "RB5/KBI1/PGM (con LVP activo es PGM)", "io"),
        Pata(39, "RB6", None, "RB6/KBI2/PGC (reloj del PICkit)", "prog"),
        Pata(40, "RB7", None, "RB7/KBI3/PGD (datos del PICkit)", "prog"),
    ),
    "nota": "Vista superior, muesca arriba. La pata 18 es VUSB, no RC3.",
}

# Fuente: Microchip, PIC18(L)F2X/45K50 Data Sheet, DS30000684B, figura 3
# "40-Pin PDIP (600 mil)" y tabla 1 "PIC18(L)F2X/45K50 Pin Summary".
PIC18F45K50 = {
    "titulo": "PIC18F45K50 (PDIP-40)",
    "forma": "dip",
    "lados": {"izquierda": list(range(1, 21)), "derecha": list(range(40, 20, -1))},
    "patas": _patas(
        Pata(1, "MCLR", None, "MCLR/VPP/RE3 (RE3 solo entrada)", "reset"),
        Pata(2, "RA0", "RA0", "RA0/AN0/C12IN0-", "io"),
        Pata(3, "RA1", "RA1", "RA1/AN1/C12IN1-/CTCMP", "io"),
        Pata(4, "RA2", "RA2", "RA2/AN2/C2IN+/VREF-/DACOUT", "io"),
        Pata(5, "RA3", "RA3", "RA3/AN3/C1IN+/VREF+", "io"),
        Pata(6, "RA4", None, "RA4/C1OUT/SRQ/T0CKI", "io"),
        Pata(7, "RA5", "RA5", "RA5/AN4/C2OUT/SRNQ/HLVDIN/SS", "io"),
        Pata(8, "RE0", "RE0", "RE0/AN5", "io"),
        Pata(9, "RE1", "RE1", "RE1/AN6", "io"),
        Pata(10, "RE2", "RE2", "RE2/AN7", "io"),
        Pata(11, "VDD", None, "VDD", "vdd"),
        Pata(12, "VSS", None, "VSS", "gnd"),
        Pata(13, "RA7", None, "RA7/OSC1/CLKI", "reloj"),
        Pata(14, "RA6", None, "RA6/OSC2/CLKO", "reloj"),
        Pata(15, "RC0", "RC0", "RC0/SOSCO/T1CKI/T3CKI/T3G", "io"),
        Pata(16, "RC1", "RC1", "RC1/SOSCI/CCP2", "io"),
        Pata(17, "RC2", "RC2", "RC2/AN14/CTPLS/CCP1/P1A", "io"),
        Pata(18, "VUSB3V3", None, "VUSB3V3/VDDCORE (regulador de 3.3 V del USB, "
                                  "capacitor a GND)", "usb"),
        Pata(19, "RD0", "RD0", "RD0/AN20", "io"),
        Pata(20, "RD1", "RD1", "RD1/AN21", "io"),
        Pata(21, "RD2", "RD2", "RD2/AN22", "io"),
        Pata(22, "RD3", "RD3", "RD3/AN23", "io"),
        Pata(23, "D-", None, "D-/RC4/IOCC4 (USB; como pin, solo entrada)", "usb"),
        Pata(24, "D+", None, "D+/RC5/IOCC5 (USB; como pin, solo entrada)", "usb"),
        Pata(25, "RC6", "RC6", "RC6/AN18/TX/CK/IOCC6", "io"),
        Pata(26, "RC7", "RC7", "RC7/AN19/RX/DT/SDO/IOCC7", "io"),
        Pata(27, "RD4", "RD4", "RD4/AN24", "io"),
        Pata(28, "RD5", "RD5", "RD5/AN25/P1B", "io"),
        Pata(29, "RD6", "RD6", "RD6/AN26/P1C", "io"),
        Pata(30, "RD7", "RD7", "RD7/AN27/P1D", "io"),
        Pata(31, "VSS", None, "VSS", "gnd"),
        Pata(32, "VDD", None, "VDD", "vdd"),
        Pata(33, "RB0", "RB0", "RB0/AN12/INT0/FLT0/SRI/SDI/SDA", "io"),
        Pata(34, "RB1", "RB1", "RB1/AN10/C12IN3-/INT1/SCK/SCL", "io"),
        Pata(35, "RB2", "RB2", "RB2/AN8/INT2/CTED1", "io"),
        Pata(36, "RB3", "RB3", "RB3/AN9/C12IN2-/CTED2/CCP2 (alterno)/SDO (alterno)", "io"),
        Pata(37, "RB4", "RB4", "RB4/AN11/IOCB4", "io"),
        Pata(38, "RB5", "RB5", "RB5/AN13/T1G/T3CKI (alterno)/IOCB5", "io"),
        Pata(39, "RB6", None, "RB6/IOCB6/PGC (reloj del PICkit)", "prog"),
        Pata(40, "RB7", None, "RB7/IOCB7/PGD (datos del PICkit)", "prog"),
    ),
    "nota": "Vista superior, muesca arriba. La pata 18 es VUSB3V3, no RC3; "
            "13 y 14 son RA7 y RA6 cuando no hay cristal.",
}

# Fuente: Microchip, PIC16F87XA Data Sheet, DS39582B, figura "40-Pin PDIP" de
# "Pin Diagrams".
PIC16F877A = {
    "titulo": "PIC16F877A (PDIP-40)",
    "forma": "dip",
    "lados": {"izquierda": list(range(1, 21)), "derecha": list(range(40, 20, -1))},
    "patas": _patas(
        Pata(1, "MCLR", None, "MCLR/VPP", "reset"),
        Pata(2, "RA0", "RA0", "RA0/AN0", "io"),
        Pata(3, "RA1", "RA1", "RA1/AN1", "io"),
        Pata(4, "RA2", "RA2", "RA2/AN2/VREF-/CVREF", "io"),
        Pata(5, "RA3", "RA3", "RA3/AN3/VREF+", "io"),
        Pata(6, "RA4", None, "RA4/T0CKI/C1OUT (drenador abierto)", "io"),
        Pata(7, "RA5", "RA5", "RA5/AN4/SS/C2OUT", "io"),
        Pata(8, "RE0", "RE0", "RE0/RD/AN5", "io"),
        Pata(9, "RE1", "RE1", "RE1/WR/AN6", "io"),
        Pata(10, "RE2", "RE2", "RE2/CS/AN7", "io"),
        Pata(11, "VDD", None, "VDD", "vdd"),
        Pata(12, "VSS", None, "VSS", "gnd"),
        Pata(13, "OSC1", None, "OSC1/CLKI (cristal)", "reloj"),
        Pata(14, "OSC2", None, "OSC2/CLKO (cristal)", "reloj"),
        Pata(15, "RC0", "RC0", "RC0/T1OSO/T1CKI", "io"),
        Pata(16, "RC1", "RC1", "RC1/T1OSI/CCP2", "io"),
        Pata(17, "RC2", "RC2", "RC2/CCP1", "io"),
        Pata(18, "RC3", "RC3", "RC3/SCK/SCL", "io"),
        Pata(19, "RD0", "RD0", "RD0/PSP0", "io"),
        Pata(20, "RD1", "RD1", "RD1/PSP1", "io"),
        Pata(21, "RD2", "RD2", "RD2/PSP2", "io"),
        Pata(22, "RD3", "RD3", "RD3/PSP3", "io"),
        Pata(23, "RC4", "RC4", "RC4/SDI/SDA", "io"),
        Pata(24, "RC5", "RC5", "RC5/SDO", "io"),
        Pata(25, "RC6", "RC6", "RC6/TX/CK", "io"),
        Pata(26, "RC7", "RC7", "RC7/RX/DT", "io"),
        Pata(27, "RD4", "RD4", "RD4/PSP4", "io"),
        Pata(28, "RD5", "RD5", "RD5/PSP5", "io"),
        Pata(29, "RD6", "RD6", "RD6/PSP6", "io"),
        Pata(30, "RD7", "RD7", "RD7/PSP7", "io"),
        Pata(31, "VSS", None, "VSS", "gnd"),
        Pata(32, "VDD", None, "VDD", "vdd"),
        Pata(33, "RB0", "RB0", "RB0/INT", "io"),
        Pata(34, "RB1", "RB1", "RB1", "io"),
        Pata(35, "RB2", "RB2", "RB2", "io"),
        Pata(36, "RB3", "RB3", "RB3/PGM (con LVP activo es PGM)", "io"),
        Pata(37, "RB4", "RB4", "RB4", "io"),
        Pata(38, "RB5", "RB5", "RB5", "io"),
        Pata(39, "RB6", None, "RB6/PGC (reloj del PICkit)", "prog"),
        Pata(40, "RB7", None, "RB7/PGD (datos del PICkit)", "prog"),
    ),
    "nota": "Vista superior, muesca arriba. Sin USB: la pata 18 es RC3.",
}

# ===================================================================== PIC 18

# Fuente: Microchip, PIC16F627A/628A/648A Data Sheet, DS40044G, "Pin Diagrams",
# PDIP/SOIC de 18 patas.
PIC16F628A = {
    "titulo": "PIC16F628A (PDIP-18)",
    "forma": "dip",
    "lados": {"izquierda": list(range(1, 10)), "derecha": list(range(18, 9, -1))},
    "patas": _patas(
        Pata(1, "RA2", "RA2", "RA2/AN2/VREF", "io"),
        Pata(2, "RA3", "RA3", "RA3/AN3/CMP1", "io"),
        Pata(3, "RA4", "RA4", "RA4/T0CKI/CMP2 (drenador abierto)", "io"),
        Pata(4, "RA5", None, "RA5/MCLR/VPP (como pin, solo entrada)", "reset"),
        Pata(5, "VSS", None, "VSS", "gnd"),
        Pata(6, "RB0", "RB0", "RB0/INT", "io"),
        Pata(7, "RB1", "RB1", "RB1/RX/DT", "io"),
        Pata(8, "RB2", "RB2", "RB2/TX/CK", "io"),
        Pata(9, "RB3", "RB3", "RB3/CCP1", "io"),
        Pata(10, "RB4", "RB4", "RB4/PGM", "io"),
        Pata(11, "RB5", "RB5", "RB5", "io"),
        Pata(12, "RB6", "RB6", "RB6/T1OSO/T1CKI/PGC", "io"),
        Pata(13, "RB7", "RB7", "RB7/T1OSI/PGD", "io"),
        Pata(14, "VDD", None, "VDD", "vdd"),
        Pata(15, "RA6", "RA6", "RA6/OSC2/CLKOUT (libre con el oscilador interno)", "io"),
        Pata(16, "RA7", "RA7", "RA7/OSC1/CLKIN (libre con el oscilador interno)", "io"),
        Pata(17, "RA0", "RA0", "RA0/AN0", "io"),
        Pata(18, "RA1", "RA1", "RA1/AN1", "io"),
    ),
    "nota": "Vista superior, muesca arriba.",
}

# Fuente: Microchip, PIC16F84A Data Sheet, DS35007C, "Pin Diagrams" (PDIP de
# 18 patas) y tabla 1-1 "PIC16F84A Pinout Description".
PIC16F84A = {
    "titulo": "PIC16F84A (PDIP-18)",
    "forma": "dip",
    "lados": {"izquierda": list(range(1, 10)), "derecha": list(range(18, 9, -1))},
    "patas": _patas(
        Pata(1, "RA2", "RA2", "RA2", "io"),
        Pata(2, "RA3", "RA3", "RA3", "io"),
        Pata(3, "RA4", "RA4", "RA4/T0CKI (drenador abierto)", "io"),
        Pata(4, "MCLR", None, "MCLR/VPP", "reset"),
        Pata(5, "VSS", None, "VSS", "gnd"),
        Pata(6, "RB0", "RB0", "RB0/INT", "io"),
        Pata(7, "RB1", "RB1", "RB1", "io"),
        Pata(8, "RB2", "RB2", "RB2", "io"),
        Pata(9, "RB3", "RB3", "RB3", "io"),
        Pata(10, "RB4", "RB4", "RB4", "io"),
        Pata(11, "RB5", "RB5", "RB5", "io"),
        Pata(12, "RB6", "RB6", "RB6 (reloj de la programacion serial)", "io"),
        Pata(13, "RB7", "RB7", "RB7 (datos de la programacion serial)", "io"),
        Pata(14, "VDD", None, "VDD", "vdd"),
        Pata(15, "OSC2", None, "OSC2/CLKOUT (cristal)", "reloj"),
        Pata(16, "OSC1", None, "OSC1/CLKIN (cristal)", "reloj"),
        Pata(17, "RA0", "RA0", "RA0", "io"),
        Pata(18, "RA1", "RA1", "RA1", "io"),
    ),
    "nota": "Vista superior, muesca arriba. No tiene RA5-RA7 ni oscilador interno.",
}

# ================================================================== MAX II

# Fuente: Intel/Altera, "Pin Information for the MAX II EPM240/EPM240G Devices",
# version 1.4 (PT-EPM240-1.4): "Dedicated Pin Information" para la columna
# 100-Pin TQFP y "I/O Pin Information" para el banco de cada pata.
#   TMS 22, TDI 23, TCK 24, TDO 25; GNDINT 11, 65; VCCINT 13, 63;
#   VCCIO1 9, 31, 45; VCCIO2 59, 80, 94; GNDIO 10, 32, 46, 60, 79, 93.
# Las patas de I/O de usuario son las de placas.EPM240_BANCO_1 y _2. En el
# dibujo, "B1" y "B2" son I/O de usuario del banco 1 y del banco 2.
EPM240 = {
    "titulo": "MAX II EPM240T100C5 (TQFP-100)",
    "forma": "qfp",
    "lados": {
        "izquierda": list(range(1, 26)),
        "abajo": list(range(26, 51)),
        "derecha": list(range(75, 50, -1)),
        "arriba": list(range(100, 75, -1)),
    },
    "patas": _patas(
        Pata(1, "B2", 1, "IO, banco 2", "io"),
        Pata(2, "B1", 2, "IO, banco 1", "io"),
        Pata(3, "B1", 3, "IO, banco 1", "io"),
        Pata(4, "B1", 4, "IO, banco 1", "io"),
        Pata(5, "B1", 5, "IO, banco 1", "io"),
        Pata(6, "B1", 6, "IO, banco 1", "io"),
        Pata(7, "B1", 7, "IO, banco 1", "io"),
        Pata(8, "B1", 8, "IO, banco 1", "io"),
        Pata(9, "VCCIO1", None, "VCCIO1 (alimentacion de I/O del banco 1)", "vdd"),
        Pata(10, "GNDIO", None, "GNDIO", "gnd"),
        Pata(11, "GNDINT", None, "GNDINT", "gnd"),
        Pata(12, "GCLK0", 12, "IO/GCLK0, banco 1", "reloj"),
        Pata(13, "VCCINT", None, "VCCINT (3.3 V o 2.5 V en el EPM240)", "vdd"),
        Pata(14, "GCLK1", 14, "IO/GCLK1, banco 1", "reloj"),
        Pata(15, "B1", 15, "IO, banco 1", "io"),
        Pata(16, "B1", 16, "IO, banco 1", "io"),
        Pata(17, "B1", 17, "IO, banco 1", "io"),
        Pata(18, "B1", 18, "IO, banco 1", "io"),
        Pata(19, "B1", 19, "IO, banco 1", "io"),
        Pata(20, "B1", 20, "IO, banco 1", "io"),
        Pata(21, "B1", 21, "IO, banco 1", "io"),
        Pata(22, "TMS", None, "TMS (JTAG)", "jtag"),
        Pata(23, "TDI", None, "TDI (JTAG)", "jtag"),
        Pata(24, "TCK", None, "TCK (JTAG)", "jtag"),
        Pata(25, "TDO", None, "TDO (JTAG)", "jtag"),
        Pata(26, "B1", 26, "IO, banco 1", "io"),
        Pata(27, "B1", 27, "IO, banco 1", "io"),
        Pata(28, "B1", 28, "IO, banco 1", "io"),
        Pata(29, "B1", 29, "IO, banco 1", "io"),
        Pata(30, "B1", 30, "IO, banco 1", "io"),
        Pata(31, "VCCIO1", None, "VCCIO1 (alimentacion de I/O del banco 1)", "vdd"),
        Pata(32, "GNDIO", None, "GNDIO", "gnd"),
        Pata(33, "B1", 33, "IO, banco 1", "io"),
        Pata(34, "B1", 34, "IO, banco 1", "io"),
        Pata(35, "B1", 35, "IO, banco 1", "io"),
        Pata(36, "B1", 36, "IO, banco 1", "io"),
        Pata(37, "B1", 37, "IO, banco 1", "io"),
        Pata(38, "B1", 38, "IO, banco 1", "io"),
        Pata(39, "B1", 39, "IO, banco 1", "io"),
        Pata(40, "B1", 40, "IO, banco 1", "io"),
        Pata(41, "B1", 41, "IO, banco 1", "io"),
        Pata(42, "B1", 42, "IO, banco 1", "io"),
        Pata(43, "DEV_OE", 43, "IO/DEV_OE, banco 1 (en bajo apaga todas las salidas "
                               "si se habilita)", "reset"),
        Pata(44, "DEV_CLRn", 44, "IO/DEV_CLRn, banco 1 (en bajo borra todos los "
                                 "registros si se habilita)", "reset"),
        Pata(45, "VCCIO1", None, "VCCIO1 (alimentacion de I/O del banco 1)", "vdd"),
        Pata(46, "GNDIO", None, "GNDIO", "gnd"),
        Pata(47, "B1", 47, "IO, banco 1", "io"),
        Pata(48, "B1", 48, "IO, banco 1", "io"),
        Pata(49, "B1", 49, "IO, banco 1", "io"),
        Pata(50, "B1", 50, "IO, banco 1", "io"),
        Pata(51, "B1", 51, "IO, banco 1", "io"),
        Pata(52, "B2", 52, "IO, banco 2", "io"),
        Pata(53, "B2", 53, "IO, banco 2", "io"),
        Pata(54, "B2", 54, "IO, banco 2", "io"),
        Pata(55, "B2", 55, "IO, banco 2", "io"),
        Pata(56, "B2", 56, "IO, banco 2", "io"),
        Pata(57, "B2", 57, "IO, banco 2", "io"),
        Pata(58, "B2", 58, "IO, banco 2", "io"),
        Pata(59, "VCCIO2", None, "VCCIO2 (alimentacion de I/O del banco 2)", "vdd"),
        Pata(60, "GNDIO", None, "GNDIO", "gnd"),
        Pata(61, "B2", 61, "IO, banco 2", "io"),
        Pata(62, "GCLK2", 62, "IO/GCLK2, banco 2", "reloj"),
        Pata(63, "VCCINT", None, "VCCINT (3.3 V o 2.5 V en el EPM240)", "vdd"),
        Pata(64, "GCLK3", 64, "IO/GCLK3, banco 2", "reloj"),
        Pata(65, "GNDINT", None, "GNDINT", "gnd"),
        Pata(66, "B2", 66, "IO, banco 2", "io"),
        Pata(67, "B2", 67, "IO, banco 2", "io"),
        Pata(68, "B2", 68, "IO, banco 2", "io"),
        Pata(69, "B2", 69, "IO, banco 2", "io"),
        Pata(70, "B2", 70, "IO, banco 2", "io"),
        Pata(71, "B2", 71, "IO, banco 2", "io"),
        Pata(72, "B2", 72, "IO, banco 2", "io"),
        Pata(73, "B2", 73, "IO, banco 2", "io"),
        Pata(74, "B2", 74, "IO, banco 2", "io"),
        Pata(75, "B2", 75, "IO, banco 2", "io"),
        Pata(76, "B2", 76, "IO, banco 2", "io"),
        Pata(77, "B2", 77, "IO, banco 2", "io"),
        Pata(78, "B2", 78, "IO, banco 2", "io"),
        Pata(79, "GNDIO", None, "GNDIO", "gnd"),
        Pata(80, "VCCIO2", None, "VCCIO2 (alimentacion de I/O del banco 2)", "vdd"),
        Pata(81, "B2", 81, "IO, banco 2", "io"),
        Pata(82, "B2", 82, "IO, banco 2", "io"),
        Pata(83, "B2", 83, "IO, banco 2", "io"),
        Pata(84, "B2", 84, "IO, banco 2", "io"),
        Pata(85, "B2", 85, "IO, banco 2", "io"),
        Pata(86, "B2", 86, "IO, banco 2", "io"),
        Pata(87, "B2", 87, "IO, banco 2", "io"),
        Pata(88, "B2", 88, "IO, banco 2", "io"),
        Pata(89, "B2", 89, "IO, banco 2", "io"),
        Pata(90, "B2", 90, "IO, banco 2", "io"),
        Pata(91, "B2", 91, "IO, banco 2", "io"),
        Pata(92, "B2", 92, "IO, banco 2", "io"),
        Pata(93, "GNDIO", None, "GNDIO", "gnd"),
        Pata(94, "VCCIO2", None, "VCCIO2 (alimentacion de I/O del banco 2)", "vdd"),
        Pata(95, "B2", 95, "IO, banco 2", "io"),
        Pata(96, "B2", 96, "IO, banco 2", "io"),
        Pata(97, "B2", 97, "IO, banco 2", "io"),
        Pata(98, "B2", 98, "IO, banco 2", "io"),
        Pata(99, "B2", 99, "IO, banco 2", "io"),
        Pata(100, "B2", 100, "IO, banco 2", "io"),
    ),
    # A donde manda "Que ktool las elija" el reloj y el reset, en este orden:
    # los relojes a la red global de reloj y el reset a DEV_CLRn.
    "preferidos": {"reloj": [12, 14, 62, 64], "reset": [44, 43]},
    "nota": "Vista superior, pata 1 arriba a la izquierda, numeracion en sentido "
            "contrario al reloj. B1/B2: I/O de usuario del banco 1/2.",
}

# ================================================================== ESP32

# Fuente: Espressif, "ESP32-DevKitC V4 Getting Started Guide", tablas de los
# cabezales J2 y J3 (esp-dev-kits). Numeracion: J2-1..19 son las patas 1-19 y
# J3-1..19 son las patas 20-38, ambos de arriba (antena) hacia abajo (USB).
ESP32_DEVKITC = {
    "titulo": "ESP32-DevKitC V4 (ESP32-WROOM-32, 38 pines)",
    "forma": "placa",
    "lados": {"izquierda": list(range(1, 20)), "derecha": list(range(20, 39))},
    "cabezales": [("J2", list(range(1, 20))), ("J3", list(range(20, 39)))],
    "conector": ("abajo", "USB"),
    "patas": _patas(
        Pata(1, "3V3", None, "3V3: alimentacion de 3.3 V", "vdd"),
        Pata(2, "EN", None, "EN: CHIP_PU, reset", "reset"),
        Pata(3, "VP", 36, "GPIO36, ADC1_CH0, S_VP (solo entrada)", "io"),
        Pata(4, "VN", 39, "GPIO39, ADC1_CH3, S_VN (solo entrada)", "io"),
        Pata(5, "IO34", 34, "GPIO34, ADC1_CH6, VDET_1 (solo entrada)", "io"),
        Pata(6, "IO35", 35, "GPIO35, ADC1_CH7, VDET_2 (solo entrada)", "io"),
        Pata(7, "IO32", 32, "GPIO32, ADC1_CH4, TOUCH_CH9, XTAL_32K_P", "io"),
        Pata(8, "IO33", 33, "GPIO33, ADC1_CH5, TOUCH_CH8, XTAL_32K_N", "io"),
        Pata(9, "IO25", 25, "GPIO25, ADC2_CH8, DAC_1", "io"),
        Pata(10, "IO26", 26, "GPIO26, ADC2_CH9, DAC_2", "io"),
        Pata(11, "IO27", 27, "GPIO27, ADC2_CH7, TOUCH_CH7", "io"),
        Pata(12, "IO14", 14, "GPIO14, ADC2_CH6, TOUCH_CH6, MTMS", "io"),
        Pata(13, "IO12", 12, "GPIO12, ADC2_CH5, TOUCH_CH5, MTDI", "io"),
        Pata(14, "GND", None, "GND", "gnd"),
        Pata(15, "IO13", 13, "GPIO13, ADC2_CH4, TOUCH_CH4, MTCK", "io"),
        Pata(16, "D2", None, "GPIO9, D2 (memoria flash)", "flash"),
        Pata(17, "D3", None, "GPIO10, D3 (memoria flash)", "flash"),
        Pata(18, "CMD", None, "GPIO11, CMD (memoria flash)", "flash"),
        Pata(19, "5V", None, "5V: alimentacion de 5 V", "vdd"),
        Pata(20, "GND", None, "GND", "gnd"),
        Pata(21, "IO23", 23, "GPIO23", "io"),
        Pata(22, "IO22", 22, "GPIO22", "io"),
        Pata(23, "TX", None, "GPIO1, U0TXD (grabacion y monitor serial)", "prog"),
        Pata(24, "RX", None, "GPIO3, U0RXD (grabacion y monitor serial)", "prog"),
        Pata(25, "IO21", 21, "GPIO21", "io"),
        Pata(26, "GND", None, "GND", "gnd"),
        Pata(27, "IO19", 19, "GPIO19", "io"),
        Pata(28, "IO18", 18, "GPIO18", "io"),
        Pata(29, "IO5", 5, "GPIO5", "io"),
        Pata(30, "IO17", 17, "GPIO17", "io"),
        Pata(31, "IO16", 16, "GPIO16", "io"),
        Pata(32, "IO4", 4, "GPIO4, ADC2_CH0, TOUCH_CH0", "io"),
        Pata(33, "IO0", 0, "GPIO0, ADC2_CH1, TOUCH_CH1, Boot", "io"),
        Pata(34, "IO2", 2, "GPIO2, ADC2_CH2, TOUCH_CH2", "io"),
        Pata(35, "IO15", 15, "GPIO15, ADC2_CH3, TOUCH_CH3, MTDO", "io"),
        Pata(36, "D1", None, "GPIO8, D1 (memoria flash)", "flash"),
        Pata(37, "D0", None, "GPIO7, D0 (memoria flash)", "flash"),
        Pata(38, "CLK", None, "GPIO6, CLK (memoria flash)", "flash"),
    ),
    "nota": "Vista superior: antena arriba, USB abajo. J2 a la izquierda, J3 a la "
            "derecha. Los IO del dibujo son el numero de GPIO.",
}

# Fuente: Espressif, "ESP32-S3-DevKitC-1 v1.1 User Guide", tablas de los
# cabezales J1 y J3 (esp-dev-kits). J1-1..22 son las patas 1-22 y J3-1..22 las
# patas 23-44, de arriba (antena) hacia abajo (USB).
ESP32_S3_DEVKITC = {
    "titulo": "ESP32-S3-DevKitC-1 (44 pines)",
    "forma": "placa",
    "lados": {"izquierda": list(range(1, 23)), "derecha": list(range(23, 45))},
    "cabezales": [("J1", list(range(1, 23))), ("J3", list(range(23, 45)))],
    "conector": ("abajo", "USB"),
    "patas": _patas(
        Pata(1, "3V3", None, "3V3: alimentacion de 3.3 V", "vdd"),
        Pata(2, "3V3", None, "3V3: alimentacion de 3.3 V", "vdd"),
        Pata(3, "RST", None, "RST: EN, reset", "reset"),
        Pata(4, "4", 4, "GPIO4, RTC_GPIO4, TOUCH4, ADC1_CH3", "io"),
        Pata(5, "5", 5, "GPIO5, RTC_GPIO5, TOUCH5, ADC1_CH4", "io"),
        Pata(6, "6", 6, "GPIO6, RTC_GPIO6, TOUCH6, ADC1_CH5", "io"),
        Pata(7, "7", 7, "GPIO7, RTC_GPIO7, TOUCH7, ADC1_CH6", "io"),
        Pata(8, "15", 15, "GPIO15, RTC_GPIO15, U0RTS, ADC2_CH4, XTAL_32K_P", "io"),
        Pata(9, "16", 16, "GPIO16, RTC_GPIO16, U0CTS, ADC2_CH5, XTAL_32K_N", "io"),
        Pata(10, "17", 17, "GPIO17, RTC_GPIO17, U1TXD, ADC2_CH6", "io"),
        Pata(11, "18", 18, "GPIO18, RTC_GPIO18, U1RXD, ADC2_CH7, CLK_OUT3", "io"),
        Pata(12, "8", 8, "GPIO8, RTC_GPIO8, TOUCH8, ADC1_CH7, SUBSPICS1", "io"),
        Pata(13, "3", None, "GPIO3, RTC_GPIO3, TOUCH3, ADC1_CH2 (pin de strapping)", "io"),
        Pata(14, "46", None, "GPIO46 (pin de strapping)", "io"),
        Pata(15, "9", 9, "GPIO9, RTC_GPIO9, TOUCH9, ADC1_CH8, FSPIHD", "io"),
        Pata(16, "10", 10, "GPIO10, RTC_GPIO10, TOUCH10, ADC1_CH9, FSPICS0", "io"),
        Pata(17, "11", 11, "GPIO11, RTC_GPIO11, TOUCH11, ADC2_CH0, FSPID", "io"),
        Pata(18, "12", 12, "GPIO12, RTC_GPIO12, TOUCH12, ADC2_CH1, FSPICLK", "io"),
        Pata(19, "13", 13, "GPIO13, RTC_GPIO13, TOUCH13, ADC2_CH2, FSPIQ", "io"),
        Pata(20, "14", 14, "GPIO14, RTC_GPIO14, TOUCH14, ADC2_CH3, FSPIWP", "io"),
        Pata(21, "5V", None, "5V: alimentacion de 5 V", "vdd"),
        Pata(22, "G", None, "GND", "gnd"),
        Pata(23, "G", None, "GND", "gnd"),
        Pata(24, "TX", None, "GPIO43, U0TXD, CLK_OUT1 (grabacion y monitor serial)", "prog"),
        Pata(25, "RX", None, "GPIO44, U0RXD, CLK_OUT2 (grabacion y monitor serial)", "prog"),
        Pata(26, "1", 1, "GPIO1, RTC_GPIO1, TOUCH1, ADC1_CH0", "io"),
        Pata(27, "2", 2, "GPIO2, RTC_GPIO2, TOUCH2, ADC1_CH1", "io"),
        Pata(28, "42", 42, "GPIO42, MTMS (JTAG)", "io"),
        Pata(29, "41", 41, "GPIO41, MTDI (JTAG), CLK_OUT1", "io"),
        Pata(30, "40", 40, "GPIO40, MTDO (JTAG), CLK_OUT2", "io"),
        Pata(31, "39", 39, "GPIO39, MTCK (JTAG), CLK_OUT3, SUBSPICS1", "io"),
        Pata(32, "38", 38, "GPIO38, FSPIWP, SUBSPIWP, LED RGB (v1.1)", "io"),
        Pata(33, "37", None, "GPIO37, SPIDQS (PSRAM octal en los modulos R8)", "flash"),
        Pata(34, "36", None, "GPIO36, SPIIO7 (PSRAM octal en los modulos R8)", "flash"),
        Pata(35, "35", None, "GPIO35, SPIIO6 (PSRAM octal en los modulos R8)", "flash"),
        Pata(36, "0", None, "GPIO0, RTC_GPIO0 (pin de strapping, boton BOOT)", "io"),
        Pata(37, "45", None, "GPIO45 (pin de strapping)", "io"),
        Pata(38, "48", 48, "GPIO48, SPICLK_N, LED RGB (v1.0)", "io"),
        Pata(39, "47", 47, "GPIO47, SPICLK_P", "io"),
        Pata(40, "21", 21, "GPIO21, RTC_GPIO21", "io"),
        Pata(41, "20", None, "GPIO20, USB_D+, U1CTS, ADC2_CH9", "usb"),
        Pata(42, "19", None, "GPIO19, USB_D-, U1RTS, ADC2_CH8", "usb"),
        Pata(43, "G", None, "GND", "gnd"),
        Pata(44, "G", None, "GND", "gnd"),
    ),
    "nota": "Vista superior: antena arriba, los dos USB abajo. J1 a la izquierda, "
            "J3 a la derecha. Los numeros del dibujo son el numero de GPIO.",
}

# Fuente: Espressif, "ESP32-C3-DevKitM-1 User Guide", tablas de los cabezales J1
# y J3 (esp-dev-kits). Se dibuja la DevKitM-1 (la oficial, documentada); la
# SuperMini es de terceros y no tiene hoja oficial. J1-1..15 son las patas 1-15
# y J3-1..15 las patas 16-30, de arriba (antena) hacia abajo (USB).
ESP32_C3_DEVKITM = {
    "titulo": "ESP32-C3-DevKitM-1 (30 pines)",
    "forma": "placa",
    "lados": {"izquierda": list(range(1, 16)), "derecha": list(range(16, 31))},
    "cabezales": [("J1", list(range(1, 16))), ("J3", list(range(16, 31)))],
    "conector": ("abajo", "USB"),
    "patas": _patas(
        Pata(1, "GND", None, "GND", "gnd"),
        Pata(2, "3V3", None, "3V3: alimentacion de 3.3 V", "vdd"),
        Pata(3, "3V3", None, "3V3: alimentacion de 3.3 V", "vdd"),
        Pata(4, "IO2", 2, "GPIO2, ADC1_CH2, FSPIQ (pin de strapping)", "io"),
        Pata(5, "IO3", 3, "GPIO3, ADC1_CH3", "io"),
        Pata(6, "GND", None, "GND", "gnd"),
        Pata(7, "RST", None, "RST: CHIP_PU, reset", "reset"),
        Pata(8, "GND", None, "GND", "gnd"),
        Pata(9, "IO0", 0, "GPIO0, ADC1_CH0, XTAL_32K_P", "io"),
        Pata(10, "IO1", 1, "GPIO1, ADC1_CH1, XTAL_32K_N", "io"),
        Pata(11, "IO10", 10, "GPIO10, FSPICS0", "io"),
        Pata(12, "GND", None, "GND", "gnd"),
        Pata(13, "5V", None, "5V: alimentacion de 5 V", "vdd"),
        Pata(14, "5V", None, "5V: alimentacion de 5 V", "vdd"),
        Pata(15, "GND", None, "GND", "gnd"),
        Pata(16, "GND", None, "GND", "gnd"),
        Pata(17, "TX", 21, "GPIO21, U0TXD", "io"),
        Pata(18, "RX", 20, "GPIO20, U0RXD", "io"),
        Pata(19, "GND", None, "GND", "gnd"),
        Pata(20, "IO9", 9, "GPIO9 (pin de strapping, boton BOOT)", "io"),
        Pata(21, "IO8", 8, "GPIO8, LED RGB (pin de strapping)", "io"),
        Pata(22, "GND", None, "GND", "gnd"),
        Pata(23, "IO7", 7, "GPIO7, FSPID, MTDO", "io"),
        Pata(24, "IO6", 6, "GPIO6, FSPICLK, MTCK", "io"),
        Pata(25, "IO5", 5, "GPIO5, ADC2_CH0, FSPIWP, MTDI", "io"),
        Pata(26, "IO4", 4, "GPIO4, ADC1_CH4, FSPIHD, MTMS", "io"),
        Pata(27, "GND", None, "GND", "gnd"),
        Pata(28, "IO18", None, "GPIO18, USB_D-", "usb"),
        Pata(29, "IO19", None, "GPIO19, USB_D+", "usb"),
        Pata(30, "GND", None, "GND", "gnd"),
    ),
    "nota": "Se dibuja la DevKitM-1 de Espressif. Vista superior: antena arriba, "
            "USB abajo. En la SuperMini los mismos GPIO estan en otro orden.",
}

# ================================================================ Arduino

# Fuente: Arduino, "Arduino UNO R3 full pinout" (A000066-full-pinout.pdf,
# docs.arduino.cc). Ahi la placa va con el USB arriba; aqui se gira un cuarto de
# vuelta para dejar el USB a la izquierda, el cabezal digital arriba y la
# alimentacion y los analogicos abajo, como se ve la placa en la mesa.
# Numeracion corrida por cabezal, de izquierda a derecha.
ARDUINO_UNO = {
    "titulo": "Arduino Uno R3 (ATmega328P)",
    "forma": "placa",
    "lados": {
        "arriba": list(range(1, 11)) + [None] + list(range(11, 19)),
        "abajo": list(range(19, 27)) + [None] + list(range(27, 33)),
    },
    "cabezales": [("DIGITAL A", list(range(1, 11))), ("DIGITAL B", list(range(11, 19))),
                  ("POWER", list(range(19, 27))), ("ANALOG IN", list(range(27, 33)))],
    "conector": ("izquierda", "USB"),
    "patas": _patas(
        Pata(1, "SCL", None, "SCL (es el mismo pin que A5)", "otro"),
        Pata(2, "SDA", None, "SDA (es el mismo pin que A4)", "otro"),
        Pata(3, "AREF", None, "AREF: referencia del convertidor analogico", "otro"),
        Pata(4, "GND", None, "GND", "gnd"),
        Pata(5, "D13", "13", "D13, PB5, SCK, LED_BUILTIN", "io"),
        Pata(6, "D12", "12", "D12, PB4, CIPO", "io"),
        Pata(7, "D11", "11", "D11, PB3, COPI, PWM", "io"),
        Pata(8, "D10", "10", "D10, PB2, SS, PWM", "io"),
        Pata(9, "D9", "9", "D9, PB1, PWM", "io"),
        Pata(10, "D8", "8", "D8, PB0", "io"),
        Pata(11, "D7", "7", "D7, PD7", "io"),
        Pata(12, "D6", "6", "D6, PD6, PWM", "io"),
        Pata(13, "D5", "5", "D5, PD5, PWM", "io"),
        Pata(14, "D4", "4", "D4, PD4", "io"),
        Pata(15, "D3", "3", "D3, PD3, PWM, INT1", "io"),
        Pata(16, "D2", "2", "D2, PD2, INT0", "io"),
        Pata(17, "D1", None, "D1, PD1, TX (el USB serial: grabacion y monitor)", "prog"),
        Pata(18, "D0", None, "D0, PD0, RX (el USB serial: grabacion y monitor)", "prog"),
        Pata(19, "NC", None, "Sin conexion", "nc"),
        Pata(20, "IOREF", None, "IOREF: voltaje de las I/O (5 V)", "vdd"),
        Pata(21, "RESET", None, "RESET, PC6", "reset"),
        Pata(22, "3V3", None, "3V3: salida de 3.3 V", "vdd"),
        Pata(23, "5V", None, "5V: salida de 5 V", "vdd"),
        Pata(24, "GND", None, "GND", "gnd"),
        Pata(25, "GND", None, "GND", "gnd"),
        Pata(26, "VIN", None, "VIN: entrada de 7 a 12 V", "vdd"),
        Pata(27, "A0", "A0", "A0, D14, PC0, ADC0", "io"),
        Pata(28, "A1", "A1", "A1, D15, PC1, ADC1", "io"),
        Pata(29, "A2", "A2", "A2, D16, PC2, ADC2", "io"),
        Pata(30, "A3", "A3", "A3, D17, PC3, ADC3", "io"),
        Pata(31, "A4", "A4", "A4, D18, PC4, ADC4, SDA", "io"),
        Pata(32, "A5", "A5", "A5, D19, PC5, ADC5, SCL", "io"),
    ),
    "nota": "Vista superior con el USB a la izquierda: cabezal digital arriba, "
            "alimentacion y analogicos abajo.",
}

# Fuente: Arduino, "Arduino Nano full pinout" (A000005-full-pinout.pdf,
# docs.arduino.cc), con el USB arriba. Numeracion de la hoja de la Nano: la pata
# 1 es D1/TX (abajo a la derecha) y sube hasta D12 (15); la 16 es D13 (arriba a
# la izquierda) y baja hasta VIN (30).
ARDUINO_NANO = {
    "titulo": "Arduino Nano (ATmega328P)",
    "forma": "placa",
    "lados": {"izquierda": list(range(16, 31)), "derecha": list(range(15, 0, -1))},
    "cabezales": [("J1", list(range(1, 16))), ("J2", list(range(16, 31)))],
    "conector": ("arriba", "USB"),
    "patas": _patas(
        Pata(1, "D1/TX", None, "D1, PD1, TX (el USB serial: grabacion y monitor)", "prog"),
        Pata(2, "D0/RX", None, "D0, PD0, RX (el USB serial: grabacion y monitor)", "prog"),
        Pata(3, "RESET", None, "RESET, PC6", "reset"),
        Pata(4, "GND", None, "GND", "gnd"),
        Pata(5, "D2", "2", "D2, PD2, INT0", "io"),
        Pata(6, "D3", "3", "D3, PD3, PWM, INT1", "io"),
        Pata(7, "D4", "4", "D4, PD4", "io"),
        Pata(8, "D5", "5", "D5, PD5, PWM", "io"),
        Pata(9, "D6", "6", "D6, PD6, PWM", "io"),
        Pata(10, "D7", "7", "D7, PD7", "io"),
        Pata(11, "D8", "8", "D8, PB0", "io"),
        Pata(12, "D9", "9", "D9, PB1, PWM", "io"),
        Pata(13, "D10", "10", "D10, PB2, SS, PWM", "io"),
        Pata(14, "D11", "11", "D11, PB3, COPI, PWM", "io"),
        Pata(15, "D12", "12", "D12, PB4, CIPO", "io"),
        Pata(16, "D13", "13", "D13, PB5, SCK, LED_BUILTIN", "io"),
        Pata(17, "3V3", None, "3V3: salida de 3.3 V", "vdd"),
        Pata(18, "AREF", None, "AREF: referencia del convertidor analogico", "otro"),
        Pata(19, "A0", "A0", "A0, D14, PC0, ADC0", "io"),
        Pata(20, "A1", "A1", "A1, D15, PC1, ADC1", "io"),
        Pata(21, "A2", "A2", "A2, D16, PC2, ADC2", "io"),
        Pata(22, "A3", "A3", "A3, D17, PC3, ADC3", "io"),
        Pata(23, "A4", "A4", "A4, D18, PC4, ADC4, SDA", "io"),
        Pata(24, "A5", "A5", "A5, D19, PC5, ADC5, SCL", "io"),
        Pata(25, "A6", None, "A6, ADC6 (solo entrada analogica)", "otro"),
        Pata(26, "A7", None, "A7, ADC7 (solo entrada analogica)", "otro"),
        Pata(27, "5V", None, "5V", "vdd"),
        Pata(28, "RESET", None, "RESET, PC6", "reset"),
        Pata(29, "GND", None, "GND", "gnd"),
        Pata(30, "VIN", None, "VIN: entrada de 7 a 12 V", "vdd"),
    ),
    "nota": "Vista superior con el USB arriba.",
}

# Fuente: Arduino, "Arduino Mega 2560 Rev3 full pinout" (A000067-full-pinout.pdf,
# docs.arduino.cc), paginas 1 y 3 ("Digital pins D22-D53"). Girada como la Uno:
# USB a la izquierda, cabezales digital y de comunicacion arriba, alimentacion y
# analogicos abajo, y el cabezal doble a la derecha con los pares (interior)
# y los nones (orilla). Numeracion corrida: arriba 1-26, abajo 27-50 y el
# cabezal doble de 51 a 86 por renglones (interior, orilla).
ARDUINO_MEGA = {
    "titulo": "Arduino Mega 2560 Rev3",
    "forma": "placa",
    "lados": {
        "arriba": list(range(1, 11)) + [None] + list(range(11, 19)) + [None]
                  + list(range(19, 27)),
        "abajo": list(range(27, 35)) + [None] + list(range(35, 43)) + [None]
                 + list(range(43, 51)),
        "doble_derecha": [(n, n + 1) for n in range(51, 87, 2)],
    },
    "cabezales": [("PWM A", list(range(1, 11))), ("PWM B", list(range(11, 19))),
                  ("COMUNICACION", list(range(19, 27))), ("POWER", list(range(27, 35))),
                  ("ANALOG IN A", list(range(35, 43))), ("ANALOG IN B", list(range(43, 51))),
                  ("DOBLE", list(range(51, 87)))],
    "conector": ("izquierda", "USB"),
    "patas": _patas(
        Pata(1, "SCL", None, "SCL (es el mismo pin que D21)", "otro"),
        Pata(2, "SDA", None, "SDA (es el mismo pin que D20)", "otro"),
        Pata(3, "AREF", None, "AREF: referencia del convertidor analogico", "otro"),
        Pata(4, "GND", None, "GND", "gnd"),
        Pata(5, "D13", "13", "D13, PB7, PWM, LED_BUILTIN", "io"),
        Pata(6, "D12", "12", "D12, PB6, PWM", "io"),
        Pata(7, "D11", "11", "D11, PB5, PWM", "io"),
        Pata(8, "D10", "10", "D10, PB4, PWM", "io"),
        Pata(9, "D9", "9", "D9, PH6, PWM", "io"),
        Pata(10, "D8", "8", "D8, PH5, PWM", "io"),
        Pata(11, "D7", "7", "D7, PH4, PWM", "io"),
        Pata(12, "D6", "6", "D6, PH3, PWM", "io"),
        Pata(13, "D5", "5", "D5, PE3, PWM", "io"),
        Pata(14, "D4", "4", "D4, PG5, PWM", "io"),
        Pata(15, "D3", "3", "D3, PE5, PWM, INT5", "io"),
        Pata(16, "D2", "2", "D2, PE4, PWM, INT4", "io"),
        Pata(17, "D1", None, "D1, PE1, TX0 (el USB serial: grabacion y monitor)", "prog"),
        Pata(18, "D0", None, "D0, PE0, RX0 (el USB serial: grabacion y monitor)", "prog"),
        Pata(19, "D14", None, "D14, PJ1, TX3", "io"),
        Pata(20, "D15", None, "D15, PJ0, RX3", "io"),
        Pata(21, "D16", None, "D16, PH1, TX2", "io"),
        Pata(22, "D17", None, "D17, PH0, RX2", "io"),
        Pata(23, "D18", None, "D18, PD3, TX1, INT3", "io"),
        Pata(24, "D19", None, "D19, PD2, RX1, INT2", "io"),
        Pata(25, "D20", None, "D20, PD1, SDA, INT1", "io"),
        Pata(26, "D21", None, "D21, PD0, SCL, INT0", "io"),
        Pata(27, "NC", None, "Sin conexion", "nc"),
        Pata(28, "IOREF", None, "IOREF: voltaje de las I/O (5 V)", "vdd"),
        Pata(29, "RESET", None, "RESET", "reset"),
        Pata(30, "3V3", None, "3V3: salida de 3.3 V", "vdd"),
        Pata(31, "5V", None, "5V: salida de 5 V", "vdd"),
        Pata(32, "GND", None, "GND", "gnd"),
        Pata(33, "GND", None, "GND", "gnd"),
        Pata(34, "VIN", None, "VIN: entrada de 6 a 20 V", "vdd"),
        Pata(35, "A0", None, "A0, D54, PF0, ADC0", "io"),
        Pata(36, "A1", None, "A1, D55, PF1, ADC1", "io"),
        Pata(37, "A2", None, "A2, D56, PF2, ADC2", "io"),
        Pata(38, "A3", None, "A3, D57, PF3, ADC3", "io"),
        Pata(39, "A4", None, "A4, D58, PF4, ADC4, TCK (JTAG)", "io"),
        Pata(40, "A5", None, "A5, D59, PF5, ADC5, TMS (JTAG)", "io"),
        Pata(41, "A6", None, "A6, D60, PF6, ADC6, TDO (JTAG)", "io"),
        Pata(42, "A7", None, "A7, D61, PF7, ADC7, TDI (JTAG)", "io"),
        Pata(43, "A8", None, "A8, D62, PK0, ADC8, PCINT16", "io"),
        Pata(44, "A9", None, "A9, D63, PK1, ADC9, PCINT17", "io"),
        Pata(45, "A10", None, "A10, D64, PK2, ADC10, PCINT18", "io"),
        Pata(46, "A11", None, "A11, D65, PK3, ADC11, PCINT19", "io"),
        Pata(47, "A12", None, "A12, D66, PK4, ADC12, PCINT20", "io"),
        Pata(48, "A13", None, "A13, D67, PK5, ADC13, PCINT21", "io"),
        Pata(49, "A14", None, "A14, D68, PK6, ADC14, PCINT22", "io"),
        Pata(50, "A15", None, "A15, D69, PK7, ADC15, PCINT23", "io"),
        Pata(51, "5V", None, "5V", "vdd"),
        Pata(52, "5V", None, "5V", "vdd"),
        Pata(53, "22", "22", "D22, PA0, AD0", "io"),
        Pata(54, "23", "23", "D23, PA1, AD1", "io"),
        Pata(55, "24", "24", "D24, PA2, AD2", "io"),
        Pata(56, "25", "25", "D25, PA3, AD3", "io"),
        Pata(57, "26", "26", "D26, PA4, AD4", "io"),
        Pata(58, "27", "27", "D27, PA5, AD5", "io"),
        Pata(59, "28", "28", "D28, PA6, AD6", "io"),
        Pata(60, "29", "29", "D29, PA7, AD7", "io"),
        Pata(61, "30", "30", "D30, PC7, A15", "io"),
        Pata(62, "31", "31", "D31, PC6, A14", "io"),
        Pata(63, "32", "32", "D32, PC5, A13", "io"),
        Pata(64, "33", "33", "D33, PC4, A12", "io"),
        Pata(65, "34", "34", "D34, PC3, A11", "io"),
        Pata(66, "35", "35", "D35, PC2, A10", "io"),
        Pata(67, "36", "36", "D36, PC1, A9", "io"),
        Pata(68, "37", "37", "D37, PC0, A8", "io"),
        Pata(69, "38", "38", "D38, PD7, T0", "io"),
        Pata(70, "39", "39", "D39, PG2, ALE", "io"),
        Pata(71, "40", "40", "D40, PG1, RD", "io"),
        Pata(72, "41", "41", "D41, PG0, WR", "io"),
        Pata(73, "42", "42", "D42, PL7", "io"),
        Pata(74, "43", "43", "D43, PL6", "io"),
        Pata(75, "44", "44", "D44, PL5, PWM", "io"),
        Pata(76, "45", "45", "D45, PL4, PWM", "io"),
        Pata(77, "46", "46", "D46, PL3, PWM", "io"),
        Pata(78, "47", "47", "D47, PL2", "io"),
        Pata(79, "48", "48", "D48, PL1", "io"),
        Pata(80, "49", "49", "D49, PL0", "io"),
        Pata(81, "50", "50", "D50, PB3, CIPO", "io"),
        Pata(82, "51", "51", "D51, PB2, COPI", "io"),
        Pata(83, "52", "52", "D52, PB1, SCK", "io"),
        Pata(84, "53", "53", "D53, PB0, SS", "io"),
        Pata(85, "GND", None, "GND", "gnd"),
        Pata(86, "GND", None, "GND", "gnd"),
    ),
    "nota": "Vista superior con el USB a la izquierda. Cabezal doble: pares por "
            "dentro, nones en la orilla.",
}

# ================================================================== ARM

# Fuente del orden de los cabezales: stm32-base.org, "STM32F103C8T6 Blue Pill"
# (Header 1: VB..G, Header 2: 3.3..B12, ambos desde el extremo opuesto al USB).
# Funciones: ST, STM32F103x8/xB Data Sheet (DS5319), tabla "Pin definitions".
# H1-1..20 son las patas 1-20 y H2-1..20 las patas 21-40. Con el USB a la
# izquierda, H2 queda arriba y H1 abajo, ambos leidos de derecha a izquierda.
# El cabezal SWD (patas 41-44) esta en el extremo opuesto al USB.
BLUEPILL = {
    "titulo": "STM32F103C8T6 Blue Pill",
    "forma": "placa",
    "lados": {
        "arriba": list(range(40, 20, -1)),
        "abajo": list(range(20, 0, -1)),
        "derecha": [41, 42, 43, 44],
    },
    "cabezales": [("H1", list(range(1, 21))), ("H2", list(range(21, 41))),
                  ("SWD", [41, 42, 43, 44])],
    "conector": ("izquierda", "USB"),
    "patas": _patas(
        Pata(1, "VB", None, "VBAT: respaldo del reloj de tiempo real", "vdd"),
        Pata(2, "C13", None, "PC13, LED de la placa (solo 3 mA)", "io"),
        Pata(3, "C14", None, "PC14, OSC32_IN (solo 3 mA)", "io"),
        Pata(4, "C15", None, "PC15, OSC32_OUT (solo 3 mA)", "io"),
        Pata(5, "A0", "PA0", "PA0, ADC12_IN0, WKUP, USART2_CTS, TIM2_CH1", "io"),
        Pata(6, "A1", "PA1", "PA1, ADC12_IN1, USART2_RTS, TIM2_CH2", "io"),
        Pata(7, "A2", "PA2", "PA2, ADC12_IN2, USART2_TX, TIM2_CH3", "io"),
        Pata(8, "A3", "PA3", "PA3, ADC12_IN3, USART2_RX, TIM2_CH4", "io"),
        Pata(9, "A4", "PA4", "PA4, ADC12_IN4, SPI1_NSS, USART2_CK", "io"),
        Pata(10, "A5", "PA5", "PA5, ADC12_IN5, SPI1_SCK", "io"),
        Pata(11, "A6", "PA6", "PA6, ADC12_IN6, SPI1_MISO, TIM3_CH1", "io"),
        Pata(12, "A7", "PA7", "PA7, ADC12_IN7, SPI1_MOSI, TIM3_CH2", "io"),
        Pata(13, "B0", "PB0", "PB0, ADC12_IN8, TIM3_CH3", "io"),
        Pata(14, "B1", "PB1", "PB1, ADC12_IN9, TIM3_CH4", "io"),
        Pata(15, "B10", "PB10", "PB10, I2C2_SCL, USART3_TX (tolera 5 V)", "io"),
        Pata(16, "B11", "PB11", "PB11, I2C2_SDA, USART3_RX (tolera 5 V)", "io"),
        Pata(17, "R", None, "NRST: reset", "reset"),
        Pata(18, "3.3", None, "3.3 V", "vdd"),
        Pata(19, "G", None, "GND", "gnd"),
        Pata(20, "G", None, "GND", "gnd"),
        Pata(21, "3.3", None, "3.3 V", "vdd"),
        Pata(22, "G", None, "GND", "gnd"),
        Pata(23, "5V", None, "5 V", "vdd"),
        Pata(24, "B9", "PB9", "PB9, TIM4_CH4 (tolera 5 V)", "io"),
        Pata(25, "B8", "PB8", "PB8, TIM4_CH3 (tolera 5 V)", "io"),
        Pata(26, "B7", "PB7", "PB7, I2C1_SDA, TIM4_CH2 (tolera 5 V)", "io"),
        Pata(27, "B6", "PB6", "PB6, I2C1_SCL, TIM4_CH1 (tolera 5 V)", "io"),
        Pata(28, "B5", "PB5", "PB5, I2C1_SMBA", "io"),
        Pata(29, "B4", None, "PB4, NJTRST (JTAG)", "jtag"),
        Pata(30, "B3", None, "PB3, JTDO (JTAG)", "jtag"),
        Pata(31, "A15", None, "PA15, JTDI (JTAG)", "jtag"),
        Pata(32, "A12", None, "PA12, USBDP", "usb"),
        Pata(33, "A11", None, "PA11, USBDM", "usb"),
        Pata(34, "A10", "PA10", "PA10, USART1_RX, TIM1_CH3 (tolera 5 V)", "io"),
        Pata(35, "A9", "PA9", "PA9, USART1_TX, TIM1_CH2 (tolera 5 V)", "io"),
        Pata(36, "A8", "PA8", "PA8, USART1_CK, TIM1_CH1, MCO (tolera 5 V)", "io"),
        Pata(37, "B15", "PB15", "PB15, SPI2_MOSI, TIM1_CH3N (tolera 5 V)", "io"),
        Pata(38, "B14", "PB14", "PB14, SPI2_MISO, TIM1_CH2N (tolera 5 V)", "io"),
        Pata(39, "B13", "PB13", "PB13, SPI2_SCK, TIM1_CH1N (tolera 5 V)", "io"),
        Pata(40, "B12", "PB12", "PB12, SPI2_NSS, TIM1_BKIN (tolera 5 V)", "io"),
        Pata(41, "3.3", None, "3.3 V del cabezal SWD", "vdd"),
        Pata(42, "DIO", None, "PA13, SWDIO (el ST-Link)", "prog"),
        Pata(43, "CLK", None, "PA14, SWCLK (el ST-Link)", "prog"),
        Pata(44, "G", None, "GND del cabezal SWD", "gnd"),
    ),
    "nota": "Vista superior con el USB a la izquierda. El orden del cabezal SWD "
            "cambia entre clones: confirmelo con la serigrafia.",
}

# Fuente: Raspberry Pi, "Raspberry Pi Pico Datasheet" (RP-008307), seccion
# "Pinout": patas 1-20 a la izquierda de arriba abajo y 21-40 a la derecha de
# abajo arriba, con el USB arriba.
PICO = {
    "titulo": "Raspberry Pi Pico (RP2040)",
    "forma": "placa",
    "lados": {"izquierda": list(range(1, 21)), "derecha": list(range(40, 20, -1))},
    "cabezales": [("", list(range(1, 41)))],
    "conector": ("arriba", "USB"),
    "patas": _patas(
        Pata(1, "GP0", 0, "GP0, UART0 TX, I2C0 SDA, SPI0 RX", "io"),
        Pata(2, "GP1", 1, "GP1, UART0 RX, I2C0 SCL, SPI0 CSn", "io"),
        Pata(3, "GND", None, "GND", "gnd"),
        Pata(4, "GP2", 2, "GP2, I2C1 SDA, SPI0 SCK", "io"),
        Pata(5, "GP3", 3, "GP3, I2C1 SCL, SPI0 TX", "io"),
        Pata(6, "GP4", 4, "GP4, UART1 TX, I2C0 SDA, SPI0 RX", "io"),
        Pata(7, "GP5", 5, "GP5, UART1 RX, I2C0 SCL, SPI0 CSn", "io"),
        Pata(8, "GND", None, "GND", "gnd"),
        Pata(9, "GP6", 6, "GP6, I2C1 SDA, SPI0 SCK", "io"),
        Pata(10, "GP7", 7, "GP7, I2C1 SCL, SPI0 TX", "io"),
        Pata(11, "GP8", 8, "GP8, UART1 TX, I2C0 SDA, SPI1 RX", "io"),
        Pata(12, "GP9", 9, "GP9, UART1 RX, I2C0 SCL, SPI1 CSn", "io"),
        Pata(13, "GND", None, "GND", "gnd"),
        Pata(14, "GP10", 10, "GP10, I2C1 SDA, SPI1 SCK", "io"),
        Pata(15, "GP11", 11, "GP11, I2C1 SCL, SPI1 TX", "io"),
        Pata(16, "GP12", 12, "GP12, UART0 TX, I2C0 SDA, SPI1 RX", "io"),
        Pata(17, "GP13", 13, "GP13, UART0 RX, I2C0 SCL, SPI1 CSn", "io"),
        Pata(18, "GND", None, "GND", "gnd"),
        Pata(19, "GP14", 14, "GP14, I2C1 SDA, SPI1 SCK", "io"),
        Pata(20, "GP15", 15, "GP15, I2C1 SCL, SPI1 TX", "io"),
        Pata(21, "GP16", 16, "GP16, UART0 TX, I2C0 SDA, SPI0 RX", "io"),
        Pata(22, "GP17", 17, "GP17, UART0 RX, I2C0 SCL, SPI0 CSn", "io"),
        Pata(23, "GND", None, "GND", "gnd"),
        Pata(24, "GP18", 18, "GP18, I2C1 SDA, SPI0 SCK", "io"),
        Pata(25, "GP19", 19, "GP19, I2C1 SCL, SPI0 TX", "io"),
        Pata(26, "GP20", 20, "GP20, I2C0 SDA", "io"),
        Pata(27, "GP21", 21, "GP21, I2C0 SCL", "io"),
        Pata(28, "GND", None, "GND", "gnd"),
        Pata(29, "GP22", 22, "GP22", "io"),
        Pata(30, "RUN", None, "RUN: reset en bajo", "reset"),
        Pata(31, "GP26", 26, "GP26, ADC0, I2C1 SDA", "io"),
        Pata(32, "GP27", 27, "GP27, ADC1, I2C1 SCL", "io"),
        Pata(33, "AGND", None, "AGND: tierra del convertidor analogico", "gnd"),
        Pata(34, "GP28", 28, "GP28, ADC2", "io"),
        Pata(35, "VREF", None, "ADC_VREF: referencia del convertidor analogico", "otro"),
        Pata(36, "3V3", None, "3V3(OUT): salida de 3.3 V", "vdd"),
        Pata(37, "3V3_EN", None, "3V3_EN: en bajo apaga el regulador", "otro"),
        Pata(38, "GND", None, "GND", "gnd"),
        Pata(39, "VSYS", None, "VSYS: entrada de 1.8 a 5.5 V", "vdd"),
        Pata(40, "VBUS", None, "VBUS: los 5 V del USB", "vdd"),
    ),
    "nota": "Vista superior con el USB arriba; pata 1 arriba a la izquierda.",
}

# ============================================================== el indice

# Todos los dibujos por nombre. Las llaves que coinciden con placas.py son el
# dibujo principal de esa placa; "nano" es el segundo dibujo de uno_nano.
ENCAPSULADOS = {
    "pic18f4550": PIC18F4550,
    "pic18f45k50": PIC18F45K50,
    "pic16f877a": PIC16F877A,
    "pic16f628a": PIC16F628A,
    "pic16f84a": PIC16F84A,
    "esp32_wroom32": ESP32_DEVKITC,
    "esp32_s3": ESP32_S3_DEVKITC,
    "esp32_c3": ESP32_C3_DEVKITM,
    "uno_nano": ARDUINO_UNO,
    "nano": ARDUINO_NANO,
    "mega2560": ARDUINO_MEGA,
    "bluepill": BLUEPILL,
    "pico": PICO,
    "max2": EPM240,
}

# Que dibujos tiene cada placa de placas.PLACAS_CON_PINES, el primero por
# omision. uno_nano son dos tarjetas distintas con los mismos pines.
DIBUJOS_DE_PLACA = {
    "pic18f4550": ["pic18f4550"],
    "pic18f45k50": ["pic18f45k50"],
    "pic16f877a": ["pic16f877a"],
    "pic16f628a": ["pic16f628a"],
    "pic16f84a": ["pic16f84a"],
    "esp32_wroom32": ["esp32_wroom32"],
    "esp32_s3": ["esp32_s3"],
    "esp32_c3": ["esp32_c3"],
    "uno_nano": ["uno_nano", "nano"],
    "mega2560": ["mega2560"],
    "bluepill": ["bluepill"],
    "pico": ["pico"],
    "max2": ["max2"],
}


# ========================================================= las consultas

def dibujo_de(placa, dibujo=None):
    """El nombre del dibujo que se usa: el pedido o el principal de la placa.
    Existe para que todas las funciones acepten el mismo par (placa, dibujo)."""
    if dibujo is None:
        return DIBUJOS_DE_PLACA[placa][0]
    if dibujo not in DIBUJOS_DE_PLACA[placa]:
        raise ValueError(f"la placa {placa} no tiene el dibujo {dibujo!r}")
    return dibujo


def asignables(placa):
    """Los pines de `placa` que pueden llevar una senal, con lo que hay que saber
    de cada uno, leidos de placas.py para no repetir el catalogo.

    Devuelve {id: {"aviso": texto, "solo_entrada": bool, "solo_para": None,
    "reloj" o "reset", "especial": texto}} en el orden de placas.py: primero
    las entradas, luego las salidas y al final los pines especiales (los GCLK y
    DEV_CLRn/DEV_OE de la MAX II, que solo admiten reloj o reset).
    """
    info = placas.PLACAS_CON_PINES[placa]
    reserva = info.get("reserva", {})
    solo_entrada = info.get("solo_entrada", [])
    resultado = {}
    for pin in list(info["entradas"]) + list(info["salidas"]):
        if pin not in resultado:
            resultado[pin] = {"aviso": reserva.get(pin, ""),
                              "solo_entrada": pin in solo_entrada,
                              "solo_para": None, "especial": ""}
    principal = ENCAPSULADOS[DIBUJOS_DE_PLACA[placa][0]]
    for pin, texto in info.get("pines_especiales", {}).items():
        pata = _buscar_pata(principal, pin)
        # el tipo de la pata en el dibujo dice para que se reservo: GCLK -> reloj
        solo_para = pata.tipo if pata is not None and pata.tipo in ("reloj", "reset") else "reloj"
        resultado[pin] = {"aviso": f"es {texto}", "solo_entrada": False,
                          "solo_para": solo_para, "especial": texto}
    return resultado


def _buscar_pata(encapsulado, pin_id):
    """La Pata de un dibujo con ese id, o None. Recorre en orden de numero."""
    for numero in sorted(encapsulado["patas"]):
        pata = encapsulado["patas"][numero]
        if pata.id is not None and pata.id == pin_id:
            return pata
    return None


def pata_de(placa, pin_id, dibujo=None):
    """La Pata donde esta el pin `pin_id` de placas.py, para decir en que numero
    de pata o de cabezal hay que conectar una senal."""
    return _buscar_pata(ENCAPSULADOS[dibujo_de(placa, dibujo)], pin_id)


def posicion(nombre_dibujo, numero):
    """'J3-5', 'pata 24' o 'POWER-3': como se busca la pata en la placa real.
    En los chips es el numero de pata; en las tarjetas, el cabezal y el lugar."""
    encapsulado = ENCAPSULADOS[nombre_dibujo]
    for nombre, numeros in encapsulado.get("cabezales", []):
        if numero in numeros and nombre:
            return f"{nombre}-{numeros.index(numero) + 1}"
    return f"pata {numero}"


def puede_ir(placa, pin_id, direccion):
    """Si una senal con `direccion` ("entrada", "salida", "reloj", "reset")
    puede ir en el pin `pin_id`. Devuelve (si/no, texto para la barra de estado).

    Las reglas son las mismas que aplica modelo.con_pines, y aqui se escriben
    una sola vez para que la ventana y las pruebas no las repitan: un pin fuera
    del catalogo no se usa, una salida no va en un pin que solo es entrada, y un
    pin especial (GCLK, DEV_CLRn) solo admite la senal para la que se reservo.
    El reloj y el reset son entradas para todo lo demas.
    """
    lista = asignables(placa)
    titulo = placas.PLACAS_CON_PINES[placa]["titulo"]
    if pin_id not in lista:
        return False, f"El pin {pin_id} no es utilizable en {titulo}."
    datos = lista[pin_id]
    if datos["solo_para"] is not None and direccion != datos["solo_para"]:
        return False, (f"El pin {pin_id} es {datos['especial']}: solo admite una "
                       f"senal de {datos['solo_para']}.")
    if datos["solo_entrada"] and direccion == "salida":
        return False, f"El pin {pin_id} de {titulo} solo sirve de entrada."
    return True, datos["aviso"]


# ============================================================ la geometria

# Separacion entre patas, en pixeles, segun la forma
PASO = {"dip": 20, "qfp": 16, "placa": 18}
LARGO_PATA = 12          # lo que sale la pata del cuerpo en dip y qfp
ANCHO_LETRA = 6.6        # ancho medio de un caracter de 11 px, para medir textos
ANCHO_NUMERO = 22        # lo que ocupa el numero de pata (hasta 3 cifras)
ANCHO_SENAL = 96         # lo que se deja afuera para el nombre de la senal
ALTO_TITULO = 30         # la franja de arriba con el titulo
LETRA = {"etiqueta": 11, "numero": 9, "senal": 11, "titulo": 13, "cuerpo": 12}

LADOS_SENCILLOS = ("izquierda", "derecha", "arriba", "abajo")


def _ancho_texto(texto, tamano=11):
    """Ancho aproximado de un texto en Segoe UI, para reservar su lugar."""
    return len(texto) * ANCHO_LETRA * tamano / 11.0


def _interior(encapsulado, lado):
    """Lo que entra del cuerpo la etiqueta mas larga de un lado."""
    numeros = [n for n in encapsulado["lados"].get(lado, []) if n is not None]
    if not numeros:
        return 0
    return 10 + max(_ancho_texto(encapsulado["patas"][n].etiqueta) for n in numeros)


def geometria(nombre_dibujo):
    """Las coordenadas de todo el dibujo, en pixeles a escala 1.

    La comparten el SVG del documento y el Canvas de la ventana, asi los dos
    dibujan lo mismo. Devuelve {"ancho", "alto", "forma", "cuerpo": (x0, y0,
    x1, y1), "patas": {numero: lugar}} donde cada lugar es:
        lado      el lado del dibujo
        pata      (x0, y0, x1, y1) de la pata (raya en chips, cuadro en placas)
        zona      (x0, y0, x1, y1) donde responde al clic
        etiqueta  (x, y, ancla, vertical) del nombre de la pata
        numero    (x, y, ancla, vertical) del numero (None en las placas)
        senal     (x, y, ancla, vertical) del nombre de la senal asignada
    El ancla es "inicio" (el texto empieza en x, y) o "fin" (termina ahi). Un
    texto vertical se lee de abajo hacia arriba.
    """
    enc = ENCAPSULADOS[nombre_dibujo]
    forma = enc["forma"]
    paso = PASO[forma]
    lados = enc["lados"]
    largo = {lado: len(lados.get(lado, [])) for lado in LADOS_SENCILLOS}
    dentro = {lado: _interior(enc, lado) for lado in LADOS_SENCILLOS}

    if forma == "dip":
        cuerpo_ancho = dentro["izquierda"] + dentro["derecha"] + 34
        cuerpo_alto = largo["izquierda"] * paso + paso
    elif forma == "qfp":
        esquina = max(dentro.values()) + 8
        cuerpo_ancho = cuerpo_alto = largo["izquierda"] * paso + 2 * esquina
    else:
        doble = lados.get("doble_derecha", [])
        ancho_doble = (2 * paso + 150) if doble else 0
        horizontal = max(largo["arriba"], largo["abajo"])
        vertical = max(largo["izquierda"], largo["derecha"])
        cuerpo_ancho = max(horizontal * paso + 2 * paso + ancho_doble
                           + dentro["izquierda"] + dentro["derecha"],
                           dentro["izquierda"] + dentro["derecha"] + 190)
        cuerpo_alto = max(vertical * paso + 2 * paso,
                          dentro["arriba"] + dentro["abajo"] + 90)
        if doble:
            cuerpo_alto = max(cuerpo_alto,
                              len(doble) * paso + dentro["arriba"] + dentro["abajo"] + 30)

    # lo que sobra afuera del cuerpo en cada lado
    afuera_pata = LARGO_PATA + ANCHO_NUMERO if forma in ("dip", "qfp") else 4
    afuera = {}
    for lado in LADOS_SENCILLOS:
        afuera[lado] = (afuera_pata + ANCHO_SENAL) if largo[lado] else 24
    if forma == "placa" and lados.get("doble_derecha"):
        afuera["derecha"] = 30 + ANCHO_SENAL
    x0 = afuera["izquierda"]
    y0 = ALTO_TITULO + afuera["arriba"]
    x1 = x0 + cuerpo_ancho
    y1 = y0 + cuerpo_alto
    ancho_total = x1 + afuera["derecha"]
    alto_total = y1 + afuera["abajo"] + 22     # la nota va abajo

    patas = {}
    for lado in LADOS_SENCILLOS:
        lista = lados.get(lado, [])
        if not lista:
            continue
        if lado in ("izquierda", "derecha"):
            desde, disponible = 0, cuerpo_alto
        elif forma == "placa":
            # en una tarjeta, los cabezales de arriba y abajo dejan libre lo
            # que ocupan las etiquetas de los lados y el cabezal doble
            desde = dentro["izquierda"]
            disponible = (cuerpo_ancho - dentro["izquierda"] - dentro["derecha"]
                          - (2 * paso + 150 if lados.get("doble_derecha") else 0))
        else:
            desde, disponible = 0, cuerpo_ancho
        inicio = desde + (disponible - len(lista) * paso) / 2.0 + paso / 2.0
        for k, numero in enumerate(lista):
            if numero is None:
                continue
            centro = inicio + k * paso
            if lado in ("izquierda", "derecha"):
                patas[numero] = _lugar_vertical(forma, lado, x0, x1, y0 + centro, paso,
                                                dentro[lado])
            else:
                patas[numero] = _lugar_horizontal(forma, lado, y0, y1, x0 + centro, paso,
                                                  dentro[lado])

    doble = lados.get("doble_derecha", [])
    if doble:
        arriba_libre = y0 + dentro["arriba"] + 15
        abajo_libre = y1 - dentro["abajo"] - 15
        inicio = arriba_libre + (abajo_libre - arriba_libre - len(doble) * paso) / 2.0 + paso / 2.0
        for k, (interior, orilla) in enumerate(doble):
            y = inicio + k * paso
            patas[interior] = _lugar_doble(x1, y, paso, por_dentro=True)
            patas[orilla] = _lugar_doble(x1, y, paso, por_dentro=False)

    return {"ancho": ancho_total, "alto": alto_total, "forma": forma,
            "cuerpo": (x0, y0, x1, y1), "patas": patas}


def _lugar_vertical(forma, lado, x0, x1, y, paso, interior):
    """Una pata en el lado izquierdo o derecho (las patas corren en vertical)."""
    medio = paso / 2.0 - 1
    if lado == "izquierda":
        orilla, hacia = x0, -1
    else:
        orilla, hacia = x1, 1
    ancla_fuera = "fin" if hacia < 0 else "inicio"
    ancla_dentro = "inicio" if hacia < 0 else "fin"
    if forma in ("dip", "qfp"):
        punta = orilla + hacia * LARGO_PATA
        pata = (min(orilla, punta), y - 2.5, max(orilla, punta), y + 2.5)
        numero = (punta + hacia * 3, y, ancla_fuera, False)
        senal = (punta + hacia * (3 + ANCHO_NUMERO), y, ancla_fuera, False)
        etiqueta = (orilla - hacia * 5, y, ancla_dentro, False)
        lejos = punta + hacia * (3 + ANCHO_NUMERO)
    else:
        centro = orilla - hacia * 9
        pata = (centro - 5, y - 5, centro + 5, y + 5)
        numero = None
        senal = (orilla + hacia * 5, y, ancla_fuera, False)
        etiqueta = (orilla - hacia * 18, y, ancla_dentro, False)
        lejos = orilla + hacia * 4
    adentro = orilla - hacia * (interior + 10)
    zona = (min(lejos, adentro), y - medio, max(lejos, adentro), y + medio)
    return {"lado": lado, "pata": pata, "zona": zona, "etiqueta": etiqueta,
            "numero": numero, "senal": senal}


def _lugar_horizontal(forma, lado, y0, y1, x, paso, interior):
    """Una pata en el lado de arriba o de abajo (los textos van en vertical)."""
    medio = paso / 2.0 - 1
    if lado == "arriba":
        orilla, hacia = y0, -1
    else:
        orilla, hacia = y1, 1
    # vertical se lee hacia arriba: "inicio" crece hacia arriba, "fin" hacia abajo
    ancla_fuera = "inicio" if hacia < 0 else "fin"
    ancla_dentro = "fin" if hacia < 0 else "inicio"
    if forma in ("dip", "qfp"):
        punta = orilla + hacia * LARGO_PATA
        pata = (x - 2.5, min(orilla, punta), x + 2.5, max(orilla, punta))
        numero = (x, punta + hacia * 3, ancla_fuera, True)
        senal = (x, punta + hacia * (3 + ANCHO_NUMERO), ancla_fuera, True)
        etiqueta = (x, orilla - hacia * 5, ancla_dentro, True)
        lejos = punta + hacia * (3 + ANCHO_NUMERO)
    else:
        centro = orilla - hacia * 9
        pata = (x - 5, centro - 5, x + 5, centro + 5)
        numero = None
        senal = (x, orilla + hacia * 5, ancla_fuera, True)
        etiqueta = (x, orilla - hacia * 18, ancla_dentro, True)
        lejos = orilla + hacia * 4
    adentro = orilla - hacia * (interior + 10)
    zona = (x - medio, min(lejos, adentro), x + medio, max(lejos, adentro))
    return {"lado": lado, "pata": pata, "zona": zona, "etiqueta": etiqueta,
            "numero": numero, "senal": senal}


def _lugar_doble(x1, y, paso, por_dentro):
    """Una pata del cabezal doble del Mega: la columna interior escribe hacia
    adentro de la placa y la de la orilla hacia afuera."""
    medio = paso / 2.0 - 1
    if por_dentro:
        centro = x1 - 9 - paso
        pata = (centro - 5, y - 5, centro + 5, y + 5)
        etiqueta = (centro - 9, y, "fin", False)
        senal = (centro - 36, y, "fin", False)
        zona = (centro - 36, y - medio, centro + 5, y + medio)
        return {"lado": "doble_interior", "pata": pata, "zona": zona,
                "etiqueta": etiqueta, "numero": None, "senal": senal}
    centro = x1 - 9
    pata = (centro - 5, y - 5, centro + 5, y + 5)
    etiqueta = (x1 + 5, y, "inicio", False)
    senal = (x1 + 30, y, "inicio", False)
    zona = (centro - 5, y - medio, x1 + 30, y + medio)
    return {"lado": "doble_orilla", "pata": pata, "zona": zona,
            "etiqueta": etiqueta, "numero": None, "senal": senal}


def marca_de_orientacion(nombre_dibujo, geo):
    """La muesca del DIP, el punto de la pata 1 del QFP o el conector USB de la
    tarjeta: (tipo, coordenadas, texto). Lo dibujan igual el SVG y la ventana."""
    enc = ENCAPSULADOS[nombre_dibujo]
    x0, y0, x1, y1 = geo["cuerpo"]
    if enc["forma"] == "dip":
        centro = (x0 + x1) / 2.0
        return ("muesca", (centro - 9, y0 - 9, centro + 9, y0 + 9), "")
    if enc["forma"] == "qfp":
        return ("punto", (x0 + 8, y0 + 8, x0 + 16, y0 + 16), "")
    lado, texto = enc.get("conector", ("", ""))
    if lado == "izquierda":
        medio = (y0 + y1) / 2.0
        return ("conector", (x0 - 12, medio - 16, x0 + 26, medio + 16), texto)
    if lado == "arriba":
        medio = (x0 + x1) / 2.0
        return ("conector", (medio - 16, y0 - 12, medio + 16, y0 + 26), texto)
    if lado == "abajo":
        medio = (x0 + x1) / 2.0
        return ("conector", (medio - 16, y1 - 26, medio + 16, y1 + 12), texto)
    return ("", (0, 0, 0, 0), "")


# ================================================================== el SVG

# Tonos para imprimir: negro, grises y nada de color
SVG_TINTA = "#000"
SVG_GRIS = "#8a8a8a"
SVG_CUERPO = "#ffffff"
SVG_PLACA = "#f2f2f2"


def _svg_texto(texto, x, y, ancla, vertical, tamano, color=SVG_TINTA, negrita=False):
    """Un <text> con el ancla y el giro de la geometria."""
    alinear = "start" if ancla == "inicio" else ("end" if ancla == "fin" else "middle")
    peso = " font-weight='bold'" if negrita else ""
    giro = f" transform='rotate(-90 {x:.1f} {y:.1f})'" if vertical else ""
    return (f"<text x='{x:.1f}' y='{y:.1f}' font-size='{tamano}' fill='{color}' "
            f"text-anchor='{alinear}' dominant-baseline='central'{peso}{giro}>"
            f"{escape(str(texto))}</text>")


def svg(placa, asignacion, titulo=None, dibujo=None):
    """El componente dibujado para el documento HTML, con cada senal junto a su
    pata. `asignacion` es {id del pin: nombre de la senal}.

    Sale en negro y grises para imprimir: las patas que llevan senal van
    rellenas y con el nombre en negritas; las que no se pueden usar (VDD, GND,
    JTAG...) en gris.
    """
    nombre = dibujo_de(placa, dibujo)
    enc = ENCAPSULADOS[nombre]
    geo = geometria(nombre)
    renglones_nota = partir_texto(enc["nota"], int((geo["ancho"] - 16) / 5.2))
    ancho, alto = geo["ancho"], geo["alto"] + 12 * (len(renglones_nota) - 1)
    x0, y0, x1, y1 = geo["cuerpo"]
    usables = asignables(placa)
    partes = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{ancho:.0f}' height='{alto:.0f}' "
        f"viewBox='0 0 {ancho:.0f} {alto:.0f}' "
        "style='max-width:100%;height:auto' "
        "font-family='Segoe UI, Arial, sans-serif'>",
        f"<rect x='0' y='0' width='{ancho:.0f}' height='{alto:.0f}' fill='#fff'/>",
        _svg_texto(titulo or enc["titulo"], ancho / 2.0, ALTO_TITULO / 2.0, "medio", False,
                   LETRA["titulo"], negrita=True),
    ]
    fondo = SVG_PLACA if enc["forma"] == "placa" else SVG_CUERPO
    esquina = 8 if enc["forma"] == "placa" else 2
    partes.append(f"<rect x='{x0:.1f}' y='{y0:.1f}' width='{x1 - x0:.1f}' "
                  f"height='{y1 - y0:.1f}' rx='{esquina}' fill='{fondo}' "
                  f"stroke='{SVG_TINTA}' stroke-width='1.2'/>")
    tipo, (a, b, c, d), texto = marca_de_orientacion(nombre, geo)
    if tipo == "muesca":
        partes.append(f"<path d='M {a:.1f} {y0:.1f} A 9 9 0 0 0 {c:.1f} {y0:.1f}' "
                      f"fill='none' stroke='{SVG_TINTA}'/>")
    elif tipo == "punto":
        partes.append(f"<circle cx='{(a + c) / 2:.1f}' cy='{(b + d) / 2:.1f}' r='3' "
                      f"fill='{SVG_TINTA}'/>")
    elif tipo == "conector":
        partes.append(f"<rect x='{a:.1f}' y='{b:.1f}' width='{c - a:.1f}' height='{d - b:.1f}' "
                      f"fill='#ddd' stroke='{SVG_TINTA}'/>")
        partes.append(_svg_texto(texto, (a + c) / 2, (b + d) / 2, "medio", False, 9))
    # el nombre del chip en medio del cuerpo, como va impreso
    vertical = enc["forma"] == "dip"
    partes.append(_svg_texto(enc["titulo"].split(" (")[0], (x0 + x1) / 2, (y0 + y1) / 2,
                             "medio", vertical, LETRA["cuerpo"], color=SVG_GRIS))

    for numero in sorted(geo["patas"]):
        lugar = geo["patas"][numero]
        pata = enc["patas"][numero]
        senal = asignacion.get(pata.id) if pata.id is not None else None
        usable = pata.id is not None and pata.id in usables
        a, b, c, d = lugar["pata"]
        if senal:
            relleno, trazo = SVG_TINTA, SVG_TINTA
        elif usable:
            relleno, trazo = "#fff", SVG_TINTA
        else:
            relleno, trazo = "#d6d6d6", SVG_GRIS
        partes.append(f"<rect x='{a:.1f}' y='{b:.1f}' width='{c - a:.1f}' height='{d - b:.1f}' "
                      f"fill='{relleno}' stroke='{trazo}' stroke-width='0.8'/>")
        color = SVG_TINTA if usable else SVG_GRIS
        x, y, ancla, vert = lugar["etiqueta"]
        partes.append(_svg_texto(pata.etiqueta, x, y, ancla, vert, LETRA["etiqueta"], color))
        if lugar["numero"] is not None:
            x, y, ancla, vert = lugar["numero"]
            partes.append(_svg_texto(numero, x, y, ancla, vert, LETRA["numero"], SVG_GRIS))
        if senal:
            x, y, ancla, vert = lugar["senal"]
            partes.append(_svg_texto(senal, x, y, ancla, vert, LETRA["senal"], negrita=True))
    for k, renglon in enumerate(renglones_nota):
        y = geo["alto"] - 10 + 12 * k
        partes.append(_svg_texto(renglon, 8, y, "inicio", False, 9, SVG_GRIS))
    partes.append("</svg>")
    return "\n".join(partes)


def partir_texto(texto, caracteres):
    """Parte un texto en renglones de a lo mas `caracteres`, sin cortar
    palabras. La nota del dibujo no cabe en un renglon en los DIP angostos."""
    renglones, actual = [], ""
    for palabra in texto.split():
        if actual and len(actual) + 1 + len(palabra) > caracteres:
            renglones.append(actual)
            actual = palabra
        else:
            actual = (actual + " " + palabra).strip()
    if actual:
        renglones.append(actual)
    return renglones or [""]
