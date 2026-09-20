"""Gramatica de nodos y evaluacion.

Gramatica (tuplas):
    ('var', nombre)
    ('const', 0|1)
    ('not', a)
    ('and', a, b)
    ('or', a, b)
    ('xor', a, b)
"""

from __future__ import annotations

from .parser import parse


def collect_vars(node, acc):
    if node[0] == "var":
        acc.add(node[1])
    elif node[0] in ("not",):
        collect_vars(node[1], acc)
    elif node[0] in ("and", "or", "xor"):
        collect_vars(node[1], acc)
        collect_vars(node[2], acc)


def evaluate(node, env):
    k = node[0]
    if k == "var":
        return env[node[1]]
    if k == "const":
        return node[1]
    if k == "not":
        return 1 - evaluate(node[1], env)
    a = evaluate(node[1], env)
    if k == "and":
        return a & evaluate(node[2], env)
    if k == "or":
        return a | evaluate(node[2], env)
    if k == "xor":
        return a ^ evaluate(node[2], env)
    raise ValueError(f"nodo desconocido: {k}")


def build_output(text, nvars=None):
    """Devuelve (variables_ordenadas, valores) para todas las combinaciones.

    Las variables de una tabla de verdad son letras sueltas: `AB` es A AND B.
    """
    ast = parse(text, letras_sueltas=True)
    found = set()
    collect_vars(ast, found)
    variables = sorted(found)
    from .table import MIN_VARS, VAR_NAMES

    # rellena con variables sin usar para respetar el tamano pedido, y nunca
    # baja del minimo (una expresion de una sola letra sigue dando una tabla)
    objetivo = max(nvars or 0, MIN_VARS)
    if objetivo > len(variables):
        extra = [v for v in VAR_NAMES if v not in variables][: objetivo - len(variables)]
        variables = sorted(variables + extra)
    n = len(variables)
    vals = []
    for i in range(1 << n):
        env = {variables[k]: (i >> (n - 1 - k)) & 1 for k in range(n)}
        vals.append(evaluate(ast, env))
    return variables, vals
