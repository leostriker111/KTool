"""Catalogo de placas: que pines se pueden usar, en que orden y con que cuidado.

Igual que el catalogo de chips del protoboard, aqui solo hay DATOS. Un pin mal
elegido no da error de compilacion: da una placa que no arranca (un pin de
*strapping* amarrado al reves), una salida que no prende (RA4 es de drenador
abierto) o un programador que ya no conecta (PGC/PGD ocupados). Por eso cada
placa trae la lista ordenada de pines y, aparte, los pines que solo se usan si
no queda de otra, cada uno con el aviso que se escribe junto a el.

Cada lista se arma asi:
  entradas   pines preferidos para las entradas, en orden.
  salidas    pines preferidos para las salidas, en orden. Puede repetir pines de
             `entradas`: el que ya tomo una entrada se salta.
  reserva    pin -> aviso. Pines que estan en alguna lista pero al final, porque
             estorban a algo (programacion, arranque, USB). Si se usan, el aviso
             queda escrito en la tabla de pines del archivo generado.
  solo_entrada  pines que no pueden ser salida (ni de reserva).

Los numeros fisicos de las patas (`pata`) son del encapsulado DIP para los PIC y
de la serigrafia de la placa para las demas.
"""

from __future__ import annotations

# ------------------------------------------------------------------ PIC

# Los tres PIC de 40 patas (18F4550, 18F45K50 y 16F877A) comparten el mismo
# acomodo de patas. Se lee de la figura "40-Pin PDIP" de cada hoja de datos.
PATAS_PIC_40 = {
    "RA0": 2, "RA1": 3, "RA2": 4, "RA3": 5, "RA4": 6, "RA5": 7,
    "RE0": 8, "RE1": 9, "RE2": 10,
    "RC0": 15, "RC1": 16, "RC2": 17, "RC3": 18, "RC4": 23, "RC5": 24, "RC6": 25, "RC7": 26,
    "RD0": 19, "RD1": 20, "RD2": 21, "RD3": 22, "RD4": 27, "RD5": 28, "RD6": 29, "RD7": 30,
    "RB0": 33, "RB1": 34, "RB2": 35, "RB3": 36, "RB4": 37, "RB5": 38, "RB6": 39, "RB7": 40,
}

# 16F628A y 16F84A: 18 patas, mismo acomodo en PORTB y en RA0-RA4.
PATAS_PIC_18 = {
    "RA2": 1, "RA3": 2, "RA4": 3, "RA5": 4,
    "RB0": 6, "RB1": 7, "RB2": 8, "RB3": 9, "RB4": 10, "RB5": 11, "RB6": 12, "RB7": 13,
    "RA6": 15, "RA7": 16, "RA0": 17, "RA1": 18,
}

_SALIDAS_PIC_40 = ["RD0", "RD1", "RD2", "RD3", "RD4", "RD5", "RD6", "RD7",
                   "RA0", "RA1", "RA2", "RA3", "RA5", "RE0", "RE1", "RE2",
                   "RC0", "RC1", "RC2", "RC6", "RC7"]

