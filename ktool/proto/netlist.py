"""El netlist: la lista de conexiones fisicas del circuito.

Un netlist es eso y nada mas: **que pin va con que pin**. "El pin 3 del U1 va
al pin 1 del U2, y los dos al mismo nodo que llamamos G1." De aqui sale todo lo
demas -- el dibujo de la protoboard, la lista de cables que sigues mientras
armas, y la comprobacion de que no quedo ningun pin al aire.

El camino completo es:

    ecuaciones  ->  plan logico   (compuertas con nombre, sin chip todavia)
                ->  expansion     (lo que no cabe en un encapsulado, en cascada)
                ->  empaquetado   (cada compuerta a su pastilla: U1 compuerta 2)
                ->  netlist       (nodos: quien se conecta con quien)

Cada paso se puede mirar por separado, que es lo que permite comprobarlos.
"""

from __future__ import annotations

from . import chips, seleccion

# --------------------------------------------------------------- plan logico


class Compuerta:
    """Una compuerta logica, todavia sin pastilla asignada."""

    def __init__(self, cid, tipo, entradas, salida, usada_en=None):
        self.id = cid
        self.tipo = tipo
        self.entradas = list(entradas)   # nombres de senal
        self.salida = salida             # nombre de senal
        self.usada_en = list(usada_en or [])
        self.chip = None                 # ref de la pastilla, ej "U1"
        self.hueco = None                # indice de compuerta dentro de la pastilla

    def __repr__(self):
        return (f"{self.id}: {self.tipo}({', '.join(self.entradas)}) -> {self.salida}"
                + (f" [{self.chip} #{self.hueco}]" if self.chip else ""))


class Plan:
    def __init__(self):
        self.compuertas = []
        self.entradas = []       # variables que entran (A, B, ...)
        self.salidas = {}        # nombre de salida -> senal que la maneja
        self.constantes = {}     # nombre de salida -> 0 / 1
        self._n = 0

    def nueva(self, tipo, entradas, usada_en=None, nombre=None):
        self._n += 1
        cid = f"G{self._n}"
        salida = nombre or cid
        g = Compuerta(cid, tipo, entradas, salida, usada_en)
        self.compuertas.append(g)
        return g


def plan_logico(soluciones, forma):
    """De las ecuaciones a compuertas con nombre, compartiendo las repetidas."""
    interna, externa = {
        "sop": (chips.AND, chips.OR),
        "pos": (chips.OR, chips.AND),
        "nand": (chips.NAND, chips.NAND),
        "nor": (chips.NOR, chips.NOR),
    }[forma]
    universal = forma in ("nand", "nor")

    plan = Plan()
    variables = set()
    negados = set()
    compartidas = {}

    for nombre, sol in soluciones:
        if sol.const is not None:
            plan.constantes[nombre] = sol.const
            continue
        terminos = sol.terminos()
        for lits in terminos:
            for lit in lits:
                base = lit.rstrip("'")
                variables.add(base)
                if lit.endswith("'"):
                    negados.add(base)

    # los literales negados se generan: en la protoboard A' no existe
    plan.entradas = sorted(variables)
    inversores = {}
    for base in sorted(negados):
        g = plan.nueva(chips.NOT, [base], usada_en=["(literales)"])
        inversores[base + "'"] = g.salida

    def senal(lit):
        return inversores.get(lit, lit)

    for nombre, sol in soluciones:
        if sol.const is not None:
            continue
        terminos = sol.terminos()
        entradas_finales = []
        for lits in terminos:
            fuentes = [senal(l) for l in lits]
            if len(lits) == 1 and (not universal or len(terminos) == 1):
                entradas_finales.append(fuentes[0])
                continue
            tipo = chips.NOT if len(lits) == 1 else interna
            clave = (tipo, tuple(sorted(fuentes)))
            if clave in compartidas:
                g = compartidas[clave]
                if nombre not in g.usada_en:
                    g.usada_en.append(nombre)
            else:
                g = plan.nueva(tipo, fuentes, usada_en=[nombre])
                compartidas[clave] = g
            entradas_finales.append(g.salida)

        if len(entradas_finales) == 1 and not universal:
            plan.salidas[nombre] = entradas_finales[0]
        elif len(entradas_finales) == 1 and entradas_finales[0] in (
                l for l in map(senal, sum(terminos, []))) and len(terminos) == 1 \
                and len(terminos[0]) == 1:
            plan.salidas[nombre] = entradas_finales[0]
        else:
            g = plan.nueva(externa, entradas_finales, usada_en=[nombre],
                           nombre=nombre)
            plan.salidas[nombre] = g.salida
    return plan


# ----------------------------------------------------------------- expansion

def _trozos(lista, n):
    return [lista[i:i + n] for i in range(0, len(lista), n)]


