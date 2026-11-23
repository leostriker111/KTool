"""Tablas de excitacion de flip-flops.

Dado el bit actual q y el bit siguiente qn de un flip-flop, cada tipo dice que
valor necesitan sus entradas. Las 'x' (don't care) son lo que hace que las
tablas JK/SR salgan cortas al minimizar.
"""

from __future__ import annotations

# kind -> (entradas, tabla {(q, qn): [valores en orden de entradas]})
_FF = {
    "D": (
        ["D"],
        {(0, 0): [0], (0, 1): [1], (1, 0): [0], (1, 1): [1]},
    ),
    "T": (
        ["T"],
        {(0, 0): [0], (0, 1): [1], (1, 0): [1], (1, 1): [0]},
    ),
    "JK": (
        ["J", "K"],
        {(0, 0): [0, "x"], (0, 1): [1, "x"], (1, 0): ["x", 1], (1, 1): ["x", 0]},
    ),
    "SR": (
        ["S", "R"],
        {(0, 0): [0, "x"], (0, 1): [1, 0], (1, 0): [0, 1], (1, 1): ["x", 0]},
    ),
}

KINDS = list(_FF)


def normalize(kind):
    k = str(kind).strip().upper()
    if k not in _FF:
        raise ValueError(f"flip-flop desconocido: {kind!r} (usa {', '.join(KINDS)})")
    return k


def inputs(kind):
    """Letras de las entradas del flip-flop, p.ej. ['J', 'K']."""
    return list(_FF[normalize(kind)][0])


def excite(kind, q, qn):
    """Valores de excitacion para la transicion q->qn (orden de inputs())."""
    return list(_FF[normalize(kind)][1][(int(q), int(qn))])
