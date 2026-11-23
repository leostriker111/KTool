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
    # VHDL-93 completo (IEEE 1076-1993, seccion 13.9) y lo que agrega VHDL-2008
    "abs", "access", "after", "alias", "all", "and", "architecture", "array",
    "assert", "attribute", "begin", "block", "body", "buffer", "bus", "case",
    "component", "configuration", "constant", "disconnect", "downto", "else",
    "elsif", "end", "entity", "exit", "file", "for", "function", "generate",
    "generic", "group", "guarded", "if", "impure", "in", "inertial", "inout",
    "is", "label", "library", "linkage", "literal", "loop", "map", "mod",
    "nand", "new", "next", "nor", "not", "null", "of", "on", "open", "or",
    "others", "out", "package", "port", "postponed", "procedure", "process",
    "pure", "range", "record", "register", "reject", "rem", "report", "return",
    "rol", "ror", "select", "severity", "shared", "signal", "sla", "sll", "sra",
    "srl", "subtype", "then", "to", "transport", "type", "unaffected", "units",
    "until", "use", "variable", "wait", "when", "while", "with", "xnor", "xor",
    "assume", "context", "cover", "default", "fairness", "force", "parameter",
    "property", "protected", "release", "restrict", "sequence", "strong",
    "vmode", "vprop", "vunit",
    # tipos y funciones de IEEE que el banco de prueba usa por nombre
    "bit", "boolean", "integer", "natural", "string", "std_logic", "unsigned",
    "to_unsigned", "now",
    # Verilog-2001 (IEEE 1364-2001, anexo B)
    "always", "assign", "automatic", "buf", "bufif0", "bufif1", "casex", "casez",
    "cell", "cmos", "config", "deassign", "defparam", "design", "disable", "edge",
    "endcase", "endconfig", "endfunction", "endgenerate", "endmodule",
    "endprimitive", "endspecify", "endtable", "endtask", "event", "forever",
    "fork", "genvar", "highz0", "highz1", "ifnone", "incdir", "include",
    "initial", "input", "instance", "join", "large", "liblist", "localparam",
    "macromodule", "medium", "module", "negedge", "nmos", "noshowcancelled",
    "notif0", "notif1", "output", "pmos", "posedge", "primitive", "pull0",
    "pull1", "pulldown", "pullup", "rcmos", "real", "realtime", "reg",
    "release", "repeat", "rnmos", "rpmos", "rtran", "rtranif0", "rtranif1",
    "scalared", "showcancelled", "signed", "small", "specify", "specparam",
    "strong0", "strong1", "supply0", "supply1", "task", "time", "tran",
    "tranif0", "tranif1", "tri", "tri0", "tri1", "triand", "trior", "trireg",
    "vectored", "wand", "weak0", "weak1", "wire", "wor",
    # los nombres que usan los archivos generados: una senal que se llamara
    # igual chocaria (en VHDL, sin importar mayusculas)
    "circuito", "tb_circuito", "combinacional", "prueba", "dut", "i", "fila",
    "errores", "x", "m",
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


def leer_pines(texto, placa):
    """'26, 28 33' -> [26, 28, 33]; 'rb0,RB1' -> ['RB0', 'RB1'].

    Cada placa nombra sus pines a su modo: numeros en ESP32, Pico y la MAX II,
    nombres de puerto en los PIC y la Blue Pill, y '13'/'A0' en Arduino (que se
    guardan como texto). Se lee al tipo que usa la placa.
    """
    numericos = all(isinstance(p, int) for p in placa["entradas"] + placa["salidas"])
    pines = []
    for ficha in texto.replace(",", " ").split():
        if numericos:
            if not ficha.isdigit():
                raise ValueError(f"en {placa['titulo']} los pines son numeros: {ficha!r}")
            pines.append(int(ficha))
        else:
            pines.append(ficha.upper())
    return pines


def con_pines(circuito, placa, pines):
    """La placa con los pines que pide el usuario: primero las entradas, en
    orden, y luego las salidas.

    Para las placas de practica, que traen LEDs y botones en pines fijos. Cada
    pin se revisa contra los utilizables de esa placa (los mismos de placas.py:
    nada de la flash del ESP32, de VCC/GND/JTAG de la MAX II, del PGC/PGD que no
    este de reserva...), y una salida no puede ir en un pin que solo es
    entrada. Lanza ValueError con el motivo; el aviso de un pin de reserva se
    conserva en la tabla de pines.
    """
    utilizables = list(dict.fromkeys(placa["entradas"] + placa["salidas"]))
    especiales = placa.get("pines_especiales", {})
    for p in pines:
        if p in especiales:
            raise ValueError(f"el pin {p} de {placa['titulo']} es {especiales[p]}. Usa otro")
        if p not in utilizables:
            fuera = f" ({placa['pines_fuera']})" if placa.get("pines_fuera") else ""
            # numeros en orden; los nombres (RB0, PA3, A0) en el orden de la placa
            lista = sorted(utilizables) if isinstance(p, int) else utilizables
            raise ValueError(
                f"el pin {p} no es utilizable en {placa['titulo']}{fuera}. Los que si: "
                + ", ".join(str(x) for x in lista))
    if len(set(pines)) != len(pines):
        raise ValueError(f"la lista de pines de {placa['titulo']} repite un pin")
    ne, ns = circuito.n_entradas, circuito.n_salidas
    if len(pines) != ne + ns:
        raise ValueError(
            f"para {placa['titulo']} diste {len(pines)} pines y el circuito tiene {ne} "
            f"entradas ({', '.join(circuito.entradas)}) y {ns} salidas "
            f"({', '.join(circuito.salidas)}): hacen falta {ne + ns}, primero las entradas")
    for p in pines[ne:]:
        if p in placa.get("solo_entrada", []):
            raise ValueError(f"el pin {p} de {placa['titulo']} solo sirve de entrada")
    propia = dict(placa)
    propia["entradas"] = list(pines[:ne])
    propia["salidas"] = list(pines[ne:])
    return propia


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