def _expandir_una(plan, g, k):
    """Parte una compuerta en piezas de a lo mas `k` entradas.

    Las asociativas (AND, OR, XOR) se encadenan: la primera toma k entradas y
    cada siguiente toma el resultado anterior mas (k-1) nuevas.

    NAND y NOR no son asociativas -- el NAND de NANDs no es un NAND mas ancho.
    Se arma la cadena positiva (el AND o el OR), que cuesta dos compuertas por
    eslabon porque hay que deshacer cada inversion, y la ultima se deja sin
    deshacer: esa es justo la negacion que se buscaba.
    """
    if len(g.entradas) <= k:
        return [g]
    if k < 2:
        raise ValueError(f"no se puede armar {g.tipo} de {len(g.entradas)} "
                         f"entradas con compuertas de {k}")

    piezas = []
    universal = g.tipo in (chips.NAND, chips.NOR)

    def crear(entradas, final=False):
        if final:
            pieza = Compuerta(g.id, g.tipo, entradas, g.salida, g.usada_en)
        else:
            plan._n += 1
            cid = f"G{plan._n}"
            pieza = Compuerta(cid, g.tipo, entradas, cid, g.usada_en)
        piezas.append(pieza)
        return pieza.salida

    def eslabon(entradas):
        if not universal:
            return crear(entradas)
        t = crear(entradas)            # el grupo, negado
        return crear([t, t])           # y se deshace la inversion

    resto = list(g.entradas)
    acc = eslabon(resto[:k])
    resto = resto[k:]
    while len(resto) > k - 1:
        acc = eslabon([acc] + resto[:k - 1])
        resto = resto[k - 1:]
    crear([acc] + resto, final=True)
    return piezas


# -------------------------------------------------------------- empaquetado

def empaquetar(plan, modo=seleccion.FIEL, forzados=None):
    """Mete cada compuerta en una pastilla concreta (U1, U2, ...).

    El encapsulado se elige **por compuerta**, no por tipo: en modo fiel una AND
    de 2 va al 7408 y una de 3 al 7411, aunque las dos sean AND. Si la elegida
    resulta mas angosta que la compuerta, esa compuerta se parte en cascada.

    Devuelve (pastillas, sin_chip).
    """
    forzados = list(forzados or [])
    anchos_max = {}
    for g in plan.compuertas:
        anchos_max[g.tipo] = max(anchos_max.get(g.tipo, 0), len(g.entradas))

    nuevas, sin_chip, chip_de = [], [], {}
    for g in list(plan.compuertas):
        elegido = seleccion._elige_chip(g.tipo, len(g.entradas), modo,
                                        forzados, anchos_max)
        if not elegido:
            sin_chip.append(g)
            continue
        chip = elegido[0]
        k = chips.CHIPS[chip]["entradas"]
        for pieza in _expandir_una(plan, g, k):
            chip_de[pieza.id] = chip
            nuevas.append(pieza)
    plan.compuertas = nuevas

    pastillas, abiertas = [], {}
    for g in plan.compuertas:
        chip = chip_de[g.id]
        libres = abiertas.get(chip)
        if not libres:
            ref = f"U{len(pastillas) + 1}"
            huecos = chips.compuertas(chip)
            pastilla = {"ref": ref, "chip": chip, "compuertas": [None] * len(huecos)}
            pastillas.append(pastilla)
            libres = abiertas[chip] = [(pastilla, i) for i in range(len(huecos))]
        pastilla, hueco = libres.pop(0)
        pastilla["compuertas"][hueco] = g
        g.chip, g.hueco = pastilla["ref"], hueco
    return pastillas, sin_chip


# ------------------------------------------------------------------ netlist

SEGMENTOS_7 = "abcdefg"
SEGMENTOS_16 = [f"s{i + 1}" for i in range(16)]


