"""La protoboard: donde va cada pieza y por donde va cada cable.

Una protoboard de 63 columnas. Cada columna son dos grupos de cinco agujeros
conectados entre si --uno arriba del canal y otro abajo-- y los rieles de + y -
corren a lo largo, arriba y abajo del todo.

**Como se cablea.** Cada pin se clava en su columna, y esa columna tiene otros
cuatro agujeros libres del mismo nodo: para eso esta hecha la protoboard. Un
cable sale de uno de esos agujeros, corre en horizontal por su **carril** y sube
o baja por la columna de destino. Puros tramos rectos, sin diagonales.

**Los carriles no van sobre la cuadricula.** Cada cable tiene su propia altura,
repartida en el espacio disponible: con N cables, el k-esimo va a (k+1)/(N+1) de
la banda, con margen a los dos lados. Asi dos horizontales nunca quedan
encimadas ni pegadas a la orilla. A lo alto sobra espacio --el dibujo crece--
asi que no hay razon para que dos cables compartan altura.

Como cada pin pertenece a un solo nodo, **dos senales nunca comparten columna**:
eso sale de como esta hecha la protoboard, ahi no hay nada que resolver.

**Los colores dicen algo.** Los cables que entran a una misma compuerta van del
mismo color, para que se vea de un golpe que van juntos. Las salidas del
circuito llevan su propio color, y ese si se elige: arcoiris, o uno fijo por
nombre o por hex.
"""

from __future__ import annotations

from . import chips
from .. import theme

COLUMNAS = 63          # la protoboard comun, de 830 puntos
SEPARACION = 1         # columnas en blanco entre pieza y pieza

PASO = 15              # pixeles por columna (el paso real es 2.54 mm)
CANAL = PASO * 2       # el hueco del centro, por donde queda a caballo el chip
FILAS = 5              # agujeros por grupo, arriba y abajo
FILAS_LIBRES = FILAS - 1   # la fila 0 la ocupa el pin; las otras 4 son para cables

SEPARACION_CARRIL = 5.2    # minimo entre dos cables paralelos, en pixeles
MARGEN_CARRIL = PASO * 0.55

# De adentro hacia afuera: canal, cinco filas de agujeros, el riel de - y el de +.
_DEL_CENTRO_AL_BORDE = CANAL / 2 + PASO * 0.5 + (FILAS - 1) * PASO
_RIEL_GND = _DEL_CENTRO_AL_BORDE + PASO * 1.2
_RIEL_VCC = _DEL_CENTRO_AL_BORDE + PASO * 2.2
ALTO_TABLERO = int(2 * (_RIEL_VCC + PASO * 0.7))

# columnas que ocupa cada componente que no va a caballo del canal
ANCHO_PIEZA = {"entrada": 1, "salida": 1, "resistencia": 2, "led": 2}


# ------------------------------------------------------------- geometria

def columnas_de(pines):
    """Columnas que ocupa una pieza que va a caballo del canal."""
    return pines // 2


def posicion_del_pin(pin, pines, col0):
    """(columna, lado) de un pin a caballo del canal: los primeros abajo de
    izquierda a derecha, los demas arriba al reves."""
    mitad = pines // 2
    if pin <= mitad:
        return col0 + pin - 1, "abajo"
    return col0 + (pines - pin), "arriba"


def _centro(y0):
    return y0 + ALTO_TABLERO / 2


def _y_de(lado, fila, y0):
    """Altura de un agujero. `fila` 0 es el pegado al canal (las filas e y f)."""
    d = CANAL / 2 + PASO * 0.5 + fila * PASO
    return _centro(y0) + (d if lado == "abajo" else -d)


def _y_riel(y0, lado, nodo):
    d = _RIEL_VCC if nodo == "VCC" else _RIEL_GND
    return _centro(y0) + (d if lado == "abajo" else -d)


def _alto_tablero():
    return ALTO_TABLERO


# ------------------------------------------------------------- colocacion

