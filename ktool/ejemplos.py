"""Ejemplos listos para abrir: Archivo > Ejemplos en la ventana.

Cada ejemplo es una funcion que dice, en Python normal, que hace el circuito
fila por fila; `_proyecto` la recorre y arma el proyecto (.ktool.json) con sus
entradas ya nombradas (S1, S0, D3...). Asi se lee como la especificacion y no
como una tabla de unos y ceros que nadie puede revisar.

Los de "De las practicas" salen de los enunciados de Aplicacion de Sistemas
Digitales; los patrones de 7 segmentos son los de la tabla de la practica de
Convertidores de codigo (catodo comun: 1 = segmento encendido).
"""

from __future__ import annotations

from . import segmentos

X = "x"   # no importa

# BCD -> segmentos a..g, catodo comun (tabla de la practica de Convertidores)
SIETE_SEG = {
    0: "1111110", 1: "0110000", 2: "1101101", 3: "1111001", 4: "0110011",
    5: "1011011", 6: "1011111", 7: "1110000", 8: "1111111", 9: "1111011",
    # A, b, C, d, E, F para el decodificador hexadecimal
    10: "1110111", 11: "0011111", 12: "1001110", 13: "0111101", 14: "1001111", 15: "1000111",
}
SEGMENTOS = ["a", "b", "c", "d", "e", "f", "g"]
# Las entradas de los displays NO pueden ser D C B A: VHDL no distingue
# mayusculas, y la entrada A chocaria con el segmento a.
BCD = ["B3", "B2", "B1", "B0"]
# Las cantidades A de varios bits de las practicas se llaman A_2 A_1 A_0 y no
# A2 A1 A0: el sketch de Arduino nombra cada pin PIN_<senal>, y el nucleo de
# Arduino ya define PIN_A0 a PIN_A7 (los pines analogicos). B_2 B_1 B_0 van
# igual para que las dos cantidades se lean parejas.


def _proyecto(titulo, descripcion, entradas, salidas, funcion):
    """Recorre las 2^n filas (la primera entrada es el bit alto, igual que la
    tabla de la ventana) y arma el proyecto. `funcion` recibe {entrada: 0/1} y
    devuelve {salida: 0/1/X}."""
    n = len(entradas)
    columnas = {s: [] for s in salidas}
    for fila in range(1 << n):
        bits = {e: (fila >> (n - 1 - k)) & 1 for k, e in enumerate(entradas)}
        valores = funcion(bits)
        for s in salidas:
            columnas[s].append(valores[s])
    return {
        "doc_type": "table",
        "nvars": n,
        "input_names": list(entradas),
        "output_names": list(salidas),
        "values": [columnas[s] for s in salidas],
        "form": "auto",
        "proyecto": {"titulo": titulo, "descripcion": descripcion},
    }


def _numero(bits, nombres):
    """Los bits de `nombres` (el primero es el mas significativo) como entero."""
    valor = 0
    for nombre in nombres:
        valor = valor * 2 + bits[nombre]
    return valor


def _a_bits(valor, nombres):
    """Entero -> {nombre: bit}, el primer nombre es el bit mas significativo."""
    n = len(nombres)
    return {nombre: (valor >> (n - 1 - k)) & 1 for k, nombre in enumerate(nombres)}


def _es_primo(n):
    return n >= 2 and all(n % d for d in range(2, int(n ** 0.5) + 1))


# ------------------------------------------------------- combinacionales basicos

def multiplexor_4_a_1():
    return _proyecto(
        "Multiplexor 4 a 1",
        "S1 S0 escogen cual de las cuatro entradas de datos sale por Y.",
        ["S1", "S0", "D3", "D2", "D1", "D0"], ["Y"],
        lambda b: {"Y": b["D" + str(_numero(b, ["S1", "S0"]))]})


def demultiplexor_1_a_4():
    def f(b):
        sel = _numero(b, ["S1", "S0"])
        return {f"Y{k}": b["E"] if k == sel else 0 for k in range(4)}
    return _proyecto(
        "Demultiplexor 1 a 4",
        "La entrada E sale por la salida que escogen S1 S0; las demas quedan en 0.",
        ["E", "S1", "S0"], ["Y3", "Y2", "Y1", "Y0"], f)