PIC = {
    "pic18f4550": {
        "titulo": "PIC18F4550",
        "familia": 18,
        "patas": PATAS_PIC_40,
        # RB6/RB7 son PGC/PGD (el PICkit); RB0-RB5 quedan libres para entradas.
        "entradas": ["RB0", "RB1", "RB2", "RB3", "RB4", "RB5"],
        # RA4 se evita (en varios PIC es de drenador abierto) y RC4/RC5 son las
        # lineas del USB: en el 4550 solo sirven de entrada.
        "salidas": _SALIDAS_PIC_40,
        "reserva": {},
        "solo_entrada": ["RC4", "RC5"],
        "reloj": "oscilador interno a 8 MHz (no hace falta cristal)",
        "xtal": 8000000,
        "palabras": 16384,   # 32 KB de flash, instrucciones de 2 bytes
    },
    "pic18f45k50": {
        "titulo": "PIC18F45K50",
        "familia": 18,
        "patas": PATAS_PIC_40,
        "entradas": ["RB0", "RB1", "RB2", "RB3", "RB4", "RB5"],
        "salidas": _SALIDAS_PIC_40,
        "reserva": {},
        "solo_entrada": ["RC4", "RC5"],
        "reloj": "oscilador interno a 16 MHz (no hace falta cristal)",
        "xtal": 16000000,
        "palabras": 16384,
    },
    "pic16f877a": {
        "titulo": "PIC16F877A",
        "familia": 16,
        "patas": PATAS_PIC_40,
        "entradas": ["RB0", "RB1", "RB2", "RB3", "RB4", "RB5"],
        # El 877A no tiene USB: RC3-RC5 tambien sirven. RA4 es de drenador abierto.
        "salidas": ["RD0", "RD1", "RD2", "RD3", "RD4", "RD5", "RD6", "RD7",
                    "RC0", "RC1", "RC2", "RC3", "RC4", "RC5", "RC6", "RC7",
                    "RA0", "RA1", "RA2", "RA3", "RA5", "RE0", "RE1", "RE2"],
        "reserva": {},
        "solo_entrada": [],
        "reloj": "cristal de 20 MHz en OSC1/OSC2 (patas 13 y 14) con dos "
                 "capacitores de 22 pF a GND: el 877A no tiene oscilador interno",
        "xtal": 20000000,
        "palabras": 8192,
    },
    "pic16f628a": {
        "titulo": "PIC16F628A",
        "familia": 16,
        "patas": PATAS_PIC_18,
        # RA5 es MCLR (solo entrada) y RA4 es de drenador abierto: como entrada
        # sirve bien. RA6/RA7 quedan libres porque se usa el oscilador interno.
        "entradas": ["RA0", "RA1", "RA2", "RA3", "RA6", "RA7", "RA4"],
        "salidas": ["RB0", "RB1", "RB2", "RB3", "RB4", "RB5", "RB6", "RB7"],
        "reserva": {
            "RB6": "comparte la pata con PGC del PICkit: desconectalo para probar",
            "RB7": "comparte la pata con PGD del PICkit: desconectalo para probar",
        },
        "solo_entrada": ["RA5"],
        "reloj": "oscilador interno a 4 MHz (no hace falta cristal)",
        "xtal": 4000000,
        "palabras": 2048,
    },
    "pic16f84a": {
        "titulo": "PIC16F84A",
        "familia": 16,
        "patas": PATAS_PIC_18,
        # Solo tiene RA0-RA4 y RB0-RB7. RA4 de drenador abierto va de entrada.
        "entradas": ["RA0", "RA1", "RA2", "RA3", "RA4", "RB7"],
        "salidas": ["RB0", "RB1", "RB2", "RB3", "RB4", "RB5", "RB6", "RB7"],
        "reserva": {
            "RB6": "comparte la pata con PGC del PICkit: desconectalo para probar",
            "RB7": "comparte la pata con PGD del PICkit: desconectalo para probar",
        },
        "solo_entrada": [],
        "reloj": "cristal de 4 MHz en OSC1/OSC2 (patas 16 y 15) con dos "
                 "capacitores de 22 pF a GND: el 84A no tiene oscilador interno",
        "xtal": 4000000,
        "palabras": 1024,
    },
}

# ------------------------------------------------------------- ESP32