def _piezas_de(net):
    """Todo lo que hay que acomodar, con su ancho y como se monta."""
    piezas = []
    for p in net["pastillas"]:
        pines = chips.CHIPS[p["chip"]]["pines"]
        piezas.append({"ref": p["ref"], "tipo": "ci", "modelo": p["chip"],
                       "pines": pines, "ancho": columnas_de(pines),
                       "montaje": "canal"})
    for c in net["componentes"]:
        if c["tipo"] == "ci":
            continue
        if c["tipo"] == "display":
            pares = c["pines"] + c["pines"] % 2
            piezas.append({"ref": c["ref"], "tipo": "display", "modelo": c["modelo"],
                           "pines": c["pines"], "ancho": columnas_de(pares),
                           "montaje": "canal"})
        else:
            piezas.append({"ref": c["ref"], "tipo": c["tipo"], "modelo": c["modelo"],
                           "pines": c["pines"],
                           "ancho": ANCHO_PIEZA.get(c["tipo"], c["pines"]),
                           "montaje": "abajo"})
    return piezas


def colocar(net, columnas=COLUMNAS):
    """Reparte las piezas en uno o varios tableros, en el orden en que se arma:
    entradas a la izquierda, encapsulados en medio, indicadores al final.

    No se abre un tablero nuevo si lo que falta cabe en el que ya hay.
    """
    piezas = _piezas_de(net)
    orden = {"entrada": 0, "ci": 1, "resistencia": 2, "led": 3, "display": 4,
             "salida": 5}
    piezas.sort(key=lambda p: orden.get(p["tipo"], 9))

    tableros, actual, cursor = [], None, 1
    for pieza in piezas:
        if actual is None or cursor + pieza["ancho"] - 1 > columnas:
            actual = {"indice": len(tableros), "piezas": []}
            tableros.append(actual)
            cursor = 1
        actual["piezas"].append(dict(pieza, col0=cursor))
        cursor += pieza["ancho"] + SEPARACION
    if not tableros:
        tableros.append({"indice": 0, "piezas": []})
    for t in tableros:
        t["pastillas"] = [p for p in t["piezas"] if p["tipo"] == "ci"]
    return tableros


def mapa_de_pines(tableros):
    """{(ref, pin): (tablero, columna, lado)} de todo lo que esta puesto."""
    mapa = {}
    for t in tableros:
        for p in t["piezas"]:
            for pin in range(1, p["pines"] + 1):
                if p["montaje"] == "canal":
                    pares = p["pines"] + p["pines"] % 2
                    col, lado = posicion_del_pin(pin, pares, p["col0"])
                else:
                    col, lado = p["col0"] + pin - 1, "abajo"
                mapa[(p["ref"], pin)] = (t["indice"], col, lado)
    return mapa


# ---------------------------------------------------------------- colores

def _color_de(indice):
    return theme.WIRE_COLORS[indice % len(theme.WIRE_COLORS)]


def _resolver_color(valor, indice):
    """None o 'arcoiris' da un color por salida; si no, el que pidan: un nombre
    CSS o un hex, con o sin gato."""
    if not valor or str(valor).lower() in ("arcoiris", "rainbow"):
        return _color_de(indice)
    color = str(valor).strip()
    if color and color[0] != "#" and len(color) in (3, 6) \
            and all(c in "0123456789abcdefABCDEF" for c in color):
        return "#" + color
    return color


def _colores_por_pin(net, salidas_color=None):
    """Que color lleva el cable que llega a cada pin.

    Los que entran a una misma compuerta comparten color; los que llegan a un
    indicador de salida usan el esquema elegido.
    """
    color_de_pin = {}
    chip_de = {p["ref"]: p["chip"] for p in net["pastillas"]}
    for i, g in enumerate(net["plan"].compuertas):
        if g.chip is None or g.chip not in chip_de:
            continue
        hueco = chips.compuertas(chip_de[g.chip])[g.hueco]
        for pin in hueco["entradas"]:
            color_de_pin[(g.chip, pin)] = _color_de(i)

    indicadores = [c for c in net["componentes"]
                   if c["tipo"] in ("resistencia", "led", "display", "salida")]
    for k, c in enumerate(indicadores):
        for pin in range(1, c["pines"] + 1):
            color_de_pin[(c["ref"], pin)] = _resolver_color(salidas_color, k)
    return color_de_pin


# ----------------------------------------------------------------- ruteo