def decodificador_2_a_4():
    def f(b):
        sel = _numero(b, ["A1", "A0"])
        return {f"D{k}": 1 if b["EN"] and k == sel else 0 for k in range(4)}
    return _proyecto(
        "Decodificador 2 a 4 con habilitacion",
        "Con EN = 1 se enciende solo la salida que indica A1 A0; con EN = 0, ninguna.",
        ["EN", "A1", "A0"], ["D3", "D2", "D1", "D0"], f)


def decodificador_3_a_8():
    def f(b):
        sel = _numero(b, ["A2", "A1", "A0"])
        return {f"D{k}": 1 if k == sel else 0 for k in range(8)}
    return _proyecto(
        "Decodificador 3 a 8",
        "Una sola salida en 1: la que dice el numero A2 A1 A0.",
        ["A2", "A1", "A0"], [f"D{k}" for k in range(7, -1, -1)], f)


def codificador_prioridad_4_a_2():
    def f(b):
        for k in (3, 2, 1, 0):          # gana la entrada mas alta
            if b[f"I{k}"]:
                return {"Y1": k >> 1, "Y0": k & 1, "V": 1}
        return {"Y1": X, "Y0": X, "V": 0}   # ninguna activa: Y no importa
    return _proyecto(
        "Codificador de prioridad 4 a 2",
        "Y1 Y0 dice cual es la entrada activa mas alta; V = 1 si hay alguna.",
        ["I3", "I2", "I1", "I0"], ["Y1", "Y0", "V"], f)


# ---------------------------------------------------------------- displays

def bcd_a_7_segmentos():
    def f(b):
        n = _numero(b, BCD)
        if n > 9:
            return {s: X for s in SEGMENTOS}      # 10 a 15 no existen en BCD
        return dict(zip(SEGMENTOS, (int(c) for c in SIETE_SEG[n])))
    return _proyecto(
        "BCD a 7 segmentos (catodo comun)",
        "Cada salida es un segmento: 1 = encendido. De 10 a 15 no importa.",
        BCD, SEGMENTOS, f)


def hexadecimal_a_7_segmentos_anodo():
    def f(b):
        n = _numero(b, BCD)
        # anodo comun: el segmento se enciende con 0, asi que se invierte
        return dict(zip(SEGMENTOS, (1 - int(c) for c in SIETE_SEG[n])))
    return _proyecto(
        "Hexadecimal a 7 segmentos (anodo comun)",
        "0 a F; anodo comun: 0 = segmento encendido.",
        BCD, SEGMENTOS, f)


# Los de 14 y 16 segmentos, el alfabeto, el mensaje y la barra salen de las
# tipografias de ktool/segmentos.py (los nombres de cada segmento estan
# dibujados al principio de ese archivo).

def bcd_a_14_segmentos():
    def f(b):
        n = _numero(b, BCD)
        if n > 9:
            return {s: X for s in segmentos.TIPOS["14seg"]}
        return segmentos.segmentos(str(n), "14seg")
    return _proyecto(
        "BCD a 14 segmentos (catodo comun)",
        "Cada salida es un segmento del display alfanumerico: 1 = encendido. "
        "De 10 a 15 no importa.",
        BCD, segmentos.TIPOS["14seg"], f)


def bcd_a_16_segmentos():
    def f(b):
        n = _numero(b, BCD)
        if n > 9:
            return {s: X for s in segmentos.TIPOS["16seg"]}
        return segmentos.segmentos(str(n), "16seg")
    return _proyecto(
        "BCD a 16 segmentos (catodo comun)",
        "Cada salida es un segmento; a1 y a2 son las mitades de arriba, d1 y d2 las de "
        "abajo. 1 = encendido. De 10 a 15 no importa.",
        BCD, segmentos.TIPOS["16seg"], f)


def _letras(tipo):
    """Las letras A-Z que tienen forma en ese display, en orden."""
    return "".join(c for c in segmentos.soportados(tipo) if c.isalpha())


def alfabeto_7_segmentos():
    letras = _letras("7seg")
    return segmentos.proyecto_mensaje(
        letras, "7seg", titulo=f"Alfabeto en 7 segmentos ({len(letras)} letras)")


