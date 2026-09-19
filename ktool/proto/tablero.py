"""La protoboard: donde va cada pastilla y por donde va cada cable.

Una protoboard de 63 columnas. Cada columna son dos grupos de cinco agujeros
conectados entre si --uno arriba del canal y otro abajo-- y los rieles de + y -
corren a lo largo, arriba y abajo del todo.

**Por que no hace falta un ruteador.** Cada pin de un chip se clava en su propia
columna, y esa columna tiene otros cuatro agujeros libres. Un cable de ese pin a
otro sale de uno de esos agujeros libres. Como cada pin pertenece a un solo nodo,
**dos senales nunca pueden compartir columna**: no hay colision que resolver, sale
de como esta hecha la protoboard. Lo unico que hay que repartir bien son las
pastillas, para que quepan y no se encimen.

Cuando ya no caben, se agrega otro tablero y se dibujan los puentes de + y -
entre los rieles de los dos, que es lo que de verdad haces en la mesa.
"""

from __future__ import annotations

from . import chips
from .. import theme

COLUMNAS = 63          # la protoboard comun, de 830 puntos
SEPARACION = 1         # columnas en blanco entre pastilla y pastilla

FILAS_ABAJO = "fghij"  # los cinco agujeros de abajo del canal
FILAS_ARRIBA = "edcba"  # los cinco de arriba, contando desde el canal


def columnas_de(pines):
    """Columnas que ocupa un encapsulado: la mitad de sus pines."""
    return pines // 2


def posicion_del_pin(pin, pines, col0):
    """(columna, lado) de un pin. El encapsulado va a caballo del canal:
    los primeros pines abajo de izquierda a derecha, los demas arriba al reves."""
    mitad = pines // 2
    if pin <= mitad:
        return col0 + pin - 1, "abajo"
    return col0 + (pines - pin), "arriba"


def colocar(net, columnas=COLUMNAS):
    """Reparte las pastillas en uno o varios tableros, por zonas.

    Como se arma de verdad: las entradas a la izquierda del todo, luego los
    encapsulados, y los indicadores (LEDs, display) al final. Asi los cables
    van de izquierda a derecha en vez de cruzar el tablero entero.

    Devuelve [{'indice', 'pastillas', 'zona_entradas', 'zona_salidas'}].
    """
    entradas = [c for c in net["componentes"] if c["tipo"] == "entrada"]
    salidas = [c for c in net["componentes"]
               if c["tipo"] in ("salida", "resistencia", "led", "display")]
    n_entradas = sum(c["pines"] for c in entradas)
    n_salidas = sum(c["pines"] for c in salidas)

    tableros = []

    def nuevo_tablero():
        t = {"indice": len(tableros), "pastillas": [],
             "zona_entradas": [], "zona_salidas": []}
        tableros.append(t)
        return t

    actual = nuevo_tablero()
    cursor = 1
    # zona de entradas, pegada a la izquierda del primer tablero
    reserva = min(n_entradas, max(0, columnas - 10))
    actual["zona_entradas"] = list(range(cursor, cursor + reserva))
    cursor += reserva + (SEPARACION if reserva else 0)

    for p in net["pastillas"]:
        pines = chips.CHIPS[p["chip"]]["pines"]
        ancho = columnas_de(pines)
        if cursor + ancho - 1 > columnas:
            actual = nuevo_tablero()
            cursor = 1
        actual["pastillas"].append({"ref": p["ref"], "chip": p["chip"],
                                    "col0": cursor, "pines": pines})
        cursor += ancho + SEPARACION

    # zona de salidas, despues de la ultima pastilla
    faltan = n_salidas
    while faltan > 0:
        hueco = columnas - cursor + 1
        if hueco <= 0:
            actual = nuevo_tablero()
            cursor = 1
            continue
        toma = min(faltan, hueco)
        actual["zona_salidas"] += list(range(cursor, cursor + toma))
        cursor += toma
        faltan -= toma
    return tableros


def mapa_de_pines(tableros):
    """{(ref, pin): (tablero, columna, lado)} para todo el circuito."""
    mapa = {}
    for t in tableros:
        for p in t["pastillas"]:
            for pin in range(1, p["pines"] + 1):
                col, lado = posicion_del_pin(pin, p["pines"], p["col0"])
                mapa[(p["ref"], pin)] = (t["indice"], col, lado)
    return mapa


