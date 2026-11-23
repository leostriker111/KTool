"""Displays de segmentos: que segmentos enciende cada caracter.

Este modulo es logica pura (sin Tk): las tipografias de 7, 14 y 16 segmentos,
la tabla de verdad de un mensaje, la de una barra de LEDs y el dibujo en SVG
para el documento HTML. La ventana (gui/displays.py) usa la misma geometria
para que lo que se ve en pantalla sea lo mismo que sale impreso.

Nombres de los segmentos (los de las hojas de datos de displays comerciales:
LTP-587 de 14 segmentos, PSC05-11 de 16 segmentos). Las hojas de datos se
saltan la letra I porque se confunde con el 1; aqui tambien, y ademas `i` es
la variable del ciclo en el codigo generado (ktool/hw/modelo.py, RESERVADAS),
asi que no podria ser el nombre de una senal.

    7 segmentos            14 segmentos             16 segmentos

       aaaa              aaaaaaaaaaa            a1a1a1  a2a2a2
      f    b            f h   j   k b          f h     j     k b
      f    b            f  h  j  k  b          f  h    j    k  b
       gggg              g1g1g1 g2g2g2          g1g1g1  g2g2g2
      e    c            e  l  m  n  c          e  l    m    n  c
      e    c            e l   m   n c          e l     m     n c
       dddd   dp         ddddddddddd   dp       d1d1d1  d2d2d2   dp

  a arriba, b arriba a la derecha, c abajo a la derecha, d abajo,
  e abajo a la izquierda, f arriba a la izquierda, g en medio.
  En 14 y 16: g1 es la mitad izquierda del de en medio y g2 la derecha;
  h, k, l, n son las cuatro diagonales (h arriba izquierda, k arriba derecha,
  l abajo izquierda, n abajo derecha); j y m son las verticales del centro
  (j arriba, m abajo). En 16 la barra de arriba y la de abajo van partidas:
  a1 y d1 son las mitades izquierdas, a2 y d2 las derechas.
  dp es el punto decimal, opcional en los tres.

Convencion de valores: catodo comun, 1 = segmento encendido (igual que
SIETE_SEG de ktool/ejemplos.py). Con anodo comun se invierte todo.
"""

from __future__ import annotations

import math

X = "x"   # no importa

TIPOS = {
    "7seg": ["a", "b", "c", "d", "e", "f", "g"],
    "14seg": ["a", "b", "c", "d", "e", "f", "g1", "g2", "h", "j", "k", "l", "m", "n"],
    "16seg": ["a1", "a2", "b", "c", "d1", "d2", "e", "f", "g1", "g2",
              "h", "j", "k", "l", "m", "n"],
}
PUNTO = "dp"   # el punto decimal: no esta en TIPOS porque es opcional

NOMBRES_TIPO = {"7seg": "7 segmentos", "14seg": "14 segmentos", "16seg": "16 segmentos"}

# La barra de LEDs: L0 es el primero en encender (a la izquierda) y L9 el ultimo.
BARRA10 = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"]

MAX_CARACTERES = 64   # 6 entradas como maximo (ktool/core/table.py, MAX_VARS)


# ---------------------------------------------------------------- tipografias
# Cada caracter es la lista de segmentos encendidos, separados por espacios.
# Las letras no distinguen mayusculas: "a" y "A" se dibujan igual.

