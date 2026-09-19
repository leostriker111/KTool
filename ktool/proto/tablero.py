"""La protoboard: donde va cada pieza y por donde va cada cable.

Una protoboard de 63 columnas. Cada columna son dos grupos de cinco agujeros
conectados entre si --uno arriba del canal y otro abajo-- y los rieles de + y -
corren a lo largo, arriba y abajo del todo.

El acomodo y el dibujo viven aqui; la matriz de la protoboard y la busqueda de
camino viven en `rejilla.py`.

**De donde sale un cable.** Nunca de la patita del chip: de uno de los otros
cuatro agujeros de esa misma columna, que electricamente son el mismo nodo.
Por eso de una entrada pueden salir varios cables y no uno. Si una columna se
llena, sirve cualquier otra que ya sea del mismo nodo, y si todas se llenan, el
nodo se estira a una columna vacia, que da cuatro agujeros mas.

**Por donde va.** Lo busca un A* sobre la rejilla: las celdas por donde ya paso
otro cable cuestan mas pero no estan prohibidas --dos jumpers se montan uno
sobre otro-- y el cuerpo de un componente si lo esta. Por eso los cables no
salen en escalerita y aprovechan el hueco libre. Todos los tramos son rectos.

**Un cable por destino, desde la fuente.** Encadenar saldria mas corto, pero un
cable que une las entradas de dos compuertas distintas no puede llevar un solo
color, y el color por compuerta es justo lo que se quiere:

**Los colores dicen algo.** Los cables que entran a una misma compuerta van del
mismo color, para que se vea de un golpe que van juntos. Las salidas del
circuito llevan su propio color, y ese si se elige: arcoiris, o uno fijo por
nombre o por hex.
"""

from __future__ import annotations

from . import chips, rejilla
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

AIRE = 22                # renglones de rejilla por fuera del tablero, cada lado
PASO_AIRE = PASO * 0.55


def y_de_nivel(rej, i, y0):
    """Altura en pixeles del renglon `i` de la rejilla."""
    tipo, lado, k = rej.niveles[i]
    if tipo == rejilla.CANAL:
        return _centro(y0)
    if tipo == rejilla.AGUJERO:
        return _y_de(lado, k, y0)
    if tipo == rejilla.AIRE:
        borde = _y_de(lado, FILAS - 1, y0)
        return borde - k * PASO_AIRE if lado == "arriba" else borde + k * PASO_AIRE
    # renglon de en medio: entre su agujero y el siguiente hacia el canal
    salto = PASO / 2 if k >= 1 else PASO * 0.25
    y = _y_de(lado, k, y0)
    return y + salto if lado == "arriba" else y - salto


def _anclas_del_nodo(conexiones, mapa):
    anclas = []
    for c in conexiones:
        punto = mapa.get((c["ref"], c["pin"]))
        if punto is not None:
            anclas.append((punto, c))
    return anclas