def alfabeto_14_segmentos():
    return segmentos.proyecto_mensaje(_letras("14seg"), "14seg",
                                      titulo="Alfabeto en 14 segmentos")


def alfabeto_16_segmentos():
    return segmentos.proyecto_mensaje(_letras("16seg"), "16seg",
                                      titulo="Alfabeto en 16 segmentos")


def mensaje_hola_16_segmentos():
    return segmentos.proyecto_mensaje("HOLA", "16seg")


def barra_10_leds_nivel():
    return segmentos.proyecto_barra(10, "nivel")


def barra_10_leds_punto():
    return segmentos.proyecto_barra(10, "punto")


# ---------------------------------------------------------------- aritmeticos

def semisumador():
    return _proyecto(
        "Semisumador", "S = A + B sin acarreo de entrada; C es el acarreo.",
        ["A", "B"], ["S", "C"],
        lambda b: {"S": b["A"] ^ b["B"], "C": b["A"] & b["B"]})


def sumador_completo():
    def f(b):
        total = b["A"] + b["B"] + b["CIN"]
        return {"S": total & 1, "COUT": total >> 1}
    return _proyecto(
        "Sumador completo", "Suma de A, B y el acarreo de entrada CIN.",
        ["A", "B", "CIN"], ["S", "COUT"], f)


def semirrestador():
    return _proyecto(
        "Semirrestador", "D = A - B; BO es el prestamo (1 cuando B > A).",
        ["A", "B"], ["D", "BO"],
        lambda b: {"D": b["A"] ^ b["B"], "BO": (1 - b["A"]) & b["B"]})


def restador_completo():
    def f(b):
        resta = b["A"] - b["B"] - b["BIN"]
        return {"D": resta & 1, "BOUT": 1 if resta < 0 else 0}
    return _proyecto(
        "Restador completo", "D = A - B - BIN; BOUT es el prestamo de salida.",
        ["A", "B", "BIN"], ["D", "BOUT"], f)


def sumador_2_bits():
    def f(b):
        total = _numero(b, ["A1", "A0"]) + _numero(b, ["B1", "B0"])
        return _a_bits(total, ["CS", "S1", "S0"])
    return _proyecto(
        "Sumador de 2 bits", "A1A0 + B1B0 = CS S1 S0 (CS es el acarreo).",
        ["A1", "A0", "B1", "B0"], ["CS", "S1", "S0"], f)


def comparador_2_bits():
    def f(b):
        a, c = _numero(b, ["A1", "A0"]), _numero(b, ["B1", "B0"])
        return {"MAYOR": int(a > c), "IGUAL": int(a == c), "MENOR": int(a < c)}
    return _proyecto(
        "Comparador de 2 bits", "Compara A1A0 contra B1B0.",
        ["A1", "A0", "B1", "B0"], ["MAYOR", "IGUAL", "MENOR"], f)


# ----------------------------------------------------- convertidores de codigo

def binario_a_gray():
    def f(b):
        n = _numero(b, ["B3", "B2", "B1", "B0"])
        return _a_bits(n ^ (n >> 1), ["G3", "G2", "G1", "G0"])
    return _proyecto(
        "Binario a Gray (4 bits)", "Codigo Gray: entre numeros seguidos cambia un solo bit.",
        ["B3", "B2", "B1", "B0"], ["G3", "G2", "G1", "G0"], f)


def gray_a_binario():
    def f(b):
        g = _numero(b, ["G3", "G2", "G1", "G0"])
        n = 0
        while g:                    # binario = XOR de todos los corrimientos del Gray
            n ^= g
            g >>= 1
        return _a_bits(n, ["B3", "B2", "B1", "B0"])
    return _proyecto(
        "Gray a binario (4 bits)", "El inverso de binario a Gray.",
        ["G3", "G2", "G1", "G0"], ["B3", "B2", "B1", "B0"], f)


def complemento_a_2():
    def f(b):
        n = _numero(b, ["X3", "X2", "X1", "X0"])
        return _a_bits((-n) & 0xF, ["Y3", "Y2", "Y1", "Y0"])
    return _proyecto(
        "Complemento a 2 (4 bits)", "Y = NOT X + 1: el negativo de X en 4 bits.",
        ["X3", "X2", "X1", "X0"], ["Y3", "Y2", "Y1", "Y0"], f)