def construir(soluciones, forma="sop", modo=seleccion.FIEL, forzados=None,
              extremos="puntos"):
    """El netlist completo: componentes, nodos y avisos.

    `extremos` dice que se pone en las salidas:
      'puntos'   solo el punto etiquetado
      'led'      LED con su resistencia a GND (enciende en alto)
      '7seg_cc'  display de 7 segmentos, catodo comun (enciende en alto)
      '7seg_ca'  display de 7 segmentos, anodo comun  (enciende en BAJO)
      '16seg_cc' / '16seg_ca'  igual con 16 segmentos
    """
    plan = plan_logico(soluciones, forma)
    pastillas, sin_chip = empaquetar(plan, modo, forzados)

    componentes = []
    nodos = {}
    avisos = []

    def conectar(nodo, ref, pin, papel=""):
        nodos.setdefault(nodo, []).append({"ref": ref, "pin": pin, "papel": papel})

    # --- las pastillas
    for p in pastillas:
        info = chips.CHIPS[p["chip"]]
        componentes.append({"ref": p["ref"], "tipo": "ci", "modelo": p["chip"],
                            "pines": info["pines"], "descripcion": info["descripcion"]})
        vcc, gnd = chips.alimentacion(p["chip"])
        conectar("VCC", p["ref"], vcc, "alimentacion")
        conectar("GND", p["ref"], gnd, "alimentacion")
        huecos = chips.compuertas(p["chip"])
        for i, g in enumerate(p["compuertas"]):
            h = huecos[i]
            if g is None:
                # compuerta sobrante del encapsulado: sus entradas se amarran
                # para que no floten (una entrada al aire en TTL es ruido)
                destino = "GND" if info["tipo"] in (chips.OR, chips.NOR) else "VCC"
                for pin in h["entradas"]:
                    conectar(destino, p["ref"], pin, "compuerta sin usar")
                continue
            for pin, senal in zip(h["entradas"], g.entradas):
                conectar(senal, p["ref"], pin, f"{g.id} entrada")
            # una compuerta mas angosta que el hueco: lo que sobra se amarra
            sobran = h["entradas"][len(g.entradas):]
            destino = "GND" if g.tipo in (chips.OR, chips.NOR) else "VCC"
            for pin in sobran:
                conectar(destino, p["ref"], pin, f"{g.id} entrada sin usar")
            conectar(g.salida, p["ref"], h["salida"], f"{g.id} salida")

    # --- las entradas del circuito
    for i, var in enumerate(plan.entradas):
        ref = f"SW{i + 1}"
        componentes.append({"ref": ref, "tipo": "entrada", "modelo": "punto",
                            "pines": 1, "descripcion": f"entrada {var}"})
        conectar(var, ref, 1, "entrada del circuito")

    # --- los extremos de salida
    nombres = list(plan.salidas) + list(plan.constantes)
    if extremos.startswith("7seg") or extremos.startswith("16seg"):
        esperados = SEGMENTOS_7 if extremos.startswith("7seg") else SEGMENTOS_16
        anodo = extremos.endswith("_ca")
        ref = "DS1"
        componentes.append({
            "ref": ref, "tipo": "display", "modelo": extremos,
            "pines": len(esperados) + 1,
            "descripcion": ("anodo comun" if anodo else "catodo comun"),
        })
        conectar("VCC" if anodo else "GND", ref, len(esperados) + 1, "comun")
        if anodo:
            avisos.append(
                "Anodo comun: el segmento enciende con la senal en BAJO. Las "
                "ecuaciones tienen que ser las del complemento (la minimizacion "
                "de los ceros), o el display mostrara el negativo.")
        faltan = [s for s in esperados if s not in nombres]
        if faltan:
            avisos.append("El display pide segmentos que la tabla no tiene: "
                          + ", ".join(faltan))
        for i, seg in enumerate(esperados):
            if seg not in nombres:
                continue
            rref = f"R{i + 1}"
            componentes.append({"ref": rref, "tipo": "resistencia", "modelo": "220",
                                "pines": 2, "descripcion": f"limitadora del segmento {seg}"})
            fuente = plan.salidas.get(seg)
            if fuente:
                conectar(fuente, rref, 1, f"segmento {seg}")
            else:
                conectar("VCC" if plan.constantes[seg] else "GND", rref, 1,
                         f"segmento {seg} fijo")
            conectar(f"{seg}@display", rref, 2, "")
            conectar(f"{seg}@display", ref, i + 1, f"segmento {seg}")
    elif extremos == "led":
        for i, nombre in enumerate(nombres):
            rref, dref = f"R{i + 1}", f"D{i + 1}"
            componentes.append({"ref": rref, "tipo": "resistencia", "modelo": "220",
                                "pines": 2, "descripcion": f"limitadora de {nombre}"})
            componentes.append({"ref": dref, "tipo": "led", "modelo": "LED",
                                "pines": 2, "descripcion": f"indicador de {nombre}"})
            fuente = plan.salidas.get(nombre)
            if fuente:
                conectar(fuente, rref, 1, f"salida {nombre}")
            else:
                conectar("VCC" if plan.constantes[nombre] else "GND", rref, 1,
                         f"salida {nombre} fija")
            conectar(f"{nombre}@led", rref, 2, "")
            conectar(f"{nombre}@led", dref, 1, "anodo")
            conectar("GND", dref, 2, "catodo")
    else:
        for i, nombre in enumerate(nombres):
            ref = f"P{i + 1}"
            componentes.append({"ref": ref, "tipo": "salida", "modelo": "punto",
                                "pines": 1, "descripcion": f"salida {nombre}"})
            fuente = plan.salidas.get(nombre)
            if fuente:
                conectar(fuente, ref, 1, f"salida {nombre}")
            else:
                conectar("VCC" if plan.constantes[nombre] else "GND", ref, 1,
                         f"salida {nombre} fija")

    for g in sin_chip:
        avisos.append(f"sin encapsulado para {g.tipo} de {len(g.entradas)} entradas")

    return {
        "forma": forma,
        "modo": modo,
        "componentes": componentes,
        "nodos": {n: c for n, c in nodos.items()},
        "pastillas": pastillas,
        "plan": plan,
        "avisos": avisos,
        "completo": not sin_chip,
    }


