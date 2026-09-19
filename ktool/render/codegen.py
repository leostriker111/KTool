"""Traductor de ecuaciones a varios lenguajes de descripcion.

Pipeline:  Solution/texto  ->  AST (tuplas de core/ast.py)  ->  emit(node, lang).

A diferencia del viejo dict SPECS (una plantilla hardcodeada por forma y por
lenguaje), aqui hay UNA sola fuente de verdad: el emisor recursivo `emit` recorre
el AST y decide los parentesis por PRECEDENCIA (NOT > AND > XOR > OR), no por caso.
Lo unico por-lenguaje son DATOS (OPS): los simbolos de cada operador.

Beneficio: ademas de los resultados minimizados (solution_to_ast), se puede
traducir CUALQUIER expresion que el usuario escriba (translate), porque todo pasa
por el mismo emisor.
"""

from __future__ import annotations

from ..core.parser import parse
from ..core.simplify import literal_pairs

LANG_ORDER = ["Matematico", "Verilog", "VHDL", "ABEL", "Logisim", "C", "Python", "LaTeX"]

# Alias de entrada (CLI) -> nombre canonico. Vive junto a LANG_ORDER (H6 del plan).
LANG_ALIASES = {
    "mate": "Matematico", "matematico": "Matematico", "math": "Matematico",
    "verilog": "Verilog", "v": "Verilog",
    "vhdl": "VHDL",
    "abel": "ABEL",
    "logisim": "Logisim",
    "c": "C",
    "python": "Python", "py": "Python",
    "latex": "LaTeX", "tex": "LaTeX",
}

# Precedencia: mayor = liga mas fuerte. NOT > AND > XOR > OR (igual que el parser).
PREC = {"or": 1, "xor": 2, "and": 3, "not": 4, "var": 5, "const": 5}

# OPS: SOLO datos por lenguaje.
#   and/or/xor -> separador infijo
#   not        -> estilo de la negacion:
#                   ("prefix", tok)   ~A , not (A and B)
#                   ("postfix", tok)  A' , (AB)'
#                   ("wrap", izq, der) \overline{A}
#   const      -> repr de 0 y 1
#   assign     -> plantilla con {name} y {rhs}
OPS = {
    "Matematico": {
        "and": "", "or": " + ", "xor": " ^ ",
        "not": ("postfix", "'"),
        "const": {0: "0", 1: "1"},
        "assign": "{name} = {rhs}",
    },
    "Verilog": {
        "and": " & ", "or": " | ", "xor": " ^ ",
        "not": ("prefix", "~"),
        "const": {0: "1'b0", 1: "1'b1"},
        "assign": "assign {name} = {rhs};",
    },
    "VHDL": {
        "and": " and ", "or": " or ", "xor": " xor ",
        "not": ("prefix", "not "),
        "const": {0: "'0'", 1: "'1'"},
        "assign": "{name} <= {rhs};",
    },
    "ABEL": {
        "and": " & ", "or": " # ", "xor": " $ ",
        "not": ("prefix", "!"),
        "const": {0: "0", 1: "1"},
        "assign": "{name} = {rhs};",
    },
    "Logisim": {
        "and": " ", "or": " + ", "xor": " ^ ",
        "not": ("prefix", "~"),
        "const": {0: "0", 1: "1"},
        "assign": "{name} = {rhs}",
    },
    "C": {
        "and": " && ", "or": " || ", "xor": " ^ ",
        "not": ("prefix", "!"),
        "const": {0: "0", 1: "1"},
        "assign": "bool {name} = {rhs};",
    },
    "Python": {
        "and": " and ", "or": " or ", "xor": " ^ ",
        "not": ("prefix", "not "),
        "const": {0: "0", 1: "1"},
        "assign": "{name} = {rhs}",
    },
    "LaTeX": {
        "and": "", "or": " + ", "xor": " \\oplus ",
        "not": ("wrap", "\\overline{", "}"),
        "const": {0: "0", 1: "1"},
        "assign": "{name} = {rhs}",
    },
}


# ------------------------------------------------------------------ emisor

def _not_paren(child, inner):
    """Parentesis del operando de NOT: solo si liga mas debil (precedencia)."""
    return "(" + inner + ")" if PREC[child[0]] < PREC["not"] else inner


