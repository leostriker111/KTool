"""Quine-McCluskey: implicantes primos y cobertura minima exacta."""

from __future__ import annotations


def _combine(a, b):
    diff = 0
    res = []
    for x, y in zip(a, b):
        if x != y:
            diff += 1
            res.append("-")
        else:
            res.append(x)
    return "".join(res) if diff == 1 else None


def pattern_minterms(pattern):
    """Todos los minterms cubiertos por un patron tipo '10-1'."""
    dash_pos = [i for i, c in enumerate(pattern) if c == "-"]
    n = len(pattern)
    base = int(pattern.replace("-", "0"), 2)
    out = set()
    for combo in range(1 << len(dash_pos)):
        v = base
        for b, i in enumerate(dash_pos):
            if (combo >> b) & 1:
                v |= 1 << (n - 1 - i)
        out.add(v)
    return out


def literal_count(pattern):
    return sum(1 for c in pattern if c != "-")


def prime_implicants(terms, nbits):
    """terms = minterms U dontcares (los que pueden combinarse)."""
    patterns = {format(t, f"0{nbits}b") for t in terms}
    primes = set()
    while patterns:
        used = set()
        nxt = set()
        plist = list(patterns)
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                c = _combine(plist[i], plist[j])
                if c is not None:
                    nxt.add(c)
                    used.add(plist[i])
                    used.add(plist[j])
        for p in patterns:
            if p not in used:
                primes.add(p)
        patterns = nxt
    return primes


# --------------------------------------------------------------- cobertura
#
# El problema: de todos los implicantes primos, elegir el subconjunto mas
# barato que cubra los minterminos obligatorios. Es cobertura de conjuntos,
# NP-dificil en general, pero con 6 variables se resuelve exacto si primero
# se reduce y solo despues se ramifica.
#
# Antes esto expandia el producto de sumas de Petrick, que multiplica el
# numero de productos por cada mintermino y con 6 variables se iba a minutos.


def _costo(conjunto):
    """(numero de terminos, literales totales). El mismo criterio de siempre."""
    return (len(conjunto), sum(literal_count(p) for p in conjunto))


def _reducir(pendientes, vivos, cobertura):
    """Reduce el problema sin ramificar y sin perder exactitud.

    Aplica hasta punto fijo: implicantes esenciales, dominancia de columnas
    (minterminos que otro arrastra) y dominancia de filas (implicantes que otro
    cubre por igual o mejor). La mayoria de las funciones se resuelven enteras
    aqui y nunca llegan a la ramificacion.
    """
    elegidos = set()
    cambio = True
    while cambio and pendientes:
        cambio = False

        # 1. esenciales: un mintermino al que solo un implicante alcanza
        esenciales = set()
        for m in pendientes:
            cubren = [p for p in vivos if m in cobertura[p]]
            if len(cubren) == 1:
                esenciales.add(cubren[0])
        if esenciales:
            elegidos |= esenciales
            vivos -= esenciales
            for p in esenciales:
                pendientes -= cobertura[p]
            cambio = True
            continue

        # 2. implicantes que ya no aportan nada
        inutiles = {p for p in vivos if not (cobertura[p] & pendientes)}
        if inutiles:
            vivos -= inutiles
            cambio = True
            continue

        # 3. dominancia de columnas: si todo el que cubre m2 cubre tambien m1,
        #    resolver m2 resuelve m1 de pasada, asi que m1 sale de la lista
        columnas = {m: frozenset(p for p in vivos if m in cobertura[p]) for m in pendientes}
        fuera = set()
        lista = sorted(pendientes)
        for m1 in lista:
            if m1 in fuera:
                continue
            for m2 in lista:
                if m2 == m1 or m2 in fuera:
                    continue
                if columnas[m2] <= columnas[m1] and (columnas[m2] != columnas[m1] or m2 < m1):
                    fuera.add(m1)
                    break
        if fuera:
            pendientes -= fuera
            cambio = True
            continue

        # 4. dominancia de filas: si p1 cubre todo lo de p2 y no cuesta mas,
        #    p2 sobra (toda solucion con p2 se cambia a p1 sin empeorar)
        fuera = set()
        lista = sorted(vivos)
        for p2 in lista:
            if p2 in fuera:
                continue
            c2 = cobertura[p2] & pendientes
            for p1 in lista:
                if p1 == p2 or p1 in fuera:
                    continue
                c1 = cobertura[p1] & pendientes
                if not c2 <= c1:
                    continue
                l1, l2 = literal_count(p1), literal_count(p2)
                if l1 < l2 or (l1 == l2 and (c1 != c2 or p1 < p2)):
                    fuera.add(p2)
                    break
        if fuera:
            vivos -= fuera
            cambio = True

    return elegidos, pendientes, vivos


def _ramificar(pendientes, vivos, cobertura, elegidos, mejor):
    """Busqueda exacta con poda sobre el nucleo ciclico que haya quedado."""
    elegidos = set(elegidos)
    nuevos, pendientes, vivos = _reducir(set(pendientes), set(vivos), cobertura)
    elegidos |= nuevos

    if not pendientes:
        costo = _costo(elegidos)
        if mejor is None or costo < mejor[0]:
            return (costo, elegidos)
        return mejor

    if not vivos:  # no deberia pasar: los primos cubren todos los minterminos
        return mejor

    # cota inferior: si el implicante mas generoso cubre `mas` minterminos,
    # faltan por lo menos ceil(pendientes / mas) terminos
    mas = max(len(cobertura[p] & pendientes) for p in vivos)
    minimo = len(elegidos) + -(-len(pendientes) // mas)
    if mejor is not None and minimo > mejor[0][0]:
        return mejor

    # ramifica sobre el mintermino mas apretado: el que menos implicantes cubren
    m = min(sorted(pendientes), key=lambda x: sum(1 for p in vivos if x in cobertura[p]))
    candidatos = sorted(
        (p for p in vivos if m in cobertura[p]),
        key=lambda p: (-len(cobertura[p] & pendientes), literal_count(p), p),
    )
    for p in candidatos:
        mejor = _ramificar(
            pendientes - cobertura[p], vivos - {p}, cobertura, elegidos | {p}, mejor
        )
    return mejor


def cover(primes, required):
    """Selecciona los implicantes primos que cubren 'required' (los unos reales).

    Exacto: minimiza (numero de terminos, literales totales)."""
    required = set(required)
    if not required:
        return set()
    cobertura = {p: pattern_minterms(p) & required for p in primes}
    vivos = {p for p in primes if cobertura[p]}
    mejor = _ramificar(required, vivos, cobertura, set(), None)
    return set(mejor[1]) if mejor else set()


def minimize(minterms, dontcares, nbits, required):
    """Regresa lista ordenada de patrones que cubre 'required'.
    'required' = unos (SOP) o ceros (POS). dontcares se usan para combinar."""
    required = set(required)
    if not required:
        return []
    terms = set(minterms) | set(dontcares)
    primes = prime_implicants(terms, nbits)
    chosen = cover(primes, required)
    return sorted(chosen)
