"""Lo que todos los generadores de hardware comparten: el circuito ya resuelto,
la ecuacion escrita en cada lenguaje y el reparto de pines.

Un generador (PIC, ESP32, VHDL...) no minimiza nada ni decide pines por su
cuenta: recibe un `Circuito` y le pide a `asignar_pines` el acomodo. Asi la
ecuacion que corre en el PIC es, caracter por caracter de logica, la misma que
corre en la FPGA y en la simulacion de Python.
"""

from __future__ import annotations

import re

from ..core.simplify import solve_output
from ..render.codegen import solution_to_ast

# Formas que el usuario puede pedir con --form. 'auto' y 'both' usan la mas
# barata en compuertas (la que la tarea escrita llama "recomendada").
FORMAS = ("sop", "pos", "nand", "nor")

# Palabras que no pueden ser nombre de senal en alguno de los lenguajes que se
# generan (C, C++, Python, VHDL, Verilog, CUPL). Se comparan en minusculas
# porque VHDL y CUPL no distinguen mayusculas.
RESERVADAS = {
    # VHDL
    "abs", "and", "begin", "bit", "case", "else", "end", "entity", "for", "if",
    "in", "inout", "is", "loop", "mod", "nand", "nor", "not", "of", "or", "out",
    "port", "process", "rem", "signal", "then", "to", "type", "wait", "when",
    "while", "with", "xnor", "xor", "architecture", "library", "use", "all",
    "others", "range", "downto", "buffer", "map", "open", "null", "on",
    # Verilog
    "assign", "module", "endmodule", "input", "output", "wire", "reg", "always",
    "initial", "integer",
    # C / C++ / Python
    "int", "char", "void", "return", "do", "def", "class", "true", "false",
    "none", "pass", "import", "from", "as", "elif", "try", "lambda", "global",
    # CUPL
    "pin", "name", "device", "field", "table", "min", "date", "partno",
    "revision", "designer", "company", "assembly", "location", "append",
    # pines y registros que ya existen como nombre en los compiladores
    "high", "low", "input_pullup", "led_builtin",
}

_IDENTIFICADOR = re.compile(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)*$")


def validar_nombres(entradas, salidas):
    """Cada senal tiene que ser un nombre valido en TODOS los lenguajes.

    Se revisa aqui una sola vez, para que ningun generador escriba un archivo
    que luego no compile. Lanza ValueError con el motivo.
    """
    vistos = {}
    for nombre in list(entradas) + list(salidas):
        if not _IDENTIFICADOR.match(nombre):
            raise ValueError(
                f"la senal {nombre!r} no sirve como nombre en VHDL/Verilog/C: usa "
                "letras, numeros y '_' sueltos, empezando con letra")
        if nombre.lower() in RESERVADAS:
            raise ValueError(
                f"la senal {nombre!r} es una palabra reservada en alguno de los "
                "lenguajes que se generan; cambiale el nombre (ej. con --name)")
        clave = nombre.lower()
        if clave in vistos:
            raise ValueError(
                f"las senales {vistos[clave]!r} y {nombre!r} chocan: VHDL y CUPL no "
                "distinguen mayusculas, y una entrada no puede llamarse igual que "
                "una salida")
        vistos[clave] = nombre


class Circuito:
    """Una tabla de verdad ya minimizada, lista para llevar a hardware.

    entradas   ['A', 'B', ...] en el orden de la tabla (A es el bit mas alto)
    salidas    ['Y', ...]
    esperado   {salida: [0, 1, 'x', ...]} la tabla original, con los don't care
    elegidas   {salida: Solution} la forma que se implementa
    arboles    {salida: AST} la misma ecuacion como arbol (core/ast.py)
    soluciones {salida: dict de solve_output} todas las formas, para quien las
               necesite (la GAL cuenta terminos SOP, el TTL compara chips)
    """

    def __init__(self, tabla, forma="auto", nombre="circuito"):
        self.nombre = nombre
        self.entradas = list(tabla.variables)
        self.salidas = list(tabla.outputs)
        validar_nombres(self.entradas, self.salidas)
        self.esperado = {n: list(v) for n, v in tabla.outputs.items()}
        self.tabla = tabla
        self.soluciones = {n: solve_output(v, self.entradas)
                           for n, v in tabla.outputs.items()}
        self.elegidas = {}
        for n, sol in self.soluciones.items():
            self.elegidas[n] = sol[forma] if forma in FORMAS else sol["best"]
        self.arboles = {n: solution_to_ast(s) for n, s in self.elegidas.items()}

    @property
    def n_entradas(self):
        return len(self.entradas)

    @property
    def n_salidas(self):
        return len(self.salidas)

    def filas(self):
        """Las 2^n combinaciones como (indice, {entrada: 0/1}), A como bit alto."""
        n = self.n_entradas
        for i in range(1 << n):
            yield i, {v: (i >> (n - 1 - k)) & 1 for k, v in enumerate(self.entradas)}


# ---------------------------------------------------------------- la ecuacion

# Los simbolos de cada lenguaje. NOT se escribe aparte porque cambia de forma.
SIMBOLOS = {
    "c":       {"and": " & ", "or": " | ", "xor": " ^ ", 0: "0", 1: "1"},
    "python":  {"and": " & ", "or": " | ", "xor": " ^ ", 0: "0", 1: "1"},
    "verilog": {"and": " & ", "or": " | ", "xor": " ^ ", 0: "1'b0", 1: "1'b1"},
    "vhdl":    {"and": " and ", "or": " or ", "xor": " xor ", 0: "'0'", 1: "'1'"},
    "cupl":    {"and": " & ", "or": " # ", "xor": " $ ", 0: "'b'0", 1: "'b'1"},
}