ESP32 = {
    "esp32_wroom32": {
        "titulo": "ESP32-WROOM-32 (DevKit de 38 pines)",
        # GPIO6-11 van a la memoria flash: no aparecen en ninguna lista.
        "entradas": [32, 33, 25, 26, 27, 14, 34, 35, 36, 39],
        "salidas": [13, 23, 22, 21, 19, 18, 17, 16, 4,
                    32, 33, 25, 26, 27, 14, 5, 2, 15, 12, 0],
        "reserva": {
            34: "solo entrada y sin resistencias internas: pon 10 kOhm a GND",
            35: "solo entrada y sin resistencias internas: pon 10 kOhm a GND",
            36: "solo entrada (VP) y sin resistencias internas: pon 10 kOhm a GND",
            39: "solo entrada (VN) y sin resistencias internas: pon 10 kOhm a GND",
            5: "pin de strapping (tiempos de SDIO): no lo fuerces a bajo al arrancar",
            2: "pin de strapping y LED de la placa: debe quedar en bajo o al aire "
               "para poder grabar",
            15: "pin de strapping (mensajes de arranque): no lo fuerces al arrancar",
            12: "pin de strapping (voltaje de la flash): si arranca en alto, la "
                "placa no inicia",
            0: "pin de strapping (boton BOOT): si arranca en bajo, entra a modo "
               "de grabacion",
        },
        "solo_entrada": [34, 35, 36, 39],
        "sin_pulldown": [34, 35, 36, 39],
    },
    "esp32_s3": {
        "titulo": "ESP32-S3 (DevKitC-1)",
        # 19/20 son el USB, 43/44 el UART0, 26-32 la flash y 35-37 la PSRAM
        # octal de los modulos R8: ninguno entra.
        "entradas": [4, 5, 6, 7, 15, 16],
        "salidas": [17, 18, 8, 9, 10, 11, 12, 13, 14, 1, 2, 21, 47,
                    4, 5, 6, 7, 15, 16, 39, 40, 41, 42, 38, 48],
        "reserva": {
            39: "es MTCK del JTAG: deja de servir para depurar por JTAG",
            40: "es MTDO del JTAG: deja de servir para depurar por JTAG",
            41: "es MTDI del JTAG: deja de servir para depurar por JTAG",
            42: "es MTMS del JTAG: deja de servir para depurar por JTAG",
            38: "en la DevKitC-1 v1.1 lleva el LED RGB",
            48: "en la DevKitC-1 v1.0 lleva el LED RGB",
        },
        "solo_entrada": [],
        "sin_pulldown": [],
    },
    "esp32_c3": {
        "titulo": "ESP32-C3 (DevKitM-1 / SuperMini)",
        # 18/19 son el USB (grabar y monitor): nunca. 12-17 son la flash.
        "entradas": [0, 1, 3, 4, 5, 6],
        "salidas": [7, 10, 0, 1, 3, 4, 5, 6, 20, 21, 2, 8, 9],
        "reserva": {
            20: "es RX del UART0: sin Serial por esos pines",
            21: "es TX del UART0: sin Serial por esos pines",
            2: "pin de strapping: debe arrancar en alto",
            8: "pin de strapping (y LED en varias placas): debe arrancar en alto",
            9: "pin de strapping (boton BOOT): si arranca en bajo, entra a modo "
               "de grabacion",
            4: "es MTMS del JTAG: deja de servir para depurar por JTAG",
            5: "es MTDI del JTAG: deja de servir para depurar por JTAG",
            6: "es MTCK del JTAG: deja de servir para depurar por JTAG",
            7: "es MTDO del JTAG: deja de servir para depurar por JTAG",
        },
        "solo_entrada": [],
        "sin_pulldown": [],
    },
}

# ----------------------------------------------- Arduino y ARM baratos

# En la serigrafia los analogicos se llaman A0-A5 y en el codigo tambien.
ARDUINO = {
    "uno_nano": {
        "titulo": "Arduino Uno / Nano (ATmega328P)",
        # D0/D1 son el Serial (el USB): fuera. A6/A7 del Nano son solo analogicos.
        "entradas": ["2", "3", "4", "5", "6", "7"],
        "salidas": ["8", "9", "10", "11", "12", "13", "A0", "A1", "A2", "A3", "A4", "A5",
                    "2", "3", "4", "5", "6", "7"],
        "reserva": {},
        "solo_entrada": [],
    },
    "mega2560": {
        "titulo": "Arduino Mega 2560",
        "entradas": ["22", "24", "26", "28", "30", "32"],
        "salidas": [str(n) for n in range(23, 54, 2)] +           # 23..53 impares
                   [str(n) for n in range(34, 54, 2)] +           # 34..52 pares
                   ["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"] +
                   ["22", "24", "26", "28", "30", "32"],
        "reserva": {},
        "solo_entrada": [],
    },
}

BLUEPILL = {
    "titulo": "STM32F103C8T6 Blue Pill (STM32duino)",
    # Las entradas van en pines tolerantes a 5 V (FT): asi un 1 de 5 V de otro
    # circuito no la dana. PA11/PA12 son el USB, PA13/PA14 el SWD (el ST-Link),
    # PA15/PB3/PB4 el JTAG, PB2 es BOOT1: ninguno entra. PC13/14/15 solo dan
    # 3 mA y PC13 lleva el LED: fuera tambien.
    "entradas": ["PB12", "PB13", "PB14", "PB15", "PB8", "PB9"],
    # PA0-PA7, PB0, PB1 y PB5 NO son tolerantes a 5 V: por eso van de salida.
    "salidas": ["PA0", "PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7",
                "PB0", "PB1", "PB5", "PB10", "PB11", "PB6", "PB7", "PA8",
                "PB12", "PB13", "PB14", "PB15", "PB8", "PB9", "PA9", "PA10"],
    "reserva": {
        "PA9": "es TX del USART1 (la grabacion por serial): desconecta el "
               "adaptador para probar",
        "PA10": "es RX del USART1 (la grabacion por serial): desconecta el "
                "adaptador para probar",
    },
    "solo_entrada": [],
    "tolerantes_5v": ["PA8", "PA9", "PA10", "PB6", "PB7", "PB8", "PB9", "PB10",
                      "PB11", "PB12", "PB13", "PB14", "PB15"],
}