def rutear(net, tableros, columnas=COLUMNAS, salidas_color=None):
    """Cablea sobre la matriz: del agujero libre mas cercano, no de la patita.

    1. Se llena la matriz de pistas: de quien es cada columna y que agujero de
       los cinco esta ocupado.
    2. Cada nodo se recorre en cadena, de ancla en ancla. Cada extremo toma el
       agujero libre mas cercano de su columna; si no queda ninguno, el nodo se
       estira a una columna vacia, que da cinco agujeros mas.
    3. El camino se busca con A* sobre la rejilla de ruteo.
    """
    mapa = mapa_de_pines(tableros)
    color_de_pin = _colores_por_pin(net, salidas_color)

    rejs = {}
    for t in tableros:
        r = rejilla.Rejilla(t, columnas, FILAS, AIRE)
        for pieza in t["piezas"]:
            r.bloquear_pieza(pieza)
        rejs[t["indice"]] = r

    # matriz de pistas: cada pin se clava en la fila 0 de su columna
    nodo_de_pin = {}
    for nodo, conexiones in net["nodos"].items():
        for c in conexiones:
            nodo_de_pin[(c["ref"], c["pin"])] = nodo
    for (ref, pin), (tab, col, lado) in mapa.items():
        rejs[tab].clavar(lado, col, 0, f"{ref}-{pin}",
                         nodo_de_pin.get((ref, pin)))

    cables, alimentacion, sueltos, avisos = [], [], [], []

    def agarre(tab, lado, col, nodo, quien):
        """Un agujero libre del nodo, empezando por la columna del pin.

        Si esa se lleno, sirve cualquier otra columna que ya sea del mismo
        nodo. Y si todas estan llenas, se estira a una columna vacia: esa pasa
        a ser del nodo y da cuatro agujeros mas.
        """
        r = rejs[tab]
        suyas = [(lado, col)] + [(l, c) for (l, c) in r.columnas_del_nodo(nodo)
                                 if (l, c) != (lado, col)]
        cerca = sorted(suyas, key=lambda lc: (lc[0] != lado, abs(lc[1] - col)))
        for l, c in cerca:
            fila = r.agujero_libre(l, c)
            if fila is not None:
                r.clavar(l, c, fila, quien, nodo)
                return (tab, l, c, fila), None

        # todas llenas: se estira desde la que todavia guarde su reserva
        for l, c in cerca:
            reserva = r.agujero_de_reserva(l, c)
            nueva = r.columna_vacia(c, l) if reserva is not None else None
            if nueva is None:
                continue
            r.clavar(l, c, reserva, f"{nodo} (estira)", nodo)
            r.clavar(l, nueva, 1, f"{nodo} (estira)", nodo)
            estiramiento = ((tab, l, c, reserva), (tab, l, nueva, 1))
            fila = r.agujero_libre(l, nueva)
            r.clavar(l, nueva, fila, quien, nodo)
            return (tab, l, nueva, fila), estiramiento

        avisos.append(f"el nodo {nodo} se quedo sin agujeros cerca de la "
                      f"columna {col}")
        return (tab, lado, col, max(1, r.filas - 1)), None

    for nodo, conexiones in sorted(net["nodos"].items()):
        anclas = _anclas_del_nodo(conexiones, mapa)
        faltan = [c for c in conexiones if mapa.get((c["ref"], c["pin"])) is None]
        for c in faltan:
            sueltos.append((nodo, c["ref"], c["pin"]))

        if nodo in ("VCC", "GND"):
            for (tab, col, lado), c in anclas:
                alimentacion.append({"nodo": nodo, "ref": c["ref"], "pin": c["pin"],
                                     "punto": (tab, col, lado),
                                     "fila": rejs[tab].agujero_libre(lado, col) or 1})
            continue
        if len(anclas) < 2:
            continue

        # estrella desde la fuente: un cable por destino. Encadenar saldria mas
        # corto, pero un cable que une las entradas de DOS compuertas no puede
        # llevar un solo color, y el color por compuerta es lo que se pidio.
        idx = 0
        for i, (_, c) in enumerate(anclas):
            if "salida" in (c.get("papel") or ""):
                idx = i
                break
        anclas.sort(key=lambda a: (a[0][0], a[0][2], a[0][1]))
        fuente = next((a for a in anclas
                       if "salida" in (a[1].get("papel") or "")), anclas[idx])
        pf, cf = fuente
        for punto, c in anclas:
            if (punto, c) == fuente:
                continue
            color = (color_de_pin.get((c["ref"], c["pin"]))
                     or color_de_pin.get((cf["ref"], cf["pin"]))
                     or _color_de(len(cables)))
            a1, ext1 = agarre(pf[0], pf[2], pf[1], nodo, f"{cf['ref']}-{cf['pin']}")
            a2, ext2 = agarre(punto[0], punto[2], punto[1], nodo,
                              f"{c['ref']}-{c['pin']}")
            for ext in (ext1, ext2):
                if ext:
                    cables.append(_cable(rejs, nodo, color, ext[0], ext[1],
                                         f"{nodo}: estira a una columna vacia"))
            cables.append(_cable(rejs, nodo, color, a1, a2,
                                 f"{cf['ref']}-{cf['pin']} -> {c['ref']}-{c['pin']}"))

    _desfasar(cables, rejs)
    return {"cables": cables, "alimentacion": alimentacion, "mapa": mapa,
            "sueltos": sueltos, "avisos": avisos, "rejillas": rejs}


DESFASE = 2.4      # pixeles entre dos cables que corren pegados


