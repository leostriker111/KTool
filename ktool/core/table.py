"""Tabla de verdad y utilidades de bases numericas."""

from __future__ import annotations

DC = "x"  # don't care

MIN_VARS = 2
MAX_VARS = 6
MAX_OUTPUTS = 32

VAR_NAMES = ["A", "B", "C", "D", "E", "F"]


def validar_nvars(n):
    """Numero de variables admitido. Lanza ValueError con el motivo."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError(f"el numero de variables debe ser entero (recibi {n!r})")
    if n < MIN_VARS or n > MAX_VARS:
        raise ValueError(
            f"el numero de variables debe estar entre {MIN_VARS} y {MAX_VARS}; pediste {n}"
        )
    return n


def validar_indices(indices, nvars, que="mintermino"):
    """Todos los indices tienen que caer dentro de la tabla."""
    limite = 1 << nvars
    for i in indices:
        if not 0 <= i < limite:
            raise ValueError(
                f"el {que} {i} no existe con {nvars} variables "
                f"(validos: 0 a {limite - 1})"
            )
    return list(indices)


def default_vars(n):
    return VAR_NAMES[:validar_nvars(n)]


def parse_value(tok):
    """0 / 1 / x (don't care). Devuelve 0, 1 o 'x'."""
    t = str(tok).strip().lower()
    if t in ("x", "-", "d", "dc"):
        return DC
    if t in ("0", "1"):
        return int(t)
    raise ValueError(f"valor de salida invalido: {tok!r} (usa 0, 1 o x)")


def parse_int_token(tok):
    """Acepta decimal, 0x.. hex, 0b.. bin, 0o.. octal."""
    t = str(tok).strip()
    return int(t, 0)


def parse_index_list(text):
    """'1,3,5' o '0x1 0b11 5' -> lista de ints."""
    if not text:
        return []
    raw = text.replace(",", " ").split()
    return [parse_int_token(t) for t in raw]


def parse_truth_string(s):
    """'01x101..' -> lista de 0/1/'x'. Tambien admite separadores."""
    s = "".join(c for c in str(s) if not c.isspace())
    return [parse_value(c) for c in s]


class TruthTable:
    """n variables, 2^n filas, una o varias salidas, columna de notas opcional."""

    def __init__(self, nvars, variables=None, outputs=None, notes=None):
        self.nvars = validar_nvars(nvars)
        self.rows = 1 << nvars
        self.variables = list(variables) if variables else default_vars(nvars)
        # outputs: dict nombre -> lista de 0/1/'x' (largo = rows)
        self.outputs = {}
        if outputs:
            for name, vals in outputs.items():
                self.set_output(name, vals)
        self.notes = list(notes) if notes else [""] * self.rows

    # -- construccion --
    def set_output(self, name, values):
        vals = [parse_value(v) for v in values]
        if len(vals) != self.rows:
            raise ValueError(
                f"la salida {name!r} tiene {len(vals)} valores, se esperaban {self.rows}"
            )
        self.outputs[name] = vals

    @classmethod
    def from_minterms(cls, nvars, minterms, dontcares=None, name="Y", variables=None):
        validar_nvars(nvars)
        dontcares = list(dontcares or [])
        validar_indices(minterms, nvars, "mintermino")
        validar_indices(dontcares, nvars, "don't care")
        repetidos = sorted(set(minterms) & set(dontcares))
        if repetidos:
            raise ValueError(
                "estos indices estan en minterminos y en don't cares a la vez: "
                + ", ".join(str(i) for i in repetidos)
            )
        vals = [0] * (1 << nvars)
        for m in minterms:
            vals[m] = 1
        for d in dontcares:
            vals[d] = DC
        return cls(nvars, variables, {name: vals})

    @classmethod
    def from_expression(cls, expr_text, nvars=None, name="Y"):
        from .ast import build_output

        variables, vals = build_output(expr_text, nvars)
        if len(variables) > MAX_VARS:
            raise ValueError(
                f"la expresion usa {len(variables)} variables "
                f"({', '.join(variables)}); el maximo son {MAX_VARS} (A a {VAR_NAMES[-1]})"
            )
        return cls(len(variables), variables, {name: vals})

    # -- consultas por salida --
    def minterms(self, name):
        return [i for i, v in enumerate(self.outputs[name]) if v == 1]

    def maxterms(self, name):
        return [i for i, v in enumerate(self.outputs[name]) if v == 0]

    def dontcares(self, name):
        return [i for i, v in enumerate(self.outputs[name]) if v == DC]

    def bits(self, index):
        """Bits de las variables para una fila (MSB = variables[0])."""
        return [(index >> (self.nvars - 1 - k)) & 1 for k in range(self.nvars)]