SIETE = {
    "0": "a b c d e f",
    "1": "b c",
    "2": "a b d e g",
    "3": "a b c d g",
    "4": "b c f g",
    "5": "a c d f g",
    "6": "a c d e f g",
    "7": "a b c",
    "8": "a b c d e f g",
    "9": "a b c d f g",
    # Letras: la forma (mayuscula o minuscula) que no se confunde con otra.
    "A": "a b c e f g",          # A
    "B": "c d e f g",            # b
    "C": "a d e f",              # C
    "D": "b c d e g",            # d
    "E": "a d e f g",            # E
    "F": "a e f g",              # F
    "G": "a c d e f",            # G
    "H": "b c e f g",            # H
    "I": "e f",                  # I a la izquierda, para no confundirla con el 1
    "J": "b c d e",              # J
    "L": "d e f",                # L
    "N": "c e g",                # n
    "O": "c d e g",              # o (la O mayuscula seria el 0)
    "P": "a b e f g",            # P
    "Q": "a b c f g",            # q
    "R": "e g",                  # r
    "S": "a c d f g",            # S (igual que el 5, es la convencion)
    "T": "d e f g",              # t
    "U": "b c d e f",            # U
    "Y": "b c d f g",            # y
    # Signos
    " ": "",
    "-": "g",
    "_": "d",
    "=": "d g",
}
# Sin forma en 7 segmentos: K, M, V, W, X, Z. M y W necesitan diagonales o un
# tercer palo; K, V, X y Z solo saldrian iguales a H, U, H y 2. segmentos()
# lanza ValueError con ellas en vez de inventar un dibujo que se lee mal.
SIN_FORMA_EN_7 = "KMVWXZ"

CATORCE = {
    "0": "a b c d e f k l",      # el cero lleva la diagonal, para no confundirlo con la O
    "1": "b c",
    "2": "a b d e g1 g2",
    "3": "a b c d g2",
    "4": "b c f g1 g2",
    "5": "a c d f g1 g2",
    "6": "a c d e f g1 g2",
    "7": "a b c",
    "8": "a b c d e f g1 g2",
    "9": "a b c d f g1 g2",
    "A": "a b c e f g1 g2",
    "B": "a b c d g2 j m",
    "C": "a d e f",
    "D": "a b c d j m",
    "E": "a d e f g1",
    "F": "a e f g1",
    "G": "a c d e f g2",
    "H": "b c e f g1 g2",
    "I": "a d j m",
    "J": "b c d e",
    "K": "e f g1 k n",
    "L": "d e f",
    "M": "b c e f h k",
    "N": "b c e f h n",
    "O": "a b c d e f",
    "P": "a b e f g1 g2",
    "Q": "a b c d e f n",
    "R": "a b e f g1 g2 n",
    "S": "a c d f g1 g2",
    "T": "a j m",
    "U": "b c d e f",
    "V": "e f k l",
    "W": "b c e f l n",
    "X": "h k l n",
    "Y": "h k m",
    "Z": "a d k l",
    " ": "",
    "-": "g1 g2",
    "_": "d",
    "=": "d g1 g2",
    "+": "g1 g2 j m",
    "*": "g1 g2 h j k l m n",
    "/": "k l",
    "\\": "h n",
    "|": "j m",
    "<": "k n",
    ">": "h l",
    "$": "a c d f g1 g2 j m",
    "'": "j",
}

DIECISEIS = {
    "0": "a1 a2 b c d1 d2 e f k l",
    "1": "b c",
    "2": "a1 a2 b d1 d2 e g1 g2",
    "3": "a1 a2 b c d1 d2 g2",
    "4": "b c f g1 g2",
    "5": "a1 a2 c d1 d2 f g1 g2",
    "6": "a1 a2 c d1 d2 e f g1 g2",
    "7": "a1 a2 b c",
    "8": "a1 a2 b c d1 d2 e f g1 g2",
    "9": "a1 a2 b c d1 d2 f g1 g2",
    "A": "a1 a2 b c e f g1 g2",
    "B": "a1 a2 b c d1 d2 g2 j m",
    "C": "a1 a2 d1 d2 e f",
    "D": "a1 a2 b c d1 d2 j m",
    "E": "a1 a2 d1 d2 e f g1",
    "F": "a1 a2 e f g1",
    "G": "a1 a2 c d1 d2 e f g2",
    "H": "b c e f g1 g2",
    "I": "a1 a2 d1 d2 j m",
    "J": "b c d1 d2 e",
    "K": "e f g1 k n",
    "L": "d1 d2 e f",
    "M": "b c e f h k",
    "N": "b c e f h n",
    "O": "a1 a2 b c d1 d2 e f",
    "P": "a1 a2 b e f g1 g2",
    "Q": "a1 a2 b c d1 d2 e f n",
    "R": "a1 a2 b e f g1 g2 n",
    "S": "a1 a2 c d1 d2 f g1 g2",
    "T": "a1 a2 j m",
    "U": "b c d1 d2 e f",
    "V": "e f k l",
    "W": "b c e f l n",
    "X": "h k l n",
    "Y": "h k m",
    "Z": "a1 a2 d1 d2 k l",
    " ": "",
    "-": "g1 g2",
    "_": "d1 d2",
    "=": "d1 d2 g1 g2",
    "+": "g1 g2 j m",
    "*": "g1 g2 h j k l m n",
    "/": "k l",
    "\\": "h n",
    "|": "j m",
    "<": "k n",
    ">": "h l",
    "$": "a1 a2 c d1 d2 f g1 g2 j m",
    "'": "j",
}