def lista_de_cables(net):
    """Los nodos como lista de cables a jalar, que es lo que sigues armando."""
    cables = []
    for nodo, conexiones in sorted(net["nodos"].items()):
        if len(conexiones) < 2:
            continue
        ancla = conexiones[0]
        for otro in conexiones[1:]:
            cables.append({
                "nodo": nodo,
                "de": f"{ancla['ref']}-{ancla['pin']}",
                "a": f"{otro['ref']}-{otro['pin']}",
            })
    return cables


# ---------------------------------------------------------- comprobaciones

_OPERA = {
    chips.AND: lambda vs: int(all(vs)),
    chips.NAND: lambda vs: int(not all(vs)),
    chips.OR: lambda vs: int(any(vs)),
    chips.NOR: lambda vs: int(not any(vs)),
    chips.NOT: lambda vs: int(not vs[0]),
    chips.XOR: lambda vs: int(sum(vs) % 2 == 1),
    chips.XNOR: lambda vs: int(sum(vs) % 2 == 0),
}


def evaluar(net, entradas):
    """Propaga valores por el netlist. `entradas` es {'A': 0/1, ...}.

    No es una funcion de usuario: es como se comprueba que lo armado hace lo
    que dicen las ecuaciones.
    """
    plan = net["plan"]
    valores = dict(entradas)
    valores["VCC"] = 1
    valores["GND"] = 0
    pendientes = list(plan.compuertas)
    while pendientes:
        avanzo = False
        quedan = []
        for g in pendientes:
            if all(e in valores for e in g.entradas):
                valores[g.salida] = _OPERA[g.tipo]([valores[e] for e in g.entradas])
                avanzo = True
            else:
                quedan.append(g)
        if not avanzo:
            faltan = {e for g in quedan for e in g.entradas if e not in valores}
            raise ValueError(f"el netlist tiene un lazo o señales sin fuente: {sorted(faltan)}")
        pendientes = quedan
    return valores


def comprobar(net, tabla):
    """Revisa el netlist contra la tabla de verdad y contra si mismo.

    Devuelve la lista de problemas; vacia si todo cuadra.
    """
    problemas = []
    plan = net["plan"]

    # --- cada senal tiene una sola fuente
    fuentes = {}
    for g in plan.compuertas:
        if g.salida in fuentes:
            problemas.append(f"la senal {g.salida} la manejan dos compuertas "
                             f"({fuentes[g.salida]} y {g.id})")
        fuentes[g.salida] = g.id

    # --- toda pastilla alimentada
    for p in net["pastillas"]:
        vcc, gnd = chips.alimentacion(p["chip"])
        for nodo, pin, que in (("VCC", vcc, "VCC"), ("GND", gnd, "GND")):
            if not any(c["ref"] == p["ref"] and c["pin"] == pin
                       for c in net["nodos"].get(nodo, [])):
                problemas.append(f"{p['ref']} ({p['chip']}) no tiene {que} conectado")

    # --- ningun pin de compuerta al aire
    for p in net["pastillas"]:
        huecos = chips.compuertas(p["chip"])
        conectados = {(c["ref"], c["pin"]) for cs in net["nodos"].values() for c in cs}
        for i, g in enumerate(p["compuertas"]):
            for pin in huecos[i]["entradas"]:
                if (p["ref"], pin) not in conectados:
                    problemas.append(f"{p['ref']} pin {pin} quedo al aire")

    # --- y lo que importa: que haga lo que dicen las ecuaciones
    n = tabla.nvars
    for i in range(1 << n):
        entradas = {v: (i >> (n - 1 - k)) & 1 for k, v in enumerate(tabla.variables)}
        try:
            valores = evaluar(net, entradas)
        except ValueError as e:
            problemas.append(str(e))
            break
        for nombre, esperado in tabla.outputs.items():
            if esperado[i] == "x":
                continue
            if nombre in plan.constantes:
                dio = plan.constantes[nombre]
            else:
                dio = valores.get(plan.salidas.get(nombre))
            if dio != esperado[i]:
                problemas.append(f"fila {i}: la salida {nombre} deberia ser "
                                 f"{esperado[i]} y el netlist da {dio}")
    return problemas