PICO = {
    "titulo": "Raspberry Pi Pico (RP2040)",
    # GP23-25 y GP29 son internos (regulador, VBUS, LED, VSYS): no salen.
    "entradas": [2, 3, 4, 5, 6, 7],
    "salidas": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
                26, 27, 28, 0, 1, 2, 3, 4, 5, 6, 7],
    "reserva": {},
    "solo_entrada": [],
}

# ------------------------------------------------------- logica programable

# MAX II EPM240T100C5. Tabla "Pin Information for the MAX II EPM240/EPM240G
# Devices", version 1.4 (PT-EPM240-1.4), de Intel/Altera:
#   https://docs.altera.com/v/u/docs/656983 (epm240.pdf)
# Son las 74 patas que la tabla marca como IO a secas. Las otras 6 de usuario
# (GCLK0-3 en 12/14/62/64, DEV_OE en 43, DEV_CLRn en 44) tambien son I/O, pero
# se dejan libres para los relojes y el reset de los disenos secuenciales.
# VCCIO, GNDIO, VCCINT, GNDINT y JTAG (22-25) no aparecen.
EPM240_BANCO_1 = [2, 3, 4, 5, 6, 7, 8, 15, 16, 17, 18, 19, 20, 21, 26, 27, 28, 29, 30,
                  33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 47, 48, 49, 50, 51]
EPM240_BANCO_2 = [1, 52, 53, 54, 55, 56, 57, 58, 61, 66, 67, 68, 69, 70, 71, 72, 73,
                  74, 75, 76, 77, 78, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92,
                  95, 96, 97, 98, 99, 100]

EPM240 = {
    "titulo": "Intel/Altera MAX II EPM240T100C5",
    # entradas en el banco 1 y salidas en el 2: si los VCCIO de cada banco van a
    # voltajes distintos, cada grupo queda en el suyo.
    "entradas": EPM240_BANCO_1,
    "salidas": EPM240_BANCO_2 + EPM240_BANCO_1,
    "reserva": {},
    "solo_entrada": [],
    # Para los mensajes cuando el usuario elige sus propias patas. Las
    # especiales tambien son I/O, pero se dejan libres para los relojes y el
    # reset de los disenos secuenciales.
    "pines_especiales": {
        12: "GCLK0, que ktool deja libre para los relojes",
        14: "GCLK1, que ktool deja libre para los relojes",
        62: "GCLK2, que ktool deja libre para los relojes",
        64: "GCLK3, que ktool deja libre para los relojes",
        43: "DEV_OE, que ktool deja libre para el reset",
        44: "DEV_CLRn, que ktool deja libre para el reset",
    },
    "pines_fuera": "es de alimentacion, tierra o JTAG",
}

# Todas las placas que aceptan pines elegidos por el usuario, con el nombre
# corto que se usa en la CLI (--pines uno_nano=2,3,8) y en la ventana.
PLACAS_CON_PINES = {
    "pic18f4550": PIC["pic18f4550"],
    "pic18f45k50": PIC["pic18f45k50"],
    "pic16f877a": PIC["pic16f877a"],
    "pic16f628a": PIC["pic16f628a"],
    "pic16f84a": PIC["pic16f84a"],
    "esp32_wroom32": ESP32["esp32_wroom32"],
    "esp32_s3": ESP32["esp32_s3"],
    "esp32_c3": ESP32["esp32_c3"],
    "uno_nano": ARDUINO["uno_nano"],
    "mega2560": ARDUINO["mega2560"],
    "bluepill": BLUEPILL,
    "pico": PICO,
    "max2": EPM240,
}

# GAL22V10: 24 patas. 1 = CLK/I0, 2-11 y 13 = entradas, 14-23 = macroceldas.
# Cada macrocelda admite un numero fijo de terminos producto (hoja de datos de
# la ATF22V10 / GAL22V10, "Output Logic Macrocell"): 8, 10, 12, 14, 16, 16, 14,
# 12, 10, 8 de la pata 14 a la 23.
GAL22V10 = {
    "titulo": "GAL22V10 (WinCUPL)",
    "entradas": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 1],
    "terminos_por_pata": {14: 8, 15: 10, 16: 12, 17: 14, 18: 16,
                          19: 16, 20: 14, 21: 12, 22: 10, 23: 8},
}