def _columnas_libres(tableros, mapa, columnas=COLUMNAS):
    """Columnas de cada tablero donde no hay ninguna pastilla."""
    libres = {}
    for t in tableros:
        ocupadas = set()
        for p in t["pastillas"]:
            ocupadas.update(range(p["col0"], p["col0"] + columnas_de(p["pines"])))
        libres[t["indice"]] = [c for c in range(1, columnas + 1) if c not in ocupadas]
    return libres


def rutear(net, tableros, columnas=COLUMNAS):
    """Los cables: de que agujero a que agujero.

    Cada nodo se recorre en cadena. Los componentes que no son pastillas
    (entradas, LEDs, displays) se clavan en columnas libres.
    """
    mapa = mapa_de_pines(tableros)

    def huecos_de(clave):
        """Las columnas reservadas de una zona, tablero por tablero."""
        for t in tableros:
            for col in t[clave]:
                yield t["indice"], col

    zona_e = huecos_de("zona_entradas")
    zona_s = huecos_de("zona_salidas")

    por_ref = {c["ref"]: c for c in net["componentes"]}
    sueltos = []
    for c in net["componentes"]:
        if c["tipo"] == "ci":
            continue
        zona = zona_e if c["tipo"] == "entrada" else zona_s
        for pin in range(1, c["pines"] + 1):
            sitio = next(zona, None)
            if sitio is None:
                sueltos.append((c["tipo"], c["ref"], pin))
                continue
            tab, col = sitio
            mapa[(c["ref"], pin)] = (tab, col, "abajo" if pin % 2 else "arriba")

    cables, alimentacion = [], []
    for i, (nodo, conexiones) in enumerate(sorted(net["nodos"].items())):
        puntos = [mapa.get((c["ref"], c["pin"])) for c in conexiones]
        if nodo in ("VCC", "GND"):
            for c, punto in zip(conexiones, puntos):
                if punto is None:
                    sueltos.append((nodo, c["ref"], c["pin"]))
                    continue
                alimentacion.append({"nodo": nodo, "ref": c["ref"], "pin": c["pin"],
                                     "punto": punto})
            continue
        color = theme.WIRE_COLORS[i % len(theme.WIRE_COLORS)]
        validos = [(c, p) for c, p in zip(conexiones, puntos) if p is not None]
        for (c, p) in zip(conexiones, puntos):
            if p is None:
                sueltos.append((nodo, c["ref"], c["pin"]))
        for (c1, p1), (c2, p2) in zip(validos, validos[1:]):
            cables.append({
                "nodo": nodo, "color": color,
                "de": {"ref": c1["ref"], "pin": c1["pin"], "punto": p1},
                "a": {"ref": c2["ref"], "pin": c2["pin"], "punto": p2},
            })
    return {"cables": cables, "alimentacion": alimentacion,
            "mapa": mapa, "sueltos": sueltos, "por_ref": por_ref}


# ------------------------------------------------------------------ dibujo

PASO = 15            # pixeles por columna (el paso real es 2.54 mm)
CANAL = PASO * 2     # el hueco del centro, por donde queda a caballo el chip
FILAS = 5            # agujeros por grupo, arriba y abajo

# De adentro hacia afuera: canal, cinco filas de agujeros, el riel de - y el de +.
_DEL_CENTRO_AL_BORDE = CANAL / 2 + PASO * 0.5 + (FILAS - 1) * PASO
_RIEL_GND = _DEL_CENTRO_AL_BORDE + PASO * 1.2
_RIEL_VCC = _DEL_CENTRO_AL_BORDE + PASO * 2.2
ALTO_TABLERO = int(2 * (_RIEL_VCC + PASO * 0.7))


def _centro(y0):
    return y0 + ALTO_TABLERO / 2


def _y_de(lado, fila, y0):
    """Altura de un agujero. `fila` 0 es el pegado al canal (las filas e y f)."""
    d = CANAL / 2 + PASO * 0.5 + fila * PASO
    return _centro(y0) + (d if lado == "abajo" else -d)


def _y_riel(y0, lado, nodo):
    """El riel que le toca: los de arriba para lo de arriba."""
    d = _RIEL_VCC if nodo == "VCC" else _RIEL_GND
    return _centro(y0) + (d if lado == "abajo" else -d)


def _alto_tablero():
    return ALTO_TABLERO


