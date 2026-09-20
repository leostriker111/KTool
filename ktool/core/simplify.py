"""Formato de ecuaciones, deteccion XOR/XNOR, reuso de terminos y costo."""

from __future__ import annotations

from . import qm


def literal_pairs(pattern, variables, polarity_invert=False):
    """Patron '10-1' -> lista de (variable, es_complemento)."""
    out = []
    for i, c in enumerate(pattern):
        if c == "-":
            continue
        v = variables[i]
        one_is_true = (c == "1") != polarity_invert
        out.append((v, not one_is_true))
    return out


def term_literals(pattern, variables, polarity_invert=False):
    """Patron '10-1' -> lista de literales. polarity_invert para sumandos POS."""
    return [
        v + "'" if comp else v
        for v, comp in literal_pairs(pattern, variables, polarity_invert)
    ]


def complemento(literal):
    """A -> A' ; A' -> A. La inversion de un literal, sin compuerta de por medio."""
    return literal[:-1] if literal.endswith("'") else literal + "'"


def format_product(pattern, variables):
    lits = term_literals(pattern, variables)
    return "".join(lits) if lits else "1"


def format_sum(pattern, variables):
    lits = term_literals(pattern, variables, polarity_invert=True)
    return "(" + " + ".join(lits) + ")" if lits else "0"


class Solution:
    """Resultado de minimizar una salida en una forma (SOP o POS)."""

    FORMAS = ("sop", "pos", "xor", "nand", "nor")

    def __init__(self, form, patterns, variables, const=None, xor_vars=None, xnor=False):
        # 'nand' son los patrones del SOP armados con puras NAND; 'nor', los del
        # POS con puras NOR. Misma funcion, otra realizacion.
        self.form = form
        self.patterns = patterns
        self.variables = variables
        self.const = const  # 0 / 1 cuando es constante
        self.xor_vars = xor_vars or []
        self.xnor = xnor

    @property
    def es_universal(self):
        """NAND-only o NOR-only: una sola clase de compuerta para todo."""
        return self.form in ("nand", "nor")

    def terminos(self):
        """Los terminos como listas de literales."""
        invertir = self.form in ("pos", "nor")
        return [term_literals(p, self.variables, polarity_invert=invertir) or ["1"]
                for p in self.patterns]

    def _ecuacion_universal(self):
        """Y = NAND(NAND(T1), NAND(T2), ...), escrito a la manera del proyecto.

        NAND de n entradas es el complemento del producto, asi que el NAND de los
        NAND por termino devuelve la suma de los terminos. Dual para NOR.
        """
        terminos = self.terminos()
        junta = "".join if self.form == "nand" else lambda xs: " + ".join(xs)

        internos = []
        for t in terminos:
            if len(t) == 1:
                # un literal suelto: se invierte, sin parentesis de por medio
                internos.append(complemento(t[0]))
            else:
                internos.append("(" + junta(t) + ")'")

        if len(internos) == 1:
            # un solo termino: la segunda compuerta deshace la primera
            unico = internos[0]
            return f"({unico})'" if unico.startswith("(") else complemento(unico)
        return "(" + junta(internos) + ")'"

    @property
    def equation(self):
        if self.const is not None:
            return str(self.const)
        if self.form == "xor":
            body = " ^ ".join(self.xor_vars)
            return f"({body})'" if self.xnor else body
        if not self.patterns:
            return "0" if self.form in ("sop", "nand") else "1"
        if self.es_universal:
            return self._ecuacion_universal()
        if self.form == "sop":
            terms = [format_product(p, self.variables) for p in self.patterns]
            return " + ".join(terms)
        terms = [format_sum(p, self.variables) for p in self.patterns]
        return "".join(terms)

    def cost(self):
        """(compuertas, literales) aprox. Para elegir la forma mas barata."""
        if self.const is not None:
            return (0, 0)
        if self.form == "xor":
            k = len(self.xor_vars)
            return (max(0, k - 1) + (1 if self.xnor else 0), k)
        if not self.patterns:
            return (0, 0)
        if self.es_universal:
            terminos = self.terminos()
            literales = sum(len(t) for t in terminos)
            if len(terminos) == 1 and len(terminos[0]) == 1:
                return (0, literales)  # Y = un literal: no hace falta compuerta
            # una compuerta por termino (la de un literal es un inversor) y la final
            return (len(terminos) + 1, literales)
        literals = sum(qm.literal_count(p) for p in self.patterns)
        multi = [p for p in self.patterns if qm.literal_count(p) > 1]
        inner_gates = len(multi)  # AND (sop) u OR (pos) de >1 literal
        outer = 1 if len(self.patterns) > 1 else 0
        return (inner_gates + outer, literals)


