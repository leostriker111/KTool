"""La protoboard: donde va cada pastilla y por donde va cada cable.

Una protoboard de 63 columnas. Cada columna son dos grupos de cinco agujeros
conectados entre si --uno arriba del canal y otro abajo-- y los rieles de + y -
corren a lo largo, arriba y abajo del todo.

**Como se cablea.** Cada pin de un chip se clava en su propia columna, y esa
columna tiene otros cuatro agujeros libres del mismo nodo -- para eso esta hecha
la protoboard. Asi que un cable sale de uno de esos agujeros libres, corre en
horizontal por un **carril** y sube o baja por la columna de destino: puros
tramos rectos, nada de diagonales ni curvas.

Los carriles se reparten por intervalos: dos cables van por el mismo carril solo
si sus columnas no se traslapan. Eso es lo que evita que dos cables se crucen
yendo en paralelo. Cuando se acaban las cuatro filas libres, los carriles
siguientes corren por fuera del tablero, que es lo que pasa de verdad cuando
apilas jumpers.

Como cada pin pertenece a un solo nodo, **dos senales nunca comparten columna**:
eso sale de como esta hecha la protoboard, no hay nada que resolver ahi.

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


def _asigna_carriles(troncos):
    """Reparte los tramos horizontales en carriles que no se pisen.

    Dos cables pueden ir por el mismo carril si sus columnas no se traslapan.
    Es el mismo reparto por intervalos que ya usa el circuito combinado, y es
    lo que evita que un cable se cruce con otro yendo en paralelo.
    """
    carriles = []
    for tronco in sorted(troncos, key=lambda x: (x["col_min"], -x["col_max"])):
        for i, ocupado in enumerate(carriles):
            if all(tronco["col_max"] < a - 1 or tronco["col_min"] > b + 1
                   for a, b in ocupado):
                ocupado.append((tronco["col_min"], tronco["col_max"]))
                tronco["carril"] = i
                break
        else:
            carriles.append([(tronco["col_min"], tronco["col_max"])])
            tronco["carril"] = len(carriles) - 1
    return len(carriles)


def rutear(net, tableros, columnas=COLUMNAS):
    """Los cables, con angulos rectos y por carriles.

    Cada cable baja (o sube) por la **columna de su pin**, se mete en uno de los
    agujeros libres de esa misma columna --que son del mismo nodo, para eso
    esta la protoboard-- y corre en horizontal por un carril hasta la columna
    de destino. Nada de curvas: puros tramos rectos.
    """
    mapa = mapa_de_pines(tableros)

    def huecos_de(clave):
        for t in tableros:
            for col in t[clave]:
                yield t["indice"], col

    zona_e, zona_s = huecos_de("zona_entradas"), huecos_de("zona_salidas")
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

    # columnas tapadas por una pastilla: por ahi no conviene cruzar
    tapadas = {}
    for t in tableros:
        ocupadas = set()
        for p in t["pastillas"]:
            ocupadas.update(range(p["col0"], p["col0"] + columnas_de(p["pines"])))
        tapadas[t["indice"]] = ocupadas

    alimentacion, troncos, puentes = [], [], []
    for i, (nodo, conexiones) in enumerate(sorted(net["nodos"].items())):
        puntos = [(c, mapa.get((c["ref"], c["pin"]))) for c in conexiones]
        if nodo in ("VCC", "GND"):
            for c, punto in puntos:
                if punto is None:
                    sueltos.append((nodo, c["ref"], c["pin"]))
                else:
                    alimentacion.append({"nodo": nodo, "ref": c["ref"],
                                         "pin": c["pin"], "punto": punto})
            continue

        color = theme.WIRE_COLORS[i % len(theme.WIRE_COLORS)]
        grupos = {}
        for c, punto in puntos:
            if punto is None:
                sueltos.append((nodo, c["ref"], c["pin"]))
                continue
            tab, col, lado = punto
            grupos.setdefault((tab, lado), []).append((col, c))

        mios = []
        for (tab, lado), items in sorted(grupos.items()):
            cols = sorted(c for c, _ in items)
            tronco = {"nodo": nodo, "color": color, "tablero": tab, "lado": lado,
                      "col_min": cols[0], "col_max": cols[-1], "columnas": cols,
                      "carril": 0}
            troncos.append(tronco)
            mios.append(tronco)

        # un nodo repartido en varios grupos se une con un puente
        for a, b in zip(mios, mios[1:]):
            columna = _columna_de_puente(a, b, tapadas, columnas)
            puentes.append({"nodo": nodo, "color": color, "de": a, "a": b,
                            "columna": columna})

    # los carriles se reparten por zona: cada lado de cada tablero es un canal
    zonas = {}
    for tronco in troncos:
        zonas.setdefault((tronco["tablero"], tronco["lado"]), []).append(tronco)
    carriles_por_zona = {z: _asigna_carriles(ts) for z, ts in zonas.items()}

    return {"troncos": troncos, "puentes": puentes, "alimentacion": alimentacion,
            "mapa": mapa, "sueltos": sueltos, "por_ref": por_ref,
            "carriles": carriles_por_zona}


def _columna_de_puente(a, b, tapadas, columnas):
    """Una columna libre para cruzar de un lado (o tablero) al otro."""
    candidatas = sorted(set(a["columnas"]) | set(b["columnas"]))
    libres = [c for c in candidatas if c not in tapadas.get(a["tablero"], set())]
    if libres:
        return libres[0]
    cerca = min(candidatas) if candidatas else 1
    for d in range(columnas):
        for c in (cerca - d, cerca + d):
            if 1 <= c <= columnas and c not in tapadas.get(a["tablero"], set()):
                return c
    return cerca


# ------------------------------------------------------------------ dibujo

PASO = 15            # pixeles por columna (el paso real es 2.54 mm)
CANAL = PASO * 2     # el hueco del centro, por donde queda a caballo el chip
FILAS = 5            # agujeros por grupo, arriba y abajo
FILAS_LIBRES = FILAS - 1   # la fila 0 la ocupa el pin; las otras 4 son para cables

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


def _y_carril(lado, carril, y0):
    """Altura de un carril. Los primeros son filas libres de la protoboard;
    si se acaban, los demas corren por fuera del tablero."""
    if carril < FILAS_LIBRES:
        return _y_de(lado, carril + 1, y0)
    fuera = carril - FILAS_LIBRES
    d = _DEL_CENTRO_AL_BORDE + PASO * 2.9 + fuera * PASO * 0.62
    return _centro(y0) + (d if lado == "abajo" else -d)


def _carriles_fuera(ruteo, tablero_idx, lado):
    n = ruteo["carriles"].get((tablero_idx, lado), 0)
    return max(0, n - FILAS_LIBRES)


def _margenes(ruteo, tableros):
    """Cuanto espacio pide cada tablero arriba y abajo por los cables de fuera."""
    margen = {}
    for t in tableros:
        i = t["indice"]
        margen[i] = (
            PASO * 3.4 + _carriles_fuera(ruteo, i, "arriba") * PASO * 0.62,
            PASO * 3.4 + _carriles_fuera(ruteo, i, "abajo") * PASO * 0.62,
        )
    return margen


def svg(net, tableros, ruteo, columnas=COLUMNAS, titulo=""):
    """Dibuja los tableros, sus pastillas y sus cables.

    Los cables van con angulos rectos: bajan por la columna de su pin, se meten
    en un agujero libre de esa misma columna, corren por su carril y suben por
    la columna de destino.
    """
    margen = _margenes(ruteo, tableros)
    ancho = int((columnas + 3) * PASO)
    alto_t = ALTO_TABLERO

    y_de_tablero, y = {}, 26
    for t in tableros:
        arriba, abajo = margen[t["indice"]]
        y += arriba
        y_de_tablero[t["indice"]] = y
        y += alto_t + abajo + 26
    alto = int(y + 10)

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
         f'font-family="Georgia, serif">',
         f'<rect width="100%" height="100%" fill="#faf8f4"/>']

    for t in tableros:
        s.append(_tablero_vacio(y_de_tablero[t["indice"]], columnas,
                                t["indice"], len(tableros)))
        for p in t["pastillas"]:
            s.append(_pastilla(p, y_de_tablero[t["indice"]]))

    def x_de(col):
        return (col + 1) * PASO

    # --- alimentacion: derecho al riel de su lado, sin rodeos
    for a in ruteo["alimentacion"]:
        tab, col, lado = a["punto"]
        y0 = y_de_tablero[tab]
        x, y1 = x_de(col), _y_de(lado, 0, y0)
        y2 = _y_riel(y0, lado, a["nodo"])
        color = "#c0392b" if a["nodo"] == "VCC" else "#2c3e50"
        s.append(f'<line x1="{x}" y1="{y1:.1f}" x2="{x}" y2="{y2:.1f}" '
                 f'stroke="{color}" stroke-width="2" opacity="0.9"/>')
        s.append(f'<circle cx="{x}" cy="{y2:.1f}" r="2.5" fill="{color}"/>')
        s.append(f'<circle cx="{x}" cy="{y1:.1f}" r="2.2" fill="{color}"/>')

    # --- los troncos: una horizontal por carril y una vertical por pin
    for tronco in ruteo["troncos"]:
        y0 = y_de_tablero[tronco["tablero"]]
        yc = _y_carril(tronco["lado"], tronco["carril"], y0)
        color = tronco["color"]
        x1, x2 = x_de(tronco["col_min"]), x_de(tronco["col_max"])
        if x2 > x1:
            s.append(f'<line x1="{x1}" y1="{yc:.1f}" x2="{x2}" y2="{yc:.1f}" '
                     f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
        for col in tronco["columnas"]:
            x = x_de(col)
            yp = _y_de(tronco["lado"], 0, y0)
            s.append(f'<line x1="{x}" y1="{yp:.1f}" x2="{x}" y2="{yc:.1f}" '
                     f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
            # el agujero del pin y el agujero libre donde entra el cable
            s.append(f'<circle cx="{x}" cy="{yp:.1f}" r="2.4" fill="{color}"/>')
            s.append(f'<circle cx="{x}" cy="{yc:.1f}" r="2.4" fill="{color}"/>')

    # --- puentes entre lados o entre tableros, tambien en angulo recto
    canal_libre = [PASO * 4.2]
    for p in ruteo["puentes"]:
        a, b = p["de"], p["a"]
        ya = _y_carril(a["lado"], a["carril"], y_de_tablero[a["tablero"]])
        yb = _y_carril(b["lado"], b["carril"], y_de_tablero[b["tablero"]])
        if a["tablero"] != b["tablero"]:
            # cable largo de un tablero a otro: se va por la orilla, no por
            # encima de los agujeros
            x = canal_libre[0]
            canal_libre[0] += PASO * 0.55
            xa, xb = x_de(a["col_min"]), x_de(b["col_min"])
        else:
            x = x_de(p["columna"])
            xa = min(max(x, x_de(a["col_min"])), x_de(a["col_max"]))
            xb = min(max(x, x_de(b["col_min"])), x_de(b["col_max"]))
        trazo = (f'M {xa},{ya:.1f} L {x:.1f},{ya:.1f} L {x:.1f},{yb:.1f} '
                 f'L {xb},{yb:.1f}')
        s.append(f'<path d="{trazo}" fill="none" stroke="{p["color"]}" '
                 f'stroke-width="2" stroke-dasharray="6 3" opacity="0.95"/>')

    # --- puentes de alimentacion entre tableros
    for t in tableros[:-1]:
        y0, y1 = y_de_tablero[t["indice"]], y_de_tablero[t["indice"] + 1]
        for nodo, color, dx in (("VCC", "#c0392b", PASO * 1.0),
                                ("GND", "#2c3e50", PASO * 1.9)):
            ya = _y_riel(y0, "abajo", nodo)
            yb = _y_riel(y1, "arriba", nodo)
            s.append(f'<path d="M {dx:.0f},{ya:.1f} L {dx:.0f},{yb:.1f}" '
                     f'stroke="{color}" stroke-width="2.4" fill="none"/>')
        s.append(f'<text x="{PASO * 3:.0f}" y="{(ya + yb) / 2:.0f}" font-size="10" '
                 f'fill="#777">puentes de + y &#8722;</text>')

    if titulo:
        s.append(f'<text x="{PASO}" y="18" font-size="13" fill="#333">'
                 f'{_esc_svg(titulo)}</text>')
    s.append("</svg>")
    return "\n".join(s)


def _esc_svg(txt):
    return (str(txt).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


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