def rutear(net, tableros, columnas=COLUMNAS, salidas_color=None):
    """Un cable por conexion, cada uno con su propio carril.

    De la fuente de la senal a cada destino. El color lo pone el destino, para
    que lo que entra a una misma compuerta se vea junto.
    """
    mapa = mapa_de_pines(tableros)
    color_de_pin = _colores_por_pin(net, salidas_color)

    tapadas = {}
    for t in tableros:
        ocupadas = set()
        for p in t["piezas"]:
            ocupadas.update(range(p["col0"], p["col0"] + p["ancho"]))
        tapadas[t["indice"]] = ocupadas

    cables, alimentacion, sueltos = [], [], []
    for nodo, conexiones in sorted(net["nodos"].items()):
        puntos = [(c, mapa.get((c["ref"], c["pin"]))) for c in conexiones]
        if nodo in ("VCC", "GND"):
            for c, punto in puntos:
                if punto is None:
                    sueltos.append((nodo, c["ref"], c["pin"]))
                else:
                    alimentacion.append({"nodo": nodo, "ref": c["ref"],
                                         "pin": c["pin"], "punto": punto})
            continue

        validos = [(c, p) for c, p in puntos if p is not None]
        for c, p in puntos:
            if p is None:
                sueltos.append((nodo, c["ref"], c["pin"]))
        if len(validos) < 2:
            continue

        # la fuente es el pin que maneja la senal
        idx = 0
        for i, (c, _) in enumerate(validos):
            if "salida" in (c.get("papel") or ""):
                idx = i
                break
        origen = validos[idx]
        for i, destino in enumerate(validos):
            if i == idx:
                continue
            color = color_de_pin.get((destino[0]["ref"], destino[0]["pin"]),
                                     _color_de(len(cables)))
            cables.append({"nodo": nodo, "color": color,
                           "origen": origen[1], "destino": destino[1],
                           "de": f"{origen[0]['ref']}-{origen[0]['pin']}",
                           "a": f"{destino[0]['ref']}-{destino[0]['pin']}"})

    carriles = _asignar_carriles(cables, tapadas, columnas)
    return {"cables": cables, "alimentacion": alimentacion, "mapa": mapa,
            "sueltos": sueltos, "carriles": carriles}


def _zona(punto):
    return (punto[0], punto[2])


def _asignar_carriles(cables, tapadas, columnas):
    """Cada cable, su propia altura dentro de la zona por la que corre."""
    porzona = {}
    for cable in cables:
        za, zb = _zona(cable["origen"]), _zona(cable["destino"])
        if za == zb:
            cable["tramos"] = [(za, cable["origen"][1], cable["destino"][1])]
        else:
            cruce = _columna_de_cruce(cable, tapadas, columnas)
            cable["cruce"] = cruce
            cable["tramos"] = [(za, cable["origen"][1], cruce),
                               (zb, cruce, cable["destino"][1])]
        for zona, a, b in cable["tramos"]:
            porzona.setdefault(zona, []).append(
                {"cable": cable, "zona": zona, "min": min(a, b), "max": max(a, b)})

    cuenta = {}
    for zona, tramos in porzona.items():
        tramos.sort(key=lambda t: (t["min"], t["max"]))
        total = len(tramos)
        cuenta[zona] = total
        for k, tramo in enumerate(tramos):
            tramo["cable"].setdefault("carril_de_zona", {})[zona] = (k, total)
    return cuenta


def _columna_de_cruce(cable, tapadas, columnas):
    """Una columna libre para saltar de un lado (o tablero) al otro."""
    tab = cable["origen"][0]
    ocupadas = tapadas.get(tab, set())
    for c in (cable["destino"][1], cable["origen"][1]):
        if c not in ocupadas:
            return c
    cerca = cable["origen"][1]
    for d in range(1, columnas):
        for c in (cerca - d, cerca + d):
            if 1 <= c <= columnas and c not in ocupadas:
                return c
    return cerca


# ---------------------------------------------------------------- dibujo

def _banda(total):
    """Alto que ocupan `total` carriles, con sus margenes."""
    if total <= 0:
        return 0.0
    return max(FILAS_LIBRES * PASO, (total + 1) * SEPARACION_CARRIL)


def _y_carril(lado, carril, total, y0):
    """La altura del carril k de N: (k+1)/(N+1) de la banda, nunca a ras."""
    d = (CANAL / 2 + PASO * 0.5 + MARGEN_CARRIL
         + _banda(total) * (carril + 1) / (total + 1))
    return _centro(y0) + (d if lado == "abajo" else -d)


def _alcance(total):
    return CANAL / 2 + PASO * 0.5 + MARGEN_CARRIL + _banda(total)