def _desfasar(cables, rejs):
    """A los cables que comparten tramo se les da un desfase distinto.

    Donde dos jumpers corren pegados --y en la columna de un agujero no hay de
    otra-- se dibujan separados un poco, como se ven de verdad: dos cables uno
    al lado del otro, no uno encima del otro.

    Es un coloreo de grafos: los que se pisan son vecinos, y cada quien toma el
    desfase mas chico que no use ningun vecino.
    """
    duenos = {}
    for i, cable in enumerate(cables):
        for tab, camino in cable["tramos"]:
            for a, b in zip(camino, camino[1:]):
                duenos.setdefault((tab, rejs[tab]._arista(a, b)), []).append(i)

    vecinos = {i: set() for i in range(len(cables))}
    for quienes in duenos.values():
        if len(quienes) < 2:
            continue
        for i in quienes:
            vecinos[i].update(q for q in quienes if q != i)

    for i, cable in enumerate(cables):
        usados = {cables[v].get("desfase", 0) for v in vecinos[i] if v < i}
        k = 0
        while k in usados:
            k += 1
        cable["desfase"] = k

    # se centra con el mismo tope para todos: si se centrara por vecindario,
    # dos cables pegados podrian caer en el mismo valor y volverse a encimar
    tope = max((c["desfase"] for c in cables), default=0)
    for cable in cables:
        cable["desfase"] = (cable["desfase"] - tope / 2) * DESFASE


def _columna_de_salto(r1, r2, cerca_de, nivel_salida, nivel_entrada):
    """Una columna libre en los dos tableros para cruzar de uno al otro."""
    for d in range(0, r1.columnas):
        for col in ({cerca_de - d, cerca_de + d} if d else {cerca_de}):
            if not 1 <= col <= r1.columnas:
                continue
            if r1.usado.get((col, nivel_salida)) or r2.usado.get((col, nivel_entrada)):
                continue
            return col
    return cerca_de


def _cable(rejs, nodo, color, a, b, etiqueta):
    """Busca el camino de un agujero a otro y lo marca en la rejilla."""
    (tab1, lado1, col1, fila1), (tab2, lado2, col2, fila2) = a, b
    cable = {"nodo": nodo, "color": color, "a1": a, "a2": b, "etiqueta": etiqueta,
             "tramos": []}
    if tab1 == tab2:
        r = rejs[tab1]
        camino = r.camino_libre((col1, r.nivel_de[(lado1, fila1)]),
                                 (col2, r.nivel_de[(lado2, fila2)]))
        if camino:
            r.marcar_camino(camino)
            cable["tramos"] = [(tab1, camino)]
        return cable

    # de un tablero a otro: cada mitad hasta el aire, y un salto derecho.
    # La columna por donde se sale se busca libre; si todos los cables salieran
    # por la misma, esa se congestiona y el resto acaba compartiendo tramo.
    r1, r2 = rejs[tab1], rejs[tab2]
    nivel_salida, nivel_entrada = len(r1.niveles) - 1, 0
    puente = _columna_de_salto(r1, r2, col1, nivel_salida, nivel_entrada)
    salida, entrada = (puente, nivel_salida), (puente, nivel_entrada)
    c1 = r1.camino_libre((col1, r1.nivel_de[(lado1, fila1)]), salida)
    c2 = r2.camino_libre(entrada, (col2, r2.nivel_de[(lado2, fila2)]))
    if c1:
        r1.marcar_camino(c1)
        cable["tramos"].append((tab1, c1))
    if c2:
        r2.marcar_camino(c2)
        cable["tramos"].append((tab2, c2))
    cable["salta"] = True
    return cable


# ---------------------------------------------------------------- dibujo

def _margen_de_aire():
    """Lo que sobresale la rejilla de ruteo por fuera del tablero."""
    return AIRE * PASO_AIRE + PASO * 1.2


