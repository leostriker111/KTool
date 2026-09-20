"""De las ecuaciones a los encapsulados: que chips hacen falta y cuantos.

Esta es la etapa donde el costo cambia de unidad. `simplify.py` cuenta
compuertas, que es lo correcto en el papel. Aqui se cuentan **chips**, que es lo
que compras y lo que ocupa lugar en la protoboard: un 7408 trae cuatro AND, asi
que usar una o usar cuatro cuesta lo mismo.

Tres modos, los tres reusan las compuertas libres de un chip ya puesto:

- FIEL: cada compuerta del diagrama con su ancho exacto. Un termino de 4
  literales pide una AND de 4 entradas (7421), aunque sobre media pastilla.
- FORZADO: armar con los chips que el usuario diga. Lo que no quepa se hace en
  cascada.
- AUTOMATICO: un solo ancho por tipo, el mayor que el circuito necesite. Las
  entradas que sobran se amarran (a Vcc en AND/NAND, a GND en OR/NOR).
"""

from __future__ import annotations

import math
from collections import Counter

from . import chips

FIEL, FORZADO, AUTOMATICO = "fiel", "forzado", "automatico"


# --------------------------------------------------- que compuertas hacen falta

def _tipos_de(forma):
    """(compuerta de los terminos, compuerta final) segun la realizacion."""
    return {
        "sop": (chips.AND, chips.OR),
        "pos": (chips.OR, chips.AND),
        "nand": (chips.NAND, chips.NAND),
        "nor": (chips.NOR, chips.NOR),
    }[forma]


def compuertas_necesarias(soluciones):
    """Cuenta las compuertas de un circuito de una o varias salidas.

    `soluciones` es [(nombre, Solution)]. Devuelve (Counter de (tipo, ancho),
    literales negados que hay que generar).

    Los terminos identicos entre salidas se cuentan una sola vez: son la misma
    compuerta fisica, que es justo el ahorro que reporta el circuito combinado.
    """
    necesarias = Counter()
    negados = set()
    terminos_vistos = set()

    for _, sol in soluciones:
        if sol.const is not None:
            continue                       # una constante se amarra a Vcc o GND
        if sol.form == "xor":
            if len(sol.xor_vars) >= 2:
                necesarias[(chips.XOR, 2)] += len(sol.xor_vars) - 1
            if sol.xnor:
                necesarias[(chips.NOT, 1)] += 1
            continue

        interno, final = _tipos_de(sol.form)
        terminos = sol.terminos()
        universal = sol.form in ("nand", "nor")

        for lits in terminos:
            for lit in lits:
                if lit.endswith("'"):
                    negados.add(lit)
            clave = (interno, tuple(sorted(lits)))
            if len(lits) == 1:
                # en SOP/POS el literal entra directo; en NAND/NOR hay que invertirlo
                if universal:
                    necesarias[(chips.NOT, 1)] += 1
                continue
            if clave in terminos_vistos:
                continue                   # compuerta compartida entre salidas
            terminos_vistos.add(clave)
            necesarias[(interno, len(lits))] += 1

        if len(terminos) > 1:
            necesarias[(final, len(terminos))] += 1
        elif universal and len(terminos[0]) > 1:
            necesarias[(chips.NOT, 1)] += 1   # la segunda compuerta deshace la primera

    return necesarias, negados


# ------------------------------------------------------------------ el reparto

def _cascada(tipo, ancho_pedido, ancho_chip):
    """Compuertas de `ancho_chip` entradas para armar una de `ancho_pedido`.

    AND, OR y XOR son asociativas: se encadenan y cada compuerta extra agrega
    (ancho_chip - 1) entradas.

    NAND y NOR **no** son asociativas: el NAND de NANDs no es un NAND mas ancho.
    Se arma el AND (u OR) en arbol --cada nivel cuesta dos compuertas, una que
    opera y otra que deshace la inversion-- y la ultima se deja sin deshacer,
    que es justo la negacion que se buscaba. De ahi el 2n-1.
    """
    if ancho_pedido <= ancho_chip:
        return 1
    if ancho_chip < 2:
        return None                        # un inversor no arma nada mas ancho
    eslabones = math.ceil((ancho_pedido - 1) / (ancho_chip - 1))
    if tipo in (chips.NAND, chips.NOR):
        return 2 * eslabones - 1
    return eslabones


def puede_cascada(tipo):
    """El inversor es el unico que no se puede ensanchar."""
    return tipo != chips.NOT


