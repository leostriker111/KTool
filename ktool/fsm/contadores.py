"""Contadores sincronos como maquinas de estado: lo que piden casi todas las
practicas de circuitos secuenciales.

Un contador se describe por lo que hace en cada combinacion de sus entradas de
control (X, Y...). Cada modo es una de estas:

    lista de numeros   la secuencia a recorrer, ej. [4, 7, 2, 6, 0, 3, 5, 1]
    "paro"             se queda en el numero donde esta
    "reinicio"         vuelve al primer numero del primer modo
    "set"              todos los flip-flops a 1 (el numero mas alto)

y `contador()` arma la maquina (Moore). El codigo de cada estado ES el numero
que muestra, asi que las salidas del contador son los propios flip-flops
(Q3 Q2 Q1 Q0) y lo que no aparece en ninguna secuencia queda como no importa.

Cuando un modo de secuencia arranca desde un numero que no esta en su lista
(ej. va en 5 y cambian a "multiplos de 4"), salta al primero de esa lista. Es
la convencion que se usa a mano en las tablas de transicion de las practicas,
y el reporte lo dice para que no sea una sorpresa.
"""

from __future__ import annotations

from .machine import Machine


def ascendente(modulo, desde=0):
    """[0, 1, ..., modulo-1] (o desde otro numero)."""
    return list(range(desde, desde + modulo))


def descendente(modulo):
    """[modulo-1, ..., 1, 0]"""
    return list(range(modulo - 1, -1, -1))


def multiplos(de, hasta, cuantos=None):
    """Multiplos de `de` hasta `hasta` (incluido), ej. multiplos(4, 15) = [0, 4, 8, 12]."""
    lista = list(range(0, hasta + 1, de))
    return lista[:cuantos] if cuantos else lista


def primos(hasta):
    return [n for n in range(2, hasta + 1) if all(n % d for d in range(2, int(n ** 0.5) + 1))]


def _bits_necesarios(mayor):
    return max(1, mayor.bit_length())


def contador(titulo, modos, entradas=(), bits=None, prefijo="Q"):
    """Arma la maquina de un contador.

    modos      {combinacion de entradas: modo}. Sin entradas, la clave es "".
               Ej. {"00": [0, 4, 8, 12], "01": "paro", "10": "reinicio",
                    "11": [15, 12, 9, 6, 3, 0]}
    entradas   nombres de las entradas de control, ej. ["X", "Y"]
    bits       cuantos flip-flops; por omision los que pida el numero mayor
    Devuelve el dict de la maquina (el mismo formato que Machine.from_dict).
    """
    entradas = list(entradas)
    combinaciones = [format(i, f"0{len(entradas)}b") if entradas else ""
                     for i in range(1 << len(entradas))]
    faltan = [c for c in combinaciones if c not in modos]
    if faltan:
        raise ValueError("falta decir que hace el contador con las entradas "
                         + ", ".join(faltan or ["(sin entradas)"]))
    secuencias = [m for m in modos.values() if isinstance(m, list)]
    if not secuencias:
        raise ValueError("al menos un modo tiene que ser una secuencia de numeros")
    for s in secuencias:
        if len(s) < 2:
            raise ValueError(f"la secuencia {s} necesita al menos dos numeros")
        if len(set(s)) != len(s):
            raise ValueError(f"la secuencia {s} repite un numero: un contador sincrono "
                             "no sabria a cual de los dos ir")
        if min(s) < 0:
            raise ValueError(f"la secuencia {s} tiene un numero negativo")

    mayor = max(max(s) for s in secuencias)
    usa_set = "set" in modos.values()
    n = bits or _bits_necesarios(mayor)
    if mayor >= (1 << n):
        raise ValueError(f"el {mayor} no cabe en {n} bits")
    tope = (1 << n) - 1
    primero = secuencias[0][0]

    # los estados: todo numero que aparece en alguna secuencia (y el SET)
    numeros = []
    for s in secuencias:
        for v in s:
            if v not in numeros:
                numeros.append(v)
    if usa_set and tope not in numeros:
        numeros.append(tope)

    def siguiente(actual, modo):
        if modo == "paro":
            return actual
        if modo == "reinicio":
            return primero
        if modo == "set":
            return tope
        if actual in modo:
            return modo[(modo.index(actual) + 1) % len(modo)]
        return modo[0]     # entra a la secuencia por su primer numero

    bits_estado = [f"{prefijo}{k}" for k in range(n - 1, -1, -1)]
    maquina = {
        "doc_type": "fsm",
        "name": titulo, "kind": "moore", "inputs": entradas,
        "state_bits": bits_estado, "outputs": [],
        "states": [{"name": f"S{v}", "code": format(v, f"0{n}b"), "label": str(v)}
                   for v in numeros],
        "transitions": [],
        "inicial": f"S{primero}",
    }
    for v in numeros:
        for combo in combinaciones:
            destino = siguiente(v, modos[combo])
            maquina["transitions"].append({"from": f"S{v}", "in": combo, "to": f"S{destino}"})
    return maquina


def simular(maquina, entradas_por_ciclo, inicial=None):
    """Recorre la maquina ciclo por ciclo. Devuelve la lista de estados (nombres),
    empezando por el inicial. Sirve para los bancos de prueba y para revisar."""
    m = Machine.from_dict(maquina)
    actual = inicial or maquina.get("inicial") or m.states[0].name
    visitados = [actual]
    for combo in entradas_por_ciclo:
        t = m.next_state(actual, combo)
        if t is None:
            raise ValueError(f"el estado {actual} no tiene transicion con la entrada {combo!r}")
        actual = t.dst
        visitados.append(actual)
    return visitados


def leer_modo(texto, por_omision=None):
    """Lo que se escribe para un modo -> el modo de contador().

        paro / reinicio / set      tal cual
        sigue                      la secuencia base (--secuencia o --mod)
        0-15  o  12-0              un rango, que sube o baja
        4,7,2,6                    una lista
    """
    t = texto.strip().lower()
    if not t:
        raise ValueError("falta decir que hace en ese modo (ej. 0-15, paro, reinicio)")
    if t in ("paro", "reinicio", "set"):
        return t
    if t == "sigue":
        if por_omision is None:
            raise ValueError("'sigue' necesita una secuencia base")
        return list(por_omision)
    try:
        if "-" in t and "," not in t:
            a, _, b = t.partition("-")
            a, b = int(a), int(b)
            return list(range(a, b + 1)) if a <= b else list(range(a, b - 1, -1))
        return [int(x) for x in t.replace(" ", "").split(",") if x]
    except ValueError:
        raise ValueError(f"no entiendo el modo {texto!r}: usa una lista (4,7,2), un rango "
                         "(0-15), paro, reinicio o set")