TIPOGRAFIAS = {"7seg": SIETE, "14seg": CATORCE, "16seg": DIECISEIS}


# ---------------------------------------------------------------- caracteres

def _revisar_tipo(tipo):
    """Un solo lugar para el error de tipo desconocido."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo de display desconocido: {tipo!r} (usa 7seg, 14seg o 16seg)")


def segmentos(caracter, tipo, con_punto=False):
    """{segmento: 0/1} de un caracter, en el orden de TIPOS[tipo].

    Existe para no repetir la consulta a la tipografia en cada lugar que dibuja
    o arma tablas. Las letras no distinguen mayusculas. Con `con_punto` agrega
    el segmento dp (apagado). Lanza ValueError si el caracter no tiene forma en
    ese tipo de display.
    """
    _revisar_tipo(tipo)
    if not isinstance(caracter, str) or len(caracter) != 1:
        raise ValueError(f"se espera un solo caracter, no {caracter!r}")
    clave = caracter.upper()
    tipografia = TIPOGRAFIAS[tipo]
    if clave not in tipografia:
        if tipo == "7seg" and clave in SIN_FORMA_EN_7:
            motivo = "no tiene una forma legible en 7 segmentos; usa 14 o 16 segmentos"
        else:
            motivo = f"no existe en {NOMBRES_TIPO[tipo]}"
        raise ValueError(f"el caracter {caracter!r} {motivo}")
    encendidos = tipografia[clave].split()
    resultado = {s: (1 if s in encendidos else 0) for s in TIPOS[tipo]}
    if con_punto:
        resultado[PUNTO] = 0
    return resultado


def texto(cadena, tipo, con_punto=False):
    """Una lista de {segmento: 0/1}, uno por digito del display.

    Existe para convertir un mensaje completo de una vez. Con `con_punto`, un
    "." enciende el dp del caracter anterior (como en "3.14"); si no hay
    caracter anterior, ocupa un digito en blanco con el punto encendido. Sin
    `con_punto`, el "." es un caracter mas y da ValueError si no existe.
    """
    _revisar_tipo(tipo)
    digitos = []
    for caracter in cadena:
        if con_punto and caracter == ".":
            if digitos and digitos[-1][PUNTO] == 0:
                digitos[-1][PUNTO] = 1
            else:
                blanco = segmentos(" ", tipo, con_punto=True)
                blanco[PUNTO] = 1
                digitos.append(blanco)
            continue
        digitos.append(segmentos(caracter, tipo, con_punto=con_punto))
    return digitos


def soportados(tipo):
    """Los caracteres que existen en ese tipo, en el orden de la tipografia.

    Existe para decirle al usuario que puede escribir, sin abrir este archivo."""
    _revisar_tipo(tipo)
    return "".join(TIPOGRAFIAS[tipo].keys())


def no_soportados(cadena, tipo):
    """Los caracteres de `cadena` que no existen en ese tipo, sin repetir y en
    el orden en que aparecen. Existe para avisar en la ventana sin lanzar errores."""
    _revisar_tipo(tipo)
    faltan = []
    for caracter in cadena:
        if caracter.upper() not in TIPOGRAFIAS[tipo] and caracter not in faltan:
            faltan.append(caracter)
    return "".join(faltan)


# ---------------------------------------------------------------- tablas de verdad

def _bits_para(cuantos):
    """Las entradas justas para numerar `cuantos` casos (minimo 2, lo que pide la tabla)."""
    bits = 2
    while (1 << bits) < cuantos:
        bits += 1
    return bits


def _tabla(titulo, descripcion, entradas, salidas, filas, notas):
    """Arma el diccionario de proyecto, el mismo formato que `_proyecto` de
    ktool/ejemplos.py. `filas` es una lista de {salida: 0/1/x}, una por fila."""
    proyecto = {
        "doc_type": "table",
        "nvars": len(entradas),
        "input_names": list(entradas),
        "output_names": list(salidas),
        "values": [[fila[s] for fila in filas] for s in salidas],
        "form": "auto",
        "proyecto": {"titulo": titulo, "descripcion": descripcion},
    }
    if notas:
        proyecto["notes_on"] = True
        proyecto["notes"] = list(notas)
    return proyecto


def proyecto_mensaje(cadena, tipo, anodo_comun=False, nombres_entrada=None, titulo=None,
                     con_punto=False):
    """Tabla de verdad que muestra un mensaje caracter por caracter.

    Existe para que un texto (p. ej. "HOLA") se convierta en el decodificador
    que lo saca en el display: las entradas son el numero del caracter (fila 0
    = primer caracter) y las salidas son los segmentos. Las filas que sobran
    quedan como no importa. Con anodo comun se invierte cada segmento.
    Los nombres de entrada por omision son N2 N1 N0 (no chocan con ningun
    segmento). Lanza ValueError si el mensaje esta vacio, pasa de 64
    caracteres, trae un caracter que no existe o los nombres no compilan.
    """
    from .hw.modelo import validar_nombres
    _revisar_tipo(tipo)
    digitos = texto(cadena, tipo, con_punto=con_punto)
    if not digitos:
        raise ValueError("el mensaje esta vacio")
    if len(digitos) > MAX_CARACTERES:
        raise ValueError(
            f"el mensaje tiene {len(digitos)} caracteres; el maximo es {MAX_CARACTERES} "
            "(6 entradas)")
    bits = _bits_para(len(digitos))
    if nombres_entrada is None:
        nombres_entrada = [f"N{k}" for k in range(bits - 1, -1, -1)]
    nombres_entrada = list(nombres_entrada)
    if len(nombres_entrada) != bits:
        raise ValueError(
            f"el mensaje necesita {bits} entradas y se dieron {len(nombres_entrada)} nombres")
    salidas = list(TIPOS[tipo]) + ([PUNTO] if con_punto else [])
    validar_nombres(nombres_entrada, salidas)

    caracteres = _caracteres_por_digito(cadena, con_punto)
    filas, notas = [], []
    for fila in range(1 << bits):
        if fila < len(digitos):
            valores = digitos[fila]
            if anodo_comun:
                valores = {s: 1 - v for s, v in valores.items()}
            filas.append(valores)
            notas.append(f"'{caracteres[fila]}'")
        else:
            filas.append({s: X for s in salidas})
            notas.append("")

    conexion = "anodo comun: 0 = encendido" if anodo_comun else "catodo comun: 1 = encendido"
    if titulo is None:
        titulo = f"Mensaje \"{cadena}\" en {NOMBRES_TIPO[tipo]}"
    descripcion = (
        f"Las entradas {' '.join(nombres_entrada)} son el numero del caracter (0 = el "
        f"primero); cada salida es un segmento ({conexion}). "
        f"Las filas despues del caracter {len(digitos) - 1} no importan.")
    return _tabla(titulo, descripcion, nombres_entrada, salidas, filas, notas)


def _caracteres_por_digito(cadena, con_punto):
    """El texto que muestra cada digito, para las notas de la tabla ("3." si
    lleva punto). Sigue la misma regla que texto()."""
    if not con_punto:
        return list(cadena)
    etiquetas = []
    for caracter in cadena:
        if caracter == ".":
            if etiquetas and not etiquetas[-1].endswith("."):
                etiquetas[-1] += "."
            else:
                etiquetas.append(".")
            continue
        etiquetas.append(caracter)
    return etiquetas


def proyecto_barra(n_leds=10, modo="nivel"):
    """Tabla de verdad de una barra de LEDs manejada por un numero binario.

    Existe para el ejemplo clasico del vumetro: en modo "nivel" (termometro)
    el valor V enciende los LEDs L0 a L(V-1), de 0 (todo apagado) a n_leds
    (todo encendido); en modo "punto" el valor V enciende solo el LED LV, de 0
    a n_leds - 1. Los valores que sobran no importan. Entradas V3..V0 (las que
    alcancen) y salidas L0 primero.
    """
    from .hw.modelo import validar_nombres
    if modo not in ("nivel", "punto"):
        raise ValueError(f"modo de barra desconocido: {modo!r} (usa nivel o punto)")
    if not 2 <= n_leds <= 32:
        raise ValueError(f"la barra admite de 2 a 32 LEDs; pediste {n_leds}")
    valores_validos = n_leds + 1 if modo == "nivel" else n_leds
    bits = _bits_para(valores_validos)
    entradas = [f"V{k}" for k in range(bits - 1, -1, -1)]
    salidas = [f"L{k}" for k in range(n_leds)]
    validar_nombres(entradas, salidas)

    filas, notas = [], []
    for valor in range(1 << bits):
        if valor >= valores_validos:
            filas.append({s: X for s in salidas})
            notas.append("")
        elif modo == "nivel":
            filas.append({f"L{k}": (1 if k < valor else 0) for k in range(n_leds)})
            notas.append(f"{valor} LEDs")
        else:
            filas.append({f"L{k}": (1 if k == valor else 0) for k in range(n_leds)})
            notas.append(f"L{valor}")

    if modo == "nivel":
        titulo = f"Barra de {n_leds} LEDs, modo nivel"
        descripcion = (f"El valor {' '.join(entradas)} dice cuantos LEDs encienden, de L0 en "
                       f"adelante (0 a {n_leds}). Los valores mayores no importan.")
    else:
        titulo = f"Barra de {n_leds} LEDs, modo punto"
        descripcion = (f"El valor {' '.join(entradas)} enciende un solo LED: el de su numero "
                       f"(0 a {n_leds - 1}). Los valores mayores no importan.")
    return _tabla(titulo, descripcion, entradas, salidas, filas, notas)


# ---------------------------------------------------------------- geometria
# Cada segmento es un poligono [x0, y0, x1, y1, ...] en pixeles de un digito.
# La misma geometria dibuja la ventana (Tk) y el documento (SVG).

def barra_horizontal(x1, x2, y, grueso):
    """Hexagono acostado con las puntas en bisel, de x1 a x2 sobre la linea y."""
    h = grueso / 2
    return [x1, y, x1 + h, y - h, x2 - h, y - h, x2, y, x2 - h, y + h, x1 + h, y + h]


def barra_vertical(x, y1, y2, grueso):
    """Hexagono parado con las puntas en bisel, de y1 a y2 sobre la columna x."""
    h = grueso / 2
    return [x, y1, x + h, y1 + h, x + h, y2 - h, x, y2, x - h, y2 - h, x - h, y1 + h]


def diagonal(x0, y0, x1, y1, grueso, bajando):
    """Banda inclinada que llena el rectangulo (x0, y0)-(x1, y1) de esquina a
    esquina, con el grueso de los demas segmentos.

    `bajando` = True va de arriba izquierda a abajo derecha (como \\); False va
    de arriba derecha a abajo izquierda (como /). Es un hexagono y no una linea
    para que se vea igual que los otros segmentos y se pueda rellenar.
    """
    ancho, alto = x1 - x0, y1 - y0
    largo = math.hypot(ancho, alto)
    dx = (grueso / 2) * largo / alto
    dy = (grueso / 2) * largo / ancho
    if bajando:
        return [x0, y0, x0 + dx, y0, x1, y1 - dy, x1, y1, x1 - dx, y1, x0, y0 + dy]
    return [x1, y0, x1, y0 + dy, x0 + dx, y1, x0, y1, x0, y1 - dy, x1 - dx, y0]


def punto(cx, cy, radio):
    """Octagono para el punto decimal: se dibuja igual que un segmento."""
    pts = []
    for k in range(8):
        angulo = math.pi / 8 + k * math.pi / 4
        pts += [round(cx + radio * math.cos(angulo), 2), round(cy + radio * math.sin(angulo), 2)]
    return pts


def geometria(tipo):
    """([(nombre, poligono), ...], ancho, alto) de un digito o de la barra.

    Existe para que la ventana y el SVG compartan un solo dibujo. `tipo` es
    7seg, 14seg, 16seg o barra10. Los digitos incluyen el dp al final.
    """
    if tipo == "barra10":
        return _geometria_barra(), 10 + 16 * len(BARRA10), 84
    if tipo == "7seg":
        return _geometria_7(), 112, 168
    if tipo in ("14seg", "16seg"):
        return _geometria_14_16(tipo), 122, 168
    raise ValueError(f"tipo de display desconocido: {tipo!r}")


def _geometria_7():
    """Las medidas del display de 7 segmentos de siempre (las de la ventana)."""
    t, xL, xR, yT, yM, yB = 13, 26, 86, 24, 84, 144
    s = 1.5   # separacion entre segmentos que se tocan
    return [
        ("a", barra_horizontal(xL + s, xR - s, yT, t)),
        ("b", barra_vertical(xR, yT + s, yM - s, t)),
        ("c", barra_vertical(xR, yM + s, yB - s, t)),
        ("d", barra_horizontal(xL + s, xR - s, yB, t)),
        ("e", barra_vertical(xL, yM + s, yB - s, t)),
        ("f", barra_vertical(xL, yT + s, yM - s, t)),
        ("g", barra_horizontal(xL + s, xR - s, yM, t)),
        (PUNTO, punto(xR + 14, yB + 2, 6)),
    ]


def _geometria_14_16(tipo):
    """14 y 16 segmentos comparten todo salvo la barra de arriba y la de abajo."""
    t, xL, xR, yT, yM, yB = 11, 24, 94, 22, 84, 146
    xC = (xL + xR) / 2
    s = 1.5          # separacion entre segmentos que se tocan
    m = t / 2 + 2.5  # margen de las diagonales y las verticales del centro
    poligonos = []
    if tipo == "16seg":
        poligonos += [
            ("a1", barra_horizontal(xL + s, xC - s, yT, t)),
            ("a2", barra_horizontal(xC + s, xR - s, yT, t)),
        ]
    else:
        poligonos.append(("a", barra_horizontal(xL + s, xR - s, yT, t)))
    poligonos += [
        ("b", barra_vertical(xR, yT + s, yM - s, t)),
        ("c", barra_vertical(xR, yM + s, yB - s, t)),
    ]
    if tipo == "16seg":
        poligonos += [
            ("d1", barra_horizontal(xL + s, xC - s, yB, t)),
            ("d2", barra_horizontal(xC + s, xR - s, yB, t)),
        ]
    else:
        poligonos.append(("d", barra_horizontal(xL + s, xR - s, yB, t)))
    poligonos += [
        ("e", barra_vertical(xL, yM + s, yB - s, t)),
        ("f", barra_vertical(xL, yT + s, yM - s, t)),
        ("g1", barra_horizontal(xL + s, xC - s, yM, t)),
        ("g2", barra_horizontal(xC + s, xR - s, yM, t)),
        ("h", diagonal(xL + m, yT + m, xC - m, yM - m, t * 0.9, bajando=True)),
        ("j", barra_vertical(xC, yT + t / 2 + s, yM - t / 2 - s, t)),
        ("k", diagonal(xC + m, yT + m, xR - m, yM - m, t * 0.9, bajando=False)),
        ("l", diagonal(xL + m, yM + m, xC - m, yB - m, t * 0.9, bajando=False)),
        ("m", barra_vertical(xC, yM + t / 2 + s, yB - t / 2 - s, t)),
        ("n", diagonal(xC + m, yM + m, xR - m, yB - m, t * 0.9, bajando=True)),
        (PUNTO, punto(xR + 14, yB + 2, 5.5)),
    ]
    return poligonos


def _geometria_barra():
    """Diez rectangulos en fila, como la barra de 10 LEDs en encapsulado DIP-20."""
    poligonos = []
    for k, nombre in enumerate(BARRA10):
        x0 = 10 + 16 * k
        poligonos.append((nombre, [x0, 12, x0 + 11, 12, x0 + 11, 60, x0, 60]))
    return poligonos


# ---------------------------------------------------------------- SVG

SVG_ENCENDIDO = "#7a1010"   # rojo oscuro: se distingue impreso en blanco y negro
SVG_APAGADO = "#e8e8e8"
SVG_BORDE_APAGADO = "#c4c4c4"


def _svg_poligonos(tipo, encendidos, dx=0):
    """Los <polygon> de un digito, corridos `dx` pixeles. El dp solo se dibuja
    si viene en `encendidos`, para no ensuciar los digitos que no lo usan."""
    poligonos, _ancho, _alto = geometria(tipo)
    partes = []
    for nombre, pts in poligonos:
        if nombre == PUNTO and PUNTO not in encendidos:
            continue
        coordenadas = " ".join(
            f"{round(pts[i] + dx, 2)},{round(pts[i + 1], 2)}" for i in range(0, len(pts), 2))
        if encendidos.get(nombre) == 1:
            relleno, borde = SVG_ENCENDIDO, SVG_ENCENDIDO
        else:
            relleno, borde = SVG_APAGADO, SVG_BORDE_APAGADO
        partes.append(f'<polygon points="{coordenadas}" fill="{relleno}" stroke="{borde}" '
                      f'stroke-width="1"><title>{nombre}</title></polygon>')
    return partes


def _svg_envoltura(partes, ancho, alto, ancho_final):
    """Pone el encabezado <svg> con viewBox, escalado al ancho que se pidio."""
    if ancho_final is None:
        ancho_final = ancho
    alto_final = round(alto * ancho_final / ancho, 2)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" '
            f'width="{ancho_final}" height="{alto_final}">' + "".join(partes) + "</svg>")


def svg(tipo, encendidos, ancho=None):
    """Dibujo de UN digito (o de la barra, tipo "barra10") para el documento HTML.

    Existe para mostrar en el documento impreso que patron saca cada fila.
    `encendidos` es {segmento: 0/1} (p. ej. lo que devuelve segmentos()).
    Encendido en rojo oscuro, apagado en gris claro. `ancho` en pixeles
    escala el dibujo; por omision va a su tamano natural.
    """
    if tipo != "barra10":
        _revisar_tipo(tipo)
    _poligonos, w, h = geometria(tipo)
    return _svg_envoltura(_svg_poligonos(tipo, encendidos), w, h, ancho)


def svg_texto(cadena, tipo, con_punto=False, ancho=None):
    """Varios digitos lado a lado, uno por caracter de `cadena`.

    Existe para dibujar un mensaje completo en el documento. Lanza ValueError
    si algun caracter no existe en ese tipo.
    """
    digitos = texto(cadena, tipo, con_punto=con_punto)
    _poligonos, w, h = geometria(tipo)
    partes = []
    for k, encendidos in enumerate(digitos):
        partes += _svg_poligonos(tipo, encendidos, dx=k * w)
    total = max(1, len(digitos)) * w
    return _svg_envoltura(partes, total, h, ancho)