def solve_output(values, variables):
    """Devuelve dict con soluciones SOP y POS y la recomendada por costo."""
    nbits = len(variables)
    minterms = [i for i, v in enumerate(values) if v == 1]
    zeros = [i for i, v in enumerate(values) if v == 0]
    dontcares = [i for i, v in enumerate(values) if v == "x"]

    if not minterms:
        sop = Solution("sop", [], variables, const=0)
        pos = Solution("pos", [], variables, const=0)
    elif not zeros:
        sop = Solution("sop", [], variables, const=1)
        pos = Solution("pos", [], variables, const=1)
    else:
        sop_pat = qm.minimize(minterms, dontcares, nbits, required=minterms)
        pos_pat = qm.minimize(zeros, dontcares, nbits, required=zeros)
        sop = Solution("sop", sop_pat, variables)
        pos = Solution("pos", pos_pat, variables)

    parity = detect_parity(values, variables)
    xor = None
    if parity:
        xor = Solution(
            "xor", [], variables,
            xor_vars=parity["subset"], xnor=parity["xnor"],
        )

    # realizaciones con una sola clase de compuerta. No compiten por 'best':
    # en compuertas casi nunca ganan, y su ventaja real es en encapsulados, que
    # es cosa del protoboard. El usuario decide cual usa.
    if sop.const is not None:
        nand = Solution("nand", [], variables, const=sop.const)
        nor = Solution("nor", [], variables, const=pos.const)
    else:
        nand = Solution("nand", sop.patterns, variables)
        nor = Solution("nor", pos.patterns, variables)

    candidates = [("sop", sop), ("pos", pos)]
    if xor is not None:
        candidates.append(("xor", xor))
    # menor costo; en empate gana sop, luego pos, luego xor
    order = {"sop": 0, "pos": 1, "xor": 2}
    best = min(candidates, key=lambda kv: (kv[1].cost(), order[kv[0]]))[1]

    return {
        "sop": sop,
        "pos": pos,
        "xor": xor,
        "nand": nand,
        "nor": nor,
        "best": best,
        "parity": parity,
    }


def detect_parity(values, variables):
    """Si la funcion es XOR/XNOR de un subconjunto de variables, lo regresa.
    Devuelve dict {subset: [nombres], xnor: bool, equation: str} o None."""
    n = len(variables)
    cares = [(i, v) for i, v in enumerate(values) if v in (0, 1)]
    if not cares:
        return None
    best = None
    for subset in range(1, 1 << n):
        mask = 0
        for k in range(n):
            if (subset >> k) & 1:
                mask |= 1 << (n - 1 - k)
        ok_xor = ok_xnor = True
        for i, v in cares:
            parity = bin(i & mask).count("1") & 1
            if v != parity:
                ok_xor = False
            if v != (parity ^ 1):
                ok_xnor = False
            if not ok_xor and not ok_xnor:
                break
        if ok_xor or ok_xnor:
            cnt = bin(subset).count("1")
            if cnt >= 2 and (best is None or cnt < best[0]):
                names = [variables[k] for k in range(n) if (subset >> k) & 1]
                best = (cnt, names, ok_xnor and not ok_xor)
    if best is None:
        return None
    _, names, is_xnor = best
    body = " ^ ".join(names)
    eq = f"({body})'" if is_xnor else body
    return {"subset": names, "xnor": is_xnor, "equation": eq}


def shared_terms(solutions, variables, form="sop"):
    """Encuentra patrones que aparecen en >=2 salidas (compuertas reutilizables).
    solutions = dict nombre_salida -> dict de solve_output."""
    seen = {}
    for out_name, sol in solutions.items():
        s = sol[form]
        if s.const is not None:
            continue
        for p in s.patterns:
            if qm.literal_count(p) < 2:
                continue  # un literal no es compuerta reutilizable
            seen.setdefault(p, []).append(out_name)
    shared = []
    for p, outs in seen.items():
        if len(outs) >= 2:
            text = format_product(p, variables) if form == "sop" else format_sum(p, variables)
            shared.append({"pattern": p, "outputs": outs, "term": text})
    shared.sort(key=lambda d: (-len(d["outputs"]), d["term"]))
    return shared