def bcd_a_exceso_3():
    def f(b):
        n = _numero(b, ["D", "C", "B", "A"])
        if n > 9:
            return {s: X for s in ("E3", "E2", "E1", "E0")}
        return _a_bits(n + 3, ["E3", "E2", "E1", "E0"])
    return _proyecto(
        "BCD a exceso-3", "Suma 3 a cada digito BCD. De 10 a 15 no importa.",
        ["D", "C", "B", "A"], ["E3", "E2", "E1", "E0"], f)


# ------------------------------------------------------------ de las practicas

def impares_menores_que_11():
    return _proyecto(
        "Impares menores que 11",
        "Detecta 1, 3, 5, 7 y 9 en binario de 4 bits (Diseno de circuitos combinatorios).",
        ["D", "C", "B", "A"], ["F"],
        lambda b: {"F": int(_numero(b, ["D", "C", "B", "A"]) in (1, 3, 5, 7, 9))})


def primos_4_bits():
    return _proyecto(
        "Primos de 4 bits", "Y = 1 si el numero es primo (2, 3, 5, 7, 11, 13).",
        ["A", "B", "C", "D"], ["Y"],
        lambda b: {"Y": int(_es_primo(_numero(b, ["A", "B", "C", "D"])))})


def primos_5_bits():
    nombres = ["A_4", "A_3", "A_2", "A_1", "A_0"]
    return _proyecto(
        "Primos de 5 bits",
        "La lampara L se enciende con cada numero primo de 0 a 31 (Practica 2). "
        "A_4 es el bit mas significativo (A4 en el enunciado).",
        nombres, ["L"], lambda b: {"L": int(_es_primo(_numero(b, nombres)))})


def copiadora():
    def f(b):
        if b["D"] and b["A"]:          # D y A nunca se cierran a la vez
            return {"Y": X}
        return {"Y": int(b["D"] + b["C"] + b["B"] + b["A"] >= 2)}
    return _proyecto(
        "Copiadora (Tocci)",
        "Salida alta con 2 o mas interruptores cerrados; D y A nunca juntos (no importa).",
        ["D", "C", "B", "A"], ["Y"], f)


def mezcladora():
    def f(b):
        cuantas = b["S4"] + b["S3"] + b["S2"] + b["S1"]
        return {"L1": int(cuantas in (1, 3)), "L2": int(cuantas in (1, 4))}
    return _proyecto(
        "Mezcladora de 4 sustancias",
        "L1 con exactamente 3, L2 con las 4, y las dos con una sola sustancia.",
        ["S4", "S3", "S2", "S1"], ["L1", "L2"], f)


def juego_de_adivinar():
    def f(b):
        if not b["CMP"]:                # sin el boton de comparar, todo apagado
            return {"MA": 0, "ME": 0, "EQ": 0}
        s, n = _numero(b, ["S1", "S0"]), _numero(b, ["N1", "N0"])
        return {"MA": int(n > s), "ME": int(n < s), "EQ": int(n == s)}
    return _proyecto(
        "Juego de adivinar",
        "Compara el numero del jugador N con el secreto S cuando se oprime CMP.",
        ["CMP", "S1", "S0", "N1", "N0"], ["MA", "ME", "EQ"], f)


def alarma_de_coche():
    return _proyecto(
        "Alarma de coche",
        "Suena con una puerta abierta, o con el switch encendido y sin cinturon "
        "(ejemplo de la Guia MAX II). Abierto = 0, cerrado = 1.",
        ["PI", "PD", "SW", "CINT"], ["AL"],   # CINT = cinturon (CIN se lee como acarreo)
        lambda b: {"AL": int((not b["PI"]) or (not b["PD"]) or (b["SW"] and not b["CINT"]))})