def _negar(texto, lenguaje):
    """NOT de un operando que ya viene entre parentesis o es un nombre suelto."""
    if lenguaje == "c":
        return "!" + texto
    if lenguaje == "python":
        # `not` de Python liga MAS DEBIL que `&` y `^`: "not A ^ B" es
        # "not (A ^ B)". Con bits 0/1, x ^ 1 niega sin esa trampa.
        return "(" + texto + " ^ 1)"
    if lenguaje == "verilog":
        return "~" + texto
    if lenguaje == "vhdl":
        return "not " + texto
    return "!" + texto  # cupl


def ecuacion(arbol, lenguaje, prefijo=""):
    """Escribe el arbol en `lenguaje` poniendo parentesis en TODA operacion.

    El emisor de la seccion de lenguajes (render/codegen.py) quita parentesis
    por precedencia, y eso es justo lo que aqui no conviene: cada lenguaje
    ordena distinto (en C y en Python `^` liga mas fuerte que en la tabla de
    ktool, en VHDL mezclar and/or sin parentesis ni compila). Con todo entre
    parentesis la ecuacion significa lo mismo en los cinco.

    `prefijo` se antepone a cada variable (ej. 'in_' para que en C no choque
    con ningun macro de los compiladores).
    """
    simb = SIMBOLOS[lenguaje]
    tipo = arbol[0]
    if tipo == "const":
        return simb[arbol[1]]
    if tipo == "var":
        return prefijo + arbol[1]
    if tipo == "not":
        hijo = arbol[1]
        texto = ecuacion(hijo, lenguaje, prefijo)
        if hijo[0] in ("and", "or", "xor"):
            texto = "(" + texto + ")"
        return _negar(texto, lenguaje)
    if tipo in ("and", "or", "xor"):
        partes = []
        for hijo in (arbol[1], arbol[2]):
            texto = ecuacion(hijo, lenguaje, prefijo)
            if hijo[0] in ("and", "or", "xor"):
                texto = "(" + texto + ")"
            elif hijo[0] == "not" and lenguaje == "c":
                # "!A & B" ya es (!A) & B, pero los compiladores avisan
                # (-Wlogical-not-parentheses). Con parentesis no hay duda.
                texto = "(" + texto + ")"
            partes.append(texto)
        return simb[tipo].join(partes)
    raise ValueError(f"nodo desconocido en la ecuacion: {tipo}")


# ------------------------------------------------------------ el reparto

class Bloqueo(Exception):
    """La placa no alcanza para el circuito. El mensaje dice por que."""


def asignar_pines(circuito, placa):
    """Reparte entradas y salidas en los pines de `placa` (un dict de placas.py).

    Devuelve una lista de renglones {senal, pin, direccion, aviso}, primero las
    entradas y luego las salidas. Si no alcanzan los pines lanza Bloqueo con
    la cuenta exacta, en vez de generar codigo que no se puede armar.
    """
    solo_entrada = set(placa.get("solo_entrada", []))
    reserva = placa.get("reserva", {})
    utilizables = []
    for pin in list(placa["entradas"]) + list(placa["salidas"]):
        if pin not in utilizables:
            utilizables.append(pin)
    seguros = [p for p in utilizables if p not in reserva]
    ne, ns = circuito.n_entradas, circuito.n_salidas

    def motivo():
        detalle = (f"{len(seguros)} seguros + {len(utilizables) - len(seguros)} de reserva"
                   if len(seguros) != len(utilizables) else f"{len(seguros)} seguros")
        return (f"requiere {ne} entradas + {ns} salidas = {ne + ns} pines y "
                f"{placa['titulo']} solo tiene {len(utilizables)} utilizables ({detalle})")

    if ne > len(placa["entradas"]):
        raise Bloqueo(f"requiere {ne} entradas y {placa['titulo']} solo tiene "
                      f"{len(placa['entradas'])} pines de entrada; " + motivo())

    renglones = []
    usados = set()
    for senal, pin in zip(circuito.entradas, placa["entradas"]):
        usados.add(pin)
        renglones.append({"senal": senal, "pin": pin, "direccion": "entrada",
                          "aviso": reserva.get(pin, "")})

    libres = [p for p in placa["salidas"] if p not in usados and p not in solo_entrada]
    # sin repetir (una lista de salidas puede volver a nombrar un pin)
    vistos = []
    for p in libres:
        if p not in vistos:
            vistos.append(p)
    if ns > len(vistos):
        raise Bloqueo(motivo())
    for senal, pin in zip(circuito.salidas, vistos):
        renglones.append({"senal": senal, "pin": pin, "direccion": "salida",
                          "aviso": reserva.get(pin, "")})
    return renglones


def tabla_de_pines(renglones, comentario, pata=None):
    """La tabla de mapeo como comentario del lenguaje (`//`, `--`, `#`, `/*`).

    `pata` es una funcion opcional pin -> texto de la pata fisica.
    """
    filas = [("Senal", "Pin", "Direccion", "Nota")]
    for r in renglones:
        pin = str(r["pin"]) if pata is None else pata(r["pin"])
        filas.append((r["senal"], pin, r["direccion"], r["aviso"]))
    anchos = [max(len(f[i]) for f in filas) for i in range(3)]
    lineas = []
    for k, f in enumerate(filas):
        texto = "  ".join(f[i].ljust(anchos[i]) for i in range(3))
        if f[3]:
            texto += "  " + f[3]
        lineas.append(f"{comentario} {texto}".rstrip())
        if k == 0:
            lineas.append(f"{comentario} " + "  ".join("-" * a for a in anchos))
    return "\n".join(lineas)