def svg(net, tableros, ruteo, columnas=COLUMNAS, titulo=""):
    """Dibuja los tableros con sus pastillas y sus cables."""
    ancho = int((columnas + 3) * PASO)
    alto_t = _alto_tablero()
    alto = alto_t * len(tableros) + 40 * len(tableros) + 30
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
         f'font-family="Georgia, serif">',
         f'<rect width="100%" height="100%" fill="#faf8f4"/>']

    y_de_tablero = {}
    for t in tableros:
        y0 = 24 + t["indice"] * (alto_t + 40)
        y_de_tablero[t["indice"]] = y0
        s.append(_tablero_vacio(y0, columnas, t["indice"], len(tableros)))

    def punto_xy(punto, fila=0):
        tab, col, lado = punto
        return (col + 1) * PASO, _y_de(lado, fila, y_de_tablero[tab])

    # las pastillas
    for t in tableros:
        y0 = y_de_tablero[t["indice"]]
        for p in t["pastillas"]:
            s.append(_pastilla(p, y0))

    # la alimentacion: cada pin a su riel, por el camino corto
    for a in ruteo["alimentacion"]:
        tab, col, lado = a["punto"]
        y0 = y_de_tablero[tab]
        x = (col + 1) * PASO
        y = _y_de(lado, 0, y0)
        riel = _y_riel(y0, lado, a["nodo"])
        color = "#d62728" if a["nodo"] == "VCC" else "#222"
        s.append(f'<path d="M {x},{y} L {x},{riel}" stroke="{color}" '
                 f'stroke-width="2" fill="none" opacity="0.85"/>')
        s.append(f'<circle cx="{x}" cy="{riel}" r="2.6" fill="{color}"/>')

    # los cables de senal, con una curva suave para que se sigan con la vista
    for c in ruteo["cables"]:
        x1, y1 = punto_xy(c["de"]["punto"], 1)
        x2, y2 = punto_xy(c["a"]["punto"], 1)
        if c["de"]["punto"][0] != c["a"]["punto"][0]:
            # cable de un tablero a otro: recto, que se vea que cruza
            s.append(f'<path d="M {x1},{y1} L {x2},{y2}" fill="none" '
                     f'stroke="{c["color"]}" stroke-width="1.8" '
                     f'stroke-dasharray="5 3" opacity="0.85"/>')
            for x, y in ((x1, y1), (x2, y2)):
                s.append(f'<circle cx="{x}" cy="{y}" r="2.4" fill="{c["color"]}"/>')
            continue
        comba = min(34, 10 + abs(x2 - x1) * 0.18)
        cy = min(y1, y2) - comba if y1 < y2 else max(y1, y2) + comba
        s.append(f'<path d="M {x1},{y1} Q {(x1 + x2) / 2},{cy} {x2},{y2}" '
                 f'fill="none" stroke="{c["color"]}" stroke-width="1.8" opacity="0.9"/>')
        for x, y in ((x1, y1), (x2, y2)):
            s.append(f'<circle cx="{x}" cy="{y}" r="2.4" fill="{c["color"]}"/>')

    # puentes de + y - entre tableros
    for t in tableros[:-1]:
        y0 = y_de_tablero[t["indice"]]
        y1 = y_de_tablero[t["indice"] + 1]
        for dx, color, arriba in ((PASO * 1.2, "#d62728", True), (PASO * 2.4, "#222", False)):
            ya = y0 + alto_t - PASO * (1.0 if arriba else 2.0)
            yb = y1 + PASO * (1.0 if arriba else 2.0)
            s.append(f'<path d="M {dx},{ya} L {dx},{yb}" stroke="{color}" '
                     f'stroke-width="2.4" fill="none"/>')
        s.append(f'<text x="{PASO * 3.2:.0f}" y="{y0 + alto_t + 22}" font-size="11" '
                 f'fill="#666">puentes de + y - al siguiente tablero</text>')

    if titulo:
        s.append(f'<text x="{PASO}" y="16" font-size="13" fill="#333">{titulo}</text>')
    s.append("</svg>")
    return "\n".join(s)