def compuertas_basicas():
    # Una salida por circuito integrado de la practica de Compuertas logicas;
    # se llaman Y_ porque AND, OR, NOT... son palabras reservadas de VHDL.
    def f(b):
        a, c = b["A"], b["B"]
        return {"Y_NAND": 1 - (a & c),     # 74LS00
                "Y_NOR": 1 - (a | c),      # 74LS02
                "Y_NOT": 1 - a,            # 74LS04 (solo usa A)
                "Y_AND": a & c,            # 74LS08
                "Y_OR": a | c,             # 74LS32
                "Y_XOR": a ^ c}            # 74LS86
    return _proyecto(
        "Compuertas basicas",
        "Las seis compuertas de la practica (74LS00, 02, 04, 08, 32 y 86) con las "
        "mismas dos entradas: un LED por compuerta.",
        ["A", "B"], ["Y_NAND", "Y_NOR", "Y_NOT", "Y_AND", "Y_OR", "Y_XOR"], f)


def alarma_refrigerador():
    # Tabla 2.3 de Diseno de circuitos combinatorios, tal como viene impresa:
    # F = 1 en las combinaciones C B A = 010, 011 y 111.
    def f(b):
        puerta_abierta = b["B"]
        return {"F": int(puerta_abierta and (b["A"] or not b["C"]))}
    return _proyecto(
        "Alarma del refrigerador (tabla 2.3)",
        "La tabla 2.3 de la practica: C = horario, B = puerta, A = dia. F = 1 en "
        "C B A = 010, 011 y 111 (F = B A + C' B).",
        ["C", "B", "A"], ["F"], f)


def sumador_3_bits():
    def f(b):
        total = _numero(b, ["A_2", "A_1", "A_0"]) + _numero(b, ["B_2", "B_1", "B_0"])
        return _a_bits(total, ["CS", "S2", "S1", "S0"])
    return _proyecto(
        "Sumador binario de 3 bits",
        "A_2A_1A_0 + B_2B_1B_0 = CS S2 S1 S0 (CS es el acarreo final).",
        ["A_2", "A_1", "A_0", "B_2", "B_1", "B_0"], ["CS", "S2", "S1", "S0"], f)


def restador_3_bits_comparador():
    def f(b):
        a, c = _numero(b, ["A_2", "A_1", "A_0"]), _numero(b, ["B_2", "B_1", "B_0"])
        resta = _a_bits((a - c) & 0b111, ["D2", "D1", "D0"])   # complemento a 2
        resta["PS"] = int(a < c)                               # prestamo final
        resta.update({"MENOR": int(a < c), "IGUAL": int(a == c), "MAYOR": int(a > c)})
        return resta
    return _proyecto(
        "Restador de 3 bits con comparador",
        "A - B = PS D2 D1 D0 (PS = 1 si la resta es negativa) y el comparador que sale "
        "de la resta: MENOR, IGUAL o MAYOR.",
        ["A_2", "A_1", "A_0", "B_2", "B_1", "B_0"],
        ["PS", "D2", "D1", "D0", "MENOR", "IGUAL", "MAYOR"], f)


def restador_3_bits_7_segmentos():
    def f(b):
        resta = _numero(b, ["A_2", "A_1", "A_0"]) - _numero(b, ["B_2", "B_1", "B_0"])
        # el display no muestra negativos: se muestra la magnitud (el complemento
        # a 2 del resultado cuando el prestamo es 1) y el signo va aparte
        salida = dict(zip(SEGMENTOS, (int(c) for c in SIETE_SEG[abs(resta)])))
        salida["SIGNO"] = int(resta < 0)
        return salida
    return _proyecto(
        "Restador de 3 bits decodificado a 7 segmentos",
        "A_2A_1A_0 - B_2B_1B_0 en un display de catodo comun: muestra la magnitud (0 a 7) y "
        "SIGNO = 1 cuando el resultado es negativo (un LED o el segmento g de otro display).",
        ["A_2", "A_1", "A_0", "B_2", "B_1", "B_0"], SEGMENTOS + ["SIGNO"], f)


def binario_a_octal_7_segmentos():
    def f(b):
        return dict(zip(SEGMENTOS, (int(c) for c in SIETE_SEG[_numero(b, ["B2", "B1", "B0"])])))
    return _proyecto(
        "Binario a octal en 7 segmentos",
        "Un numero de 3 bits (0 a 7) en un display de catodo comun: 1 = segmento encendido.",
        ["B2", "B1", "B0"], SEGMENTOS, f)