def _margenes(ruteo, tableros):
    """Cuanto espacio pide cada tablero por fuera, arriba y abajo."""
    margen = {}
    for t in tableros:
        i = t["indice"]
        fuera = []
        for lado in ("arriba", "abajo"):
            total = ruteo["carriles"].get((i, lado), 0)
            fuera.append(max(PASO * 2.2,
                             _alcance(total) - _DEL_CENTRO_AL_BORDE + PASO * 1.8))
        margen[i] = tuple(fuera)
    return margen


def svg(net, tableros, ruteo, columnas=COLUMNAS, titulo=""):
    """Dibuja los tableros, sus piezas y sus cables."""
    margen = _margenes(ruteo, tableros)
    ancho = int((columnas + 3) * PASO)

    y_de_tablero, y = {}, 26
    for t in tableros:
        arriba, abajo = margen[t["indice"]]
        y += arriba
        y_de_tablero[t["indice"]] = y
        y += ALTO_TABLERO + abajo + 30
    alto = int(y + 10)

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
         f'font-family="Georgia, serif">',
         f'<rect width="100%" height="100%" fill="#faf8f4"/>']

    for t in tableros:
        y0 = y_de_tablero[t["indice"]]
        s.append(_tablero_vacio(y0, columnas, t["indice"], len(tableros)))
        for pieza in t["piezas"]:
            s.append(_dibuja_pieza(pieza, y0))

    def x_de(col):
        return (col + 1) * PASO

    # --- alimentacion: derecho al riel de su lado
    for a in ruteo["alimentacion"]:
        tab, col, lado = a["punto"]
        y0 = y_de_tablero[tab]
        x, y1 = x_de(col), _y_de(lado, 0, y0)
        y2 = _y_riel(y0, lado, a["nodo"])
        color = "#c0392b" if a["nodo"] == "VCC" else "#2c3e50"
        s.append(f'<line x1="{x}" y1="{y1:.1f}" x2="{x}" y2="{y2:.1f}" '
                 f'stroke="{color}" stroke-width="2" opacity="0.9"/>')
        s.append(f'<circle cx="{x}" cy="{y2:.1f}" r="2.5" fill="{color}"/>')

    # --- los cables: tramo por tramo, todos en angulo recto
    for cable in ruteo["cables"]:
        s.append(_dibuja_cable(cable, y_de_tablero, x_de))

    # --- puentes de alimentacion entre tableros
    for t in tableros[:-1]:
        y0, y1 = y_de_tablero[t["indice"]], y_de_tablero[t["indice"] + 1]
        for nodo, color, dx in (("VCC", "#c0392b", PASO * 0.9),
                                ("GND", "#2c3e50", PASO * 1.6)):
            s.append(f'<path d="M {dx:.0f},{_y_riel(y0, "abajo", nodo):.1f} '
                     f'L {dx:.0f},{_y_riel(y1, "arriba", nodo):.1f}" '
                     f'stroke="{color}" stroke-width="2.4" fill="none"/>')

    if titulo:
        s.append(f'<text x="{PASO}" y="18" font-size="13" fill="#333">'
                 f'{_esc_svg(titulo)}</text>')
    s.append("</svg>")
    return "\n".join(s)


def _dibuja_cable(cable, y_de_tablero, x_de):
    color = cable["color"]
    s = []
    tramos = []
    for zona, a, b in cable["tramos"]:
        carril, total = cable["carril_de_zona"][zona]
        tab, lado = zona
        y0 = y_de_tablero[tab]
        tramos.append((a, b, _y_carril(lado, carril, total, y0),
                       _y_de(lado, 0, y0)))

    a1, b1, yc1, ypin1 = tramos[0]
    s.append(_recta(x_de(a1), ypin1, x_de(a1), yc1, color))
    s.append(f'<circle cx="{x_de(a1)}" cy="{ypin1:.1f}" r="2.3" fill="{color}"/>')
    s.append(_recta(x_de(a1), yc1, x_de(b1), yc1, color))

    if len(tramos) == 1:
        s.append(_recta(x_de(b1), yc1, x_de(b1), ypin1, color))
        s.append(f'<circle cx="{x_de(b1)}" cy="{ypin1:.1f}" r="2.3" fill="{color}"/>')
    else:
        a2, b2, yc2, ypin2 = tramos[1]
        s.append(_recta(x_de(b1), yc1, x_de(a2), yc2, color))
        s.append(_recta(x_de(a2), yc2, x_de(b2), yc2, color))
        s.append(_recta(x_de(b2), yc2, x_de(b2), ypin2, color))
        s.append(f'<circle cx="{x_de(b2)}" cy="{ypin2:.1f}" r="2.3" fill="{color}"/>')
    return "".join(s)