def svg(net, tableros, ruteo, columnas=COLUMNAS, titulo=""):
    """Dibuja los tableros, sus piezas y sus cables."""
    ancho = int((columnas + 3) * PASO)
    fuera = _margen_de_aire()

    y_de_tablero, y = {}, 26 + fuera
    for t in tableros:
        y_de_tablero[t["indice"]] = y
        y += ALTO_TABLERO + 2 * fuera + 26
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

    # --- alimentacion: del agujero libre al riel, no de la patita
    for a in ruteo["alimentacion"]:
        tab, col, lado = a["punto"]
        y0 = y_de_tablero[tab]
        x = x_de(col)
        y1 = _y_de(lado, a.get("fila", 1), y0)
        y2 = _y_riel(y0, lado, a["nodo"])
        color = "#c0392b" if a["nodo"] == "VCC" else "#2c3e50"
        s.append(f'<line x1="{x}" y1="{y1:.1f}" x2="{x}" y2="{y2:.1f}" '
                 f'stroke="{color}" stroke-width="2" opacity="0.9"/>')
        s.append(f'<circle cx="{x}" cy="{y1:.1f}" r="2.4" fill="{color}"/>')
        s.append(f'<circle cx="{x}" cy="{y2:.1f}" r="2.5" fill="{color}"/>')

    # --- los cables, siguiendo el camino que encontro el A*
    for cable in ruteo["cables"]:
        s.append(_dibuja_cable(cable, ruteo["rejillas"], y_de_tablero, x_de))

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


def _con_desfase(puntos, d):
    """Corre el trazo para que no quede encima de otro, sin sacar las puntas.

    Se mueve todo el camino en diagonal --asi las horizontales se separan a lo
    alto y las verticales a lo ancho, la misma cantidad-- pero los extremos se
    dejan clavados en su agujero, y el enganche se hace con un quiebre en
    angulo recto, nunca con una diagonal.
    """
    medio = [(x + d, y + d) for x, y in puntos[1:-1]]

    def enganche(punta, vecino_original, vecino_movido):
        """El punto que une la punta con el trazo corrido, en escuadra."""
        if abs(punta[0] - vecino_original[0]) < 0.01:      # tramo vertical
            return (punta[0], vecino_movido[1])
        return (vecino_movido[0], punta[1])

    inicio = enganche(puntos[0], puntos[1], medio[0])
    final = enganche(puntos[-1], puntos[-2], medio[-1])
    return [puntos[0], inicio] + medio + [final, puntos[-1]]


def _simplifica(puntos):
    """Quita los puntos de en medio de un tramo recto."""
    if len(puntos) < 3:
        return puntos
    salida = [puntos[0]]
    for anterior, medio, siguiente in zip(puntos, puntos[1:], puntos[2:]):
        d1 = (medio[0] - anterior[0], medio[1] - anterior[1])
        d2 = (siguiente[0] - medio[0], siguiente[1] - medio[1])
        if (d1[0] == 0) != (d2[0] == 0) or (d1[1] == 0) != (d2[1] == 0):
            salida.append(medio)
    salida.append(puntos[-1])
    return salida


def _dibuja_cable(cable, rejs, y_de_tablero, x_de):
    color = cable["color"]
    desfase = cable.get("desfase", 0)
    s = []
    for tab, camino in cable["tramos"]:
        rej = rejs[tab]
        y0 = y_de_tablero[tab]
        puntos = [(x_de(col), y_de_nivel(rej, niv, y0))
                  for col, niv in _simplifica(camino)]
        if len(puntos) < 2:
            continue
        if desfase and len(puntos) > 2:
            puntos = _con_desfase(puntos, desfase)
        d = " ".join(("M" if i == 0 else "L") + f" {x:.1f},{y:.1f}"
                     for i, (x, y) in enumerate(puntos))
        s.append(f'<path class="cable" d="{d}" fill="none" stroke="{color}" '
                 f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    # las puntas: donde se clava el cable
    for tab, camino in cable["tramos"]:
        rej, y0 = rejs[tab], y_de_tablero[tab]
        for col, niv in (camino[0], camino[-1]):
            if rej.niveles[niv][0] == rejilla.AGUJERO:
                s.append(f'<circle cx="{x_de(col)}" '
                         f'cy="{y_de_nivel(rej, niv, y0):.1f}" r="2.6" '
                         f'fill="{color}"/>')
    # salto de un tablero a otro: recto por la misma columna
    if cable.get("salta") and len(cable["tramos"]) == 2:
        (t1, c1), (t2, c2) = cable["tramos"]
        x = x_de(c1[-1][0])
        y1 = y_de_nivel(rejs[t1], c1[-1][1], y_de_tablero[t1])
        y2 = y_de_nivel(rejs[t2], c2[0][1], y_de_tablero[t2])
        s.append(f'<line x1="{x}" y1="{y1:.1f}" x2="{x_de(c2[0][0])}" y2="{y2:.1f}" '
                 f'stroke="{color}" stroke-width="2"/>')
    return "".join(s)


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