def nombre_16_segmentos():
    # El texto es de ejemplo: cada quien escribe el suyo en Herramientas >
    # Texto a segmentos.
    return segmentos.proyecto_mensaje(
        "NOMBRE", "16seg", titulo="Nombre en 16 segmentos (texto de ejemplo)")


def alu_2_bits():
    def f(b):
        a, c = _numero(b, ["A_1", "A_0"]), _numero(b, ["B_1", "B_0"])
        operacion = _numero(b, ["SB", "SC"])
        # salidas aritmeticas: Sb Sc = 00 suma, 01 resta, 10 comparador, 11 apagadas
        if operacion == 0:                  # Cs S1 S0
            aritmetica = a + c
        elif operacion == 1:                # Ps D1 D0: la resta en complemento a 2
            aritmetica = (a - c) & 0b111
        elif operacion == 2:                # menor, igual, mayor
            aritmetica = 4 * (a < c) + 2 * (a == c) + (a > c)
        else:
            aritmetica = 0
        # salidas logicas, bit a bit: 00 AND, 01 OR, 10 XOR, 11 NOT A
        logica = [a & c, a | c, a ^ c, ~a & 0b11][operacion]
        salida = _a_bits(aritmetica, ["ZA", "ZB", "ZC"])
        salida.update(_a_bits(logica, ["ZD", "ZE"]))
        return salida
    return _proyecto(
        "ALU de 2 bits",
        "SB SC escogen la operacion. ZA ZB ZC: suma (Cs S1 S0), resta (Ps D1 D0), "
        "comparador (menor, igual, mayor) o apagadas. ZD ZE: AND, OR, XOR o NOT A, bit a "
        "bit. Sa no entra: en la tabla de la practica las salidas que no escoge Sa no "
        "importan, asi que ninguna salida depende de Sa.",
        ["SB", "SC", "A_1", "A_0", "B_1", "B_0"], ["ZA", "ZB", "ZC", "ZD", "ZE"], f)


def xor_de_tres_entradas():
    return _proyecto(
        "XOR de tres entradas",
        "F = A xor B xor C: el Ejemplo 1 de Dispositivos logicos programables y VHDL.",
        ["A", "B", "C"], ["F"],
        lambda b: {"F": b["A"] ^ b["B"] ^ b["C"]})


# -------------------------------------------- secuenciales (Circuitos Secuenciales)
# Se abren en el editor de maquinas de estado. Son los del Desarrollo y el
# Cuestionario de la practica; los que traen una ambiguedad en el enunciado lo
# dicen en su titulo.

def _contador(*args, **kw):
    from .fsm import contadores
    return contadores.contador(*args, **kw)


def mod13_descendente():
    from .fsm.contadores import descendente
    return _contador("Contador mod-13 descendente", {"": descendente(13)})


def mod8_secuencia_con_paro():
    return _contador("Contador mod-8: 4,7,2,6,0,3,5,1 (X=1 paro)",
                     {"0": [4, 7, 2, 6, 0, 3, 5, 1], "1": "paro"}, ["X"])


def mod16_con_x_y():
    from .fsm.contadores import ascendente
    return _contador("Contador mod-16 con X Y (00 sube, 01 paro, 10 reinicio, 11 multiplos de 3)",
                     {"00": ascendente(16), "01": "paro", "10": "reinicio",
                      "11": [15, 12, 9, 6, 3, 0]}, ["X", "Y"])


def mod6_descendente():
    from .fsm.contadores import descendente
    return _contador("Contador mod-6 descendente", {"": descendente(6)})


def mod11_ascendente():
    from .fsm.contadores import ascendente
    return _contador("Contador mod-11 ascendente", {"": ascendente(11)})


def mod8_pares_impares():
    return _contador("Contador mod-8: X=0 pares sube, X=1 impares baja",
                     {"0": [0, 2, 4, 6], "1": [7, 5, 3, 1]}, ["X"])


def mod16_multiplos_de_5():
    return _contador("Contador mod-16: 00 multiplos de 5, 01 paro, 10 SET, 11 multiplos de 3 baja",
                     {"00": [0, 5, 10, 15], "01": "paro", "10": "set",
                      "11": [15, 12, 9, 6, 3, 0]}, ["X", "Y"])