def _recta(x1, y1, x2, y2, color):
    """Un tramo recto. Si los dos extremos no se alinean, se dobla en L: nunca
    sale una diagonal."""
    if abs(x1 - x2) < 0.01 or abs(y1 - y2) < 0.01:
        return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
    return (f'<path d="M {x1:.1f},{y1:.1f} L {x1:.1f},{y2:.1f} L {x2:.1f},{y2:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>')


def _esc_svg(txt):
    return str(txt).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tablero_vacio(y0, columnas, indice, total):
    alto = ALTO_TABLERO
    ancho = (columnas + 2) * PASO
    cy = _centro(y0)
    s = [f'<rect x="{PASO * 0.5:.0f}" y="{y0 + 3}" width="{ancho:.0f}" height="{alto}" '
         f'rx="5" fill="#000" opacity="0.13"/>',
         f'<rect x="{PASO * 0.5:.0f}" y="{y0}" width="{ancho:.0f}" height="{alto}" '
         f'rx="5" fill="#efe9dc" stroke="#cdc4b2"/>',
         f'<rect x="{PASO * 0.5:.0f}" y="{cy - CANAL / 2:.1f}" width="{ancho:.0f}" '
         f'height="{CANAL}" fill="#e3ddce"/>',
         f'<rect x="{PASO * 0.5:.0f}" y="{cy - CANAL / 2:.1f}" width="{ancho:.0f}" '
         f'height="2.5" fill="#000" opacity="0.12"/>']
    for lado in ("arriba", "abajo"):
        for nodo, color in (("VCC", "#c0392b"), ("GND", "#2c3e50")):
            yy = _y_riel(y0, lado, nodo)
            s.append(f'<line x1="{PASO * 1.2:.0f}" y1="{yy:.1f}" x2="{ancho:.0f}" '
                     f'y2="{yy:.1f}" stroke="{color}" stroke-width="1.2" opacity="0.5"/>')
            s.append(f'<text x="{PASO * 0.75:.0f}" y="{yy + 3.5:.1f}" font-size="11" '
                     f'fill="{color}" text-anchor="middle">'
                     f'{"+" if nodo == "VCC" else "&#8722;"}</text>')
    for col in range(1, columnas + 1):
        x = (col + 1) * PASO
        for lado in ("arriba", "abajo"):
            for fila in range(FILAS):
                s.append(f'<circle cx="{x}" cy="{_y_de(lado, fila, y0):.1f}" r="1.6" '
                         f'fill="#d3cbba"/>')
        if col % 5 == 0:
            s.append(f'<text x="{x}" y="{cy + 3:.0f}" font-size="8" fill="#a39a88" '
                     f'text-anchor="middle">{col}</text>')
    if total > 1:
        s.append(f'<text x="{ancho - PASO:.0f}" y="{y0 - 6}" font-size="11" '
                 f'fill="#666" text-anchor="end">tablero {indice + 1} de {total}</text>')
    return "".join(s)


def _relieve(x, y, w, h, base="#2f3237", borde="#15171a"):
    return [f'<rect x="{x + 1.5:.1f}" y="{y + 2.5:.1f}" width="{w:.1f}" '
            f'height="{h:.1f}" rx="2" fill="#000" opacity="0.30"/>',
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" '
            f'fill="{base}" stroke="{borde}"/>',
            f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" width="{w - 2:.1f}" '
            f'height="{h * 0.16:.1f}" rx="1" fill="#ffffff" opacity="0.17"/>',
            f'<rect x="{x + 1:.1f}" y="{y + h - h * 0.15:.1f}" width="{w - 2:.1f}" '
            f'height="{h * 0.13:.1f}" rx="1" fill="#000000" opacity="0.28"/>']


def _dibuja_pieza(p, y0):
    if p["montaje"] == "canal":
        return _pieza_a_caballo(p, y0)
    return _pieza_acostada(p, y0)