def _elige_chip(tipo, ancho, modo, forzados, anchos_max):
    """Devuelve (nombre_chip, compuertas_del_chip_que_se_gastan) o None."""
    if modo == FORZADO:
        candidatos = [c for c in forzados if chips.CHIPS[c]["tipo"] == tipo]
        if not candidatos:
            return None
        # el mas ancho de los permitidos, para gastar menos compuertas
        chip = max(candidatos, key=lambda c: chips.CHIPS[c]["entradas"])
        gasto = _cascada(tipo, ancho, chips.CHIPS[chip]["entradas"])
        return (chip, gasto) if gasto else None

    anchos = chips.anchos(tipo)
    if not anchos:
        return None

    if modo == AUTOMATICO:
        objetivo = max(ancho, anchos_max.get(tipo, ancho))
        cabe = [a for a in anchos if a >= objetivo] or [a for a in anchos if a >= ancho]
    else:                                   # FIEL: el ancho exacto que pide el diagrama
        cabe = [a for a in anchos if a >= ancho]

    if cabe:
        elegido = min(cabe)
        return chips.por_tipo(tipo, entradas=elegido)[0], 1

    # no hay encapsulado tan ancho: se arma en cascada con el mas ancho que haya
    elegido = max(anchos)
    gasto = _cascada(tipo, ancho, elegido)
    if not gasto:
        return None
    return chips.por_tipo(tipo, entradas=elegido)[0], gasto


def repartir(soluciones, modo=FIEL, forzados=None, generar_negados=True):
    """Reparte las compuertas en encapsulados.

    Devuelve un dict con los chips y cuantos, las compuertas que sobran, y lo
    que no se pudo armar.
    """
    if modo == FORZADO and not forzados:
        raise ValueError("el modo forzado necesita la lista de chips a usar")
    forzados = list(forzados or [])
    for c in forzados:
        if c not in chips.CHIPS:
            raise ValueError(f"el chip {c!r} no esta en el catalogo")

    necesarias, negados = compuertas_necesarias(soluciones)

    # los inversores de los literales negados: en la protoboard A' no existe
    if generar_negados and negados:
        necesarias[(chips.NOT, 1)] += len(negados)

    anchos_max = {}
    for (tipo, ancho) in necesarias:
        anchos_max[tipo] = max(anchos_max.get(tipo, 0), ancho)

    gastadas = Counter()          # chip -> compuertas ocupadas
    sin_armar = []
    for (tipo, ancho), cuantas in sorted(necesarias.items(), key=lambda kv: str(kv[0])):
        elegido = _elige_chip(tipo, ancho, modo, forzados, anchos_max)
        if elegido is None:
            sin_armar.append({"tipo": tipo, "entradas": ancho, "cuantas": cuantas})
            continue
        chip, por_compuerta = elegido
        gastadas[chip] += cuantas * por_compuerta

    inventario = {}
    for chip, ocupadas in gastadas.items():
        por_chip = len(chips.compuertas(chip))
        cuantos = math.ceil(ocupadas / por_chip)
        inventario[chip] = {
            "cuantos": cuantos,
            "compuertas_usadas": ocupadas,
            "compuertas_totales": cuantos * por_chip,
            "libres": cuantos * por_chip - ocupadas,
            "descripcion": chips.CHIPS[chip]["descripcion"],
        }

    return {
        "modo": modo,
        "chips": inventario,
        # si algo quedo sin armar, el total NO es el costo del circuito: es el
        # costo de un circuito incompleto. Un numero mas chico que no se puede
        # construir es peor que ningun numero.
        "completo": not sin_armar,
        "total_chips": sum(v["cuantos"] for v in inventario.values()),
        "compuertas": dict(necesarias),
        "negados": sorted(negados),
        "sin_armar": sin_armar,
    }


def comparar(soluciones_por_forma, modo=FIEL, forzados=None):
    """{forma: reparto} para ver que realizacion sale mas barata EN CHIPS."""
    return {forma: repartir(sols, modo, forzados)
            for forma, sols in soluciones_por_forma.items()}


def mas_barata(repartos):
    """La realizacion con menos chips, de entre las que SI se pueden armar.

    Un reparto incompleto queda fuera aunque su numero sea el mas chico: ese
    numero no corresponde al circuito, sino a lo que alcanzo a armarse.
    """
    completos = {f: r for f, r in repartos.items() if r["completo"]}
    if not completos:
        return None
    return min(completos, key=lambda f: (completos[f]["total_chips"], f))