def mod16_multiplos_de_4_primos():
    return _contador("Contador mod-16: 00 multiplos de 4, 01 paro, 10 reinicio, 11 primos baja",
                     {"00": [0, 4, 8, 12], "01": "paro", "10": "reinicio",
                      "11": [13, 11, 7, 5, 3, 2]}, ["X", "Y"])

# El orden y los nombres del menu Archivo > Ejemplos
CATALOGO = [
    ("Combinacionales", [
        ("Multiplexor 4 a 1", multiplexor_4_a_1),
        ("Demultiplexor 1 a 4", demultiplexor_1_a_4),
        ("Decodificador 2 a 4", decodificador_2_a_4),
        ("Decodificador 3 a 8", decodificador_3_a_8),
        ("Codificador de prioridad 4 a 2", codificador_prioridad_4_a_2),
    ]),
    ("Displays", [
        ("BCD a 7 segmentos (catodo comun)", bcd_a_7_segmentos),
        ("Hexadecimal a 7 segmentos (anodo comun)", hexadecimal_a_7_segmentos_anodo),
        ("BCD a 14 segmentos", bcd_a_14_segmentos),
        ("BCD a 16 segmentos", bcd_a_16_segmentos),
        ("Alfabeto en 7 segmentos", alfabeto_7_segmentos),
        ("Alfabeto en 14 segmentos", alfabeto_14_segmentos),
        ("Alfabeto en 16 segmentos", alfabeto_16_segmentos),
        ("Mensaje HOLA en 16 segmentos", mensaje_hola_16_segmentos),
        ("Barra de 10 LEDs (nivel)", barra_10_leds_nivel),
        ("Barra de 10 LEDs (punto)", barra_10_leds_punto),
    ]),
    ("Aritmeticos", [
        ("Semisumador", semisumador),
        ("Sumador completo", sumador_completo),
        ("Semirrestador", semirrestador),
        ("Restador completo", restador_completo),
        ("Sumador de 2 bits", sumador_2_bits),
        ("Comparador de 2 bits", comparador_2_bits),
    ]),
    ("Convertidores de codigo", [
        ("Binario a Gray", binario_a_gray),
        ("Gray a binario", gray_a_binario),
        ("Complemento a 2", complemento_a_2),
        ("BCD a exceso-3", bcd_a_exceso_3),
    ]),
    ("De las practicas", [
        ("Impares menores que 11", impares_menores_que_11),
        ("Primos de 4 bits", primos_4_bits),
        ("Primos de 5 bits", primos_5_bits),
        ("Copiadora", copiadora),
        ("Mezcladora de 4 sustancias", mezcladora),
        ("Juego de adivinar", juego_de_adivinar),
        ("Alarma de coche", alarma_de_coche),
        ("Compuertas basicas", compuertas_basicas),
        ("Alarma del refrigerador (tabla 2.3)", alarma_refrigerador),
        ("Sumador de 3 bits", sumador_3_bits),
        ("Restador de 3 bits con comparador", restador_3_bits_comparador),
        ("Restador de 3 bits a 7 segmentos", restador_3_bits_7_segmentos),
        ("Binario a octal en 7 segmentos", binario_a_octal_7_segmentos),
        ("Nombre en 16 segmentos", nombre_16_segmentos),
        ("ALU de 2 bits", alu_2_bits),
        ("XOR de tres entradas", xor_de_tres_entradas),
    ]),
    ("Contadores (maquinas de estado)", [
        ("Mod-13 descendente", mod13_descendente),
        ("Mod-8: 4,7,2,6,0,3,5,1 con paro", mod8_secuencia_con_paro),
        ("Mod-16 con X Y", mod16_con_x_y),
        ("Mod-6 descendente", mod6_descendente),
        ("Mod-11 ascendente", mod11_ascendente),
        ("Mod-8 pares / impares", mod8_pares_impares),
        ("Mod-16 multiplos de 5 y SET", mod16_multiplos_de_5),
        ("Mod-16 multiplos de 4 y primos", mod16_multiplos_de_4_primos),
    ]),
]