def _tablero_vacio(y0, columnas, indice, total):
    alto = ALTO_TABLERO
    ancho = (columnas + 2) * PASO
    cy = _centro(y0)
    s = [f'<rect x="{PASO * 0.5:.0f}" y="{y0 + 3}" width="{ancho:.0f}" height="{alto}" '
         f'rx="5" fill="#000" opacity="0.13"/>',
         f'<rect x="{PASO * 0.5:.0f}" y="{y0}" width="{ancho:.0f}" height="{alto}" '
         f'rx="5" fill="#efe9dc" stroke="#cdc4b2"/>']
    # el canal del centro, hundido
    s.append(f'<rect x="{PASO * 0.5:.0f}" y="{cy - CANAL / 2:.1f}" width="{ancho:.0f}" '
             f'height="{CANAL}" fill="#e3ddce"/>')
    s.append(f'<rect x="{PASO * 0.5:.0f}" y="{cy - CANAL / 2:.1f}" width="{ancho:.0f}" '
             f'height="2.5" fill="#000" opacity="0.12"/>')
    # los rieles de alimentacion, arriba y abajo
    for lado in ("arriba", "abajo"):
        for nodo, color in (("VCC", "#c0392b"), ("GND", "#2c3e50")):
            yy = _y_riel(y0, lado, nodo)
            s.append(f'<line x1="{PASO * 1.2:.0f}" y1="{yy:.1f}" x2="{ancho:.0f}" '
                     f'y2="{yy:.1f}" stroke="{color}" stroke-width="1.2" opacity="0.5"/>')
            s.append(f'<text x="{PASO * 0.75:.0f}" y="{yy + 3.5:.1f}" font-size="11" '
                     f'fill="{color}" text-anchor="middle">'
                     f'{"+" if nodo == "VCC" else "−"}</text>')
    # los agujeros
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


def _pastilla(p, y0):
    """El encapsulado a caballo del canal, con su relieve."""
    ancho_cols = columnas_de(p["pines"])
    x0 = (p["col0"] + 1) * PASO - PASO * 0.45
    w = (ancho_cols - 1) * PASO + PASO * 0.9
    cy = _centro(y0)
    # el cuerpo cubre el canal y llega casi hasta la primera fila de agujeros,
    # sin taparla: ahi es donde se clavan sus patas
    h = min(CANAL + PASO * 0.9, 2 * (CANAL / 2 + PASO * 0.5) - 2)
    y = cy - h / 2
    s = [f'<rect x="{x0 + 1.5:.1f}" y="{y + 2.5:.1f}" width="{w:.1f}" height="{h:.1f}" '
         f'rx="2" fill="#000" opacity="0.32"/>',
         f'<rect x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" '
         f'fill="#2f3237" stroke="#15171a"/>',
         f'<rect x="{x0 + 1:.1f}" y="{y + 1:.1f}" width="{w - 2:.1f}" '
         f'height="{h * 0.16:.1f}" rx="1" fill="#ffffff" opacity="0.17"/>',
         f'<rect x="{x0 + 1:.1f}" y="{y + h - h * 0.15:.1f}" width="{w - 2:.1f}" '
         f'height="{h * 0.13:.1f}" rx="1" fill="#000000" opacity="0.30"/>']
    # la muesca, del lado del pin 1
    s.append(f'<path d="M {x0},{cy - PASO * 0.32:.1f} A {PASO * 0.32:.1f},'
             f'{PASO * 0.32:.1f} 0 0 1 {x0},{cy + PASO * 0.32:.1f}" fill="#15171a"/>')
    s.append(f'<text x="{x0 + w / 2:.1f}" y="{cy + 3.2:.1f}" font-size="8.5" '
             f'fill="#d5d9de" text-anchor="middle">{p["ref"]} {p["chip"]}</text>')
    # las patitas, de la orilla del encapsulado a su agujero
    for pin in range(1, p["pines"] + 1):
        col, lado = posicion_del_pin(pin, p["pines"], p["col0"])
        x = (col + 1) * PASO
        yy = _y_de(lado, 0, y0)
        borde = y + h if lado == "abajo" else y
        s.append(f'<line x1="{x}" y1="{borde:.1f}" x2="{x}" y2="{yy:.1f}" '
                 f'stroke="#c9ccd1" stroke-width="2.4"/>')
        s.append(f'<circle cx="{x}" cy="{yy:.1f}" r="2.3" fill="#b9bdc4" '
                 f'stroke="#8a8f96" stroke-width="0.4"/>')
    return "".join(s)


def dibujar(net, columnas=COLUMNAS, titulo=""):
    """Todo junto: coloca, rutea y dibuja. Devuelve (svg, ruteo, tableros)."""
    tableros = colocar(net, columnas)
    ruteo = rutear(net, tableros, columnas)
    return svg(net, tableros, ruteo, columnas, titulo), ruteo, tableros