def _pieza_a_caballo(p, y0):
    """Encapsulado o display: el cuerpo sobre el canal y las patas a los lados."""
    pares = p["pines"] + p["pines"] % 2
    x0 = (p["col0"] + 1) * PASO - PASO * 0.45
    w = (p["ancho"] - 1) * PASO + PASO * 0.9
    cy = _centro(y0)
    h = min(CANAL + PASO * 0.9, 2 * (CANAL / 2 + PASO * 0.5) - 2)
    y = cy - h / 2
    s = _relieve(x0, y, w, h, "#2f3237" if p["tipo"] == "ci" else "#1d1f22")
    s.append(f'<path d="M {x0},{cy - PASO * 0.32:.1f} A {PASO * 0.32:.1f},'
             f'{PASO * 0.32:.1f} 0 0 1 {x0},{cy + PASO * 0.32:.1f}" fill="#15171a"/>')
    etiqueta = f'{p["ref"]} {p["modelo"]}' if p["tipo"] == "ci" else p["ref"]
    s.append(f'<text x="{x0 + w / 2:.1f}" y="{cy + 3.2:.1f}" font-size="8.5" '
             f'fill="#d5d9de" text-anchor="middle">{_esc_svg(etiqueta)}</text>')
    for pin in range(1, p["pines"] + 1):
        col, lado = posicion_del_pin(pin, pares, p["col0"])
        x = (col + 1) * PASO
        yy = _y_de(lado, 0, y0)
        borde = y + h if lado == "abajo" else y
        s.append(f'<line x1="{x}" y1="{borde:.1f}" x2="{x}" y2="{yy:.1f}" '
                 f'stroke="#c9ccd1" stroke-width="2.4"/>')
        s.append(f'<circle cx="{x}" cy="{yy:.1f}" r="2.3" fill="#b9bdc4" '
                 f'stroke="#8a8f96" stroke-width="0.4"/>')
    return "".join(s)


def _pieza_acostada(p, y0):
    """Resistencia, LED o punto: acostados abajo, ocupando sus columnas."""
    x1 = (p["col0"] + 1) * PASO
    x2 = (p["col0"] + p["ancho"]) * PASO
    yy = _y_de("abajo", 0, y0)
    if p["tipo"] in ("entrada", "salida"):
        return (f'<circle cx="{x1}" cy="{yy:.1f}" r="4" fill="#fff" stroke="#555" '
                f'stroke-width="1.4"/>'
                f'<text x="{x1}" y="{yy - 8:.1f}" font-size="8" fill="#555" '
                f'text-anchor="middle">{_esc_svg(p["ref"])}</text>')

    s = [f'<line x1="{x1}" y1="{yy:.1f}" x2="{x2}" y2="{yy:.1f}" '
         f'stroke="#8a8f96" stroke-width="1.6"/>']
    cx = (x1 + x2) / 2
    if p["tipo"] == "resistencia":
        w, h = PASO * 0.9, PASO * 0.42
        s += _relieve(cx - w / 2, yy - h / 2, w, h, "#c8a165", "#8a6d3b")
        s.append(f'<text x="{cx:.1f}" y="{yy - PASO * 0.55:.1f}" font-size="7.5" '
                 f'fill="#888" text-anchor="middle">{_esc_svg(p["modelo"])}</text>')
    else:
        s.append(f'<circle cx="{cx:.1f}" cy="{yy + 1.5:.1f}" r="{PASO * 0.30:.1f}" '
                 f'fill="#000" opacity="0.28"/>')
        s.append(f'<circle cx="{cx:.1f}" cy="{yy:.1f}" r="{PASO * 0.30:.1f}" '
                 f'fill="#d94b3a" stroke="#8f2f22" stroke-width="0.8"/>')
    for x in (x1, x2):
        s.append(f'<circle cx="{x}" cy="{yy:.1f}" r="2.2" fill="#b9bdc4" '
                 f'stroke="#8a8f96" stroke-width="0.4"/>')
    return "".join(s)


def dibujar(net, columnas=COLUMNAS, titulo="", salidas_color=None):
    """Todo junto: coloca, rutea y dibuja. Devuelve (svg, ruteo, tableros)."""
    tableros = colocar(net, columnas)
    ruteo = rutear(net, tableros, columnas, salidas_color)
    return svg(net, tableros, ruteo, columnas, titulo), ruteo, tableros