def _operand(child, inner, parent_op, ops):
    """Parentiza un operando de un binario.

    Regla: (1) por correccion, si el hijo liga mas debil que el padre;
           (2) por legibilidad, si el hijo es un termino compuesto de OTRO
               operador cuyo simbolo es explicito (ej '&', 'or'). En notacion
               por yuxtaposicion (Matematico ''/LaTeX/Logisim ' ') no se envuelve,
               porque el termino ya se lee como un bloque.
    """
    ck = child[0]
    if PREC[ck] < PREC[parent_op]:
        return "(" + inner + ")"
    if ck in ("and", "or", "xor") and ck != parent_op and ops[ck].strip():
        return "(" + inner + ")"
    return inner


def emit(node, lang):
    """Recorre el AST y produce el codigo en `lang`."""
    ops = OPS[lang]
    kind = node[0]

    if kind == "const":
        return ops["const"][node[1]]
    if kind == "var":
        return node[1]
    if kind == "not":
        child = node[1]
        inner = emit(child, lang)
        style = ops["not"]
        if style[0] == "prefix":
            return style[1] + _not_paren(child, inner)
        if style[0] == "postfix":
            return _not_paren(child, inner) + style[1]
        # wrap: las llaves ya agrupan, no hace falta parentesis extra
        return style[1] + inner + style[2]
    if kind in ("and", "or", "xor"):
        sep = ops[kind]
        parts = [_operand(c, emit(c, lang), kind, ops) for c in (node[1], node[2])]
        return sep.join(parts)
    raise ValueError(f"nodo desconocido: {kind}")


# ------------------------------------------------------ Solution -> AST

def _chain(op, nodes):
    """Encadena nodos binarios asociativos: [a,b,c] -> (op,a,(op,b,c))."""
    node = nodes[-1]
    for left in reversed(nodes[:-1]):
        node = (op, left, node)
    return node


def _literal(v, comp):
    return ("not", ("var", v)) if comp else ("var", v)


def solution_to_ast(solution):
    """Convierte una Solution minimizada en un AST (la unica costura con codegen)."""
    if solution.const is not None:
        return ("const", solution.const)

    if solution.form == "xor":
        body = _chain("xor", [("var", v) for v in solution.xor_vars])
        return ("not", body) if solution.xnor else body

    if solution.form in ("nand", "nor"):
        # NAND(NAND(T1), NAND(T2), ...) -> not(and(not(and(T1)), ...))
        op = "and" if solution.form == "nand" else "or"
        invertir = solution.form == "nor"
        internos = []
        for p in solution.patterns:
            lits = [_literal(v, c) for v, c in
                    literal_pairs(p, solution.variables, polarity_invert=invertir)]
            internos.append(("not", _chain(op, lits)) if lits else ("const", 0))
        if not internos:
            return ("const", 0 if solution.form == "nand" else 1)
        return ("not", _chain(op, internos))

    if solution.form == "sop":
        if not solution.patterns:
            return ("const", 0)
        terms = []
        for p in solution.patterns:
            lits = [_literal(v, c) for v, c in literal_pairs(p, solution.variables)]
            terms.append(_chain("and", lits) if lits else ("const", 1))
        return _chain("or", terms)

    # pos
    if not solution.patterns:
        return ("const", 1)
    terms = []
    for p in solution.patterns:
        lits = [_literal(v, c) for v, c in literal_pairs(p, solution.variables, polarity_invert=True)]
        terms.append(_chain("or", lits) if lits else ("const", 0))
    return _chain("and", terms)


# ------------------------------------------------------------- API publica

def render(solution, name, lang):
    """Emite la asignacion de una Solution minimizada en `lang`."""
    rhs = emit(solution_to_ast(solution), lang)
    return OPS[lang]["assign"].format(name=name, rhs=rhs)


def render_all(solution, name):
    """Devuelve lista de (lenguaje, codigo) para la solucion dada."""
    return [(lang, render(solution, name, lang)) for lang in LANG_ORDER]


def translate(expr_text, name, lang):
    """Traduce una expresion libre (matematico) directo a `lang`, sin minimizar."""
    rhs = emit(parse(expr_text), lang)
    return OPS[lang]["assign"].format(name=name, rhs=rhs)
