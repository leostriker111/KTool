"""La protoboard como dos matrices: la de pistas y la de ruteo.

**Matriz de pistas.** Cada columna de la protoboard es un nodo: cinco agujeros
conectados entre si. La matriz guarda de quien es cada columna y cual de sus
agujeros esta ocupado. Un cable **nunca sale de la patita del chip**: toma el
agujero libre mas cercano de esa misma columna, que electricamente es lo mismo.
Y como sobran cuatro, de una entrada pueden salir cuatro cables, no uno.

Si una columna se queda sin agujeros, se tira un cable a una **columna vacia**:
esa columna pasa a ser del mismo nodo y da cinco agujeros mas. Es lo que harias
a mano.

**Matriz de ruteo.** Una rejilla sobre el tablero donde se marca por donde pasa
cada cable. El camino se busca con A*: las celdas por donde ya paso otro cable
cuestan mas pero no estan prohibidas --dos jumpers pueden cruzarse, se montan
uno sobre otro-- y el cuerpo de un componente si esta prohibido. Por eso los
cables no salen en escalerita y aprovechan el hueco que queda libre.

Los renglones de la rejilla alternan: un renglon por cada fila de agujeros y uno
**entre** cada par. Los cables corren por los de en medio y solo se clavan en
los de agujero, asi no se confunde un cable que pasa con uno que entra.
"""

from __future__ import annotations

import heapq

AGUJERO, ENTRE, AIRE, CANAL = "agujero", "entre", "aire", "canal"


class Rejilla:
    """La matriz de un tablero: pistas, agujeros y por donde van los cables."""

    def __init__(self, tablero, columnas, filas=5, aire=6):
        self.indice = tablero["indice"]
        self.columnas = columnas
        self.filas = filas
        self.niveles = self._armar_niveles(filas, aire)
        self.nivel_de = {}
        for i, n in enumerate(self.niveles):
            if n[0] == AGUJERO:
                self.nivel_de[(n[1], n[2])] = i

        self.es_agujero = {i for i, n in enumerate(self.niveles) if n[0] == AGUJERO}

        self.dueno = {}        # (lado, col) -> nodo que manda en esa columna
        self.ocupado = {}      # (lado, col, fila) -> quien clava ahi
        self.bloqueado = set()  # (col, nivel) por donde no se puede pasar
        self.usado = {}        # (col, nivel) -> cuantos cables cruzaron la celda
        self.aristas = {}      # tramo (celda, celda) -> cuantos cables lo recorren

    # ------------------------------------------------------------ armado

    @staticmethod
    def _armar_niveles(filas, aire):
        """De arriba hacia abajo: aire, agujeros de arriba, canal, agujeros de
        abajo, aire. Con un renglon 'entre' entre cada par."""
        niveles = [(AIRE, "arriba", k) for k in range(aire, 0, -1)]
        for fila in range(filas - 1, -1, -1):
            niveles.append((AGUJERO, "arriba", fila))
            niveles.append((ENTRE, "arriba", fila))
        niveles.append((CANAL, None, 0))
        for fila in range(filas):
            niveles.append((ENTRE, "abajo", fila))
            niveles.append((AGUJERO, "abajo", fila))
        niveles += [(AIRE, "abajo", k) for k in range(1, aire + 1)]
        return niveles

    def bloquear_pieza(self, pieza):
        """El cuerpo de un componente: por ahi no pasa un cable."""
        cols = range(pieza["col0"], pieza["col0"] + pieza["ancho"])
        if pieza["montaje"] == "canal":
            objetivo = {CANAL}
            for i, n in enumerate(self.niveles):
                if n[0] in objetivo or (n[0] == ENTRE and n[2] == 0):
                    for c in cols:
                        self.bloqueado.add((c, i))
        else:
            for i, n in enumerate(self.niveles):
                if n[0] == ENTRE and n[1] == "abajo" and n[2] == 0:
                    for c in cols:
                        self.bloqueado.add((c, i))

    def clavar(self, lado, col, fila, quien, nodo=None):
        """Marca un agujero como ocupado y, si hace falta, dice de quien es la
        columna."""
        self.ocupado[(lado, col, fila)] = quien
        if nodo is not None:
            self.dueno[(lado, col)] = nodo

    # ------------------------------------------------ agujeros disponibles

    def agujero_libre(self, lado, col, con_reserva=True):
        """El agujero libre mas cercano al pin de esa columna, o None.

        La fila 0 es la del pin: los cables usan de la 1 en adelante. La ultima
        se guarda para el cable que estira el nodo a otra columna, que si no
        no habria de donde jalarlo cuando se llene.
        """
        tope = self.filas - 1 if con_reserva else self.filas
        for fila in range(1, tope):
            if (lado, col, fila) not in self.ocupado:
                return fila
        return None

    def agujero_de_reserva(self, lado, col):
        """El que se guardo para estirar el nodo."""
        fila = self.filas - 1
        return None if (lado, col, fila) in self.ocupado else fila

    def columnas_del_nodo(self, nodo):
        return [(lado, col) for (lado, col), n in self.dueno.items() if n == nodo]

    def columna_vacia(self, cerca_de, lado):
        """Una columna sin dueno, lo mas cerca posible. Para estirar un nodo
        cuando se le acabaron los agujeros."""
        for d in range(1, self.columnas):
            for col in (cerca_de - d, cerca_de + d):
                if not 1 <= col <= self.columnas:
                    continue
                if (lado, col) in self.dueno:
                    continue
                nivel = self.nivel_de.get((lado, 0))
                if nivel is not None and (col, nivel) in self.bloqueado:
                    continue
                return col
        return None

    # ------------------------------------------------------------- ruteo

    @staticmethod
    def _arista(a, b):
        return (a, b) if a <= b else (b, a)

    def buscar_camino(self, origen, destino, castigo_tramo=70, castigo_cruce=3,
                      castigo_vuelta=3, evitar_usadas=True):
        """A* de un agujero a otro. Devuelve [(col, nivel), ...] o None.

        Dos reglas mandan aqui:

        - **Las horizontales no corren a la altura de los pines.** En un renglon
          de agujeros solo se puede subir o bajar; para ir de lado hay que
          pasarse a un renglon de en medio. Asi un cable que va de largo no se
          confunde con uno que se clava.

        - **Dos cables no comparten tramo.** Se cuenta por *arista* --el trecho
          entre dos celdas-- y no por celda: cruzarse en un punto esta bien, dos
          jumpers se montan uno sobre otro; correr encimados por el mismo trecho
          no. La excepcion es la columna del propio agujero: un agujero solo
          tiene dos aristas de acceso --de lado no se puede-- asi que para
          salir hacia el aire hay que pasar por las de arriba. Eso es lo unico
          que queda pegado, y se dibuja con un **desfase** para que se vean los
          dos cables y no uno. Si aun asi no hay paso, se reintenta cobrando el
          tramo caro: mejor un cable encimado que un cable que no llega.
        """
        alto = len(self.niveles)
        # en la columna del propio agujero no hay de otra: para salir de la
        # fila 3 hacia el aire hay que pasar por la 4. Ahi se permite compartir.
        columnas_propias = {origen[0], destino[0]}

        def heuristica(celda):
            return abs(celda[0] - destino[0]) + abs(celda[1] - destino[1])

        abierto = [(heuristica(origen), 0, origen, None)]
        visto = {(origen, None): 0}
        padre = {}
        while abierto:
            _, costo, celda, direccion = heapq.heappop(abierto)
            if celda == destino:
                camino, clave = [celda], (celda, direccion)
                while clave in padre:
                    clave = padre[clave]
                    camino.append(clave[0])
                camino.reverse()
                return camino
            col, niv = celda
            for dc, dn in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if dc and niv in self.es_agujero:
                    continue            # de lado no, a la altura de los pines
                vecino = (col + dc, niv + dn)
                if not (1 <= vecino[0] <= self.columnas and 0 <= vecino[1] < alto):
                    continue
                if vecino in self.bloqueado and vecino != destino:
                    continue
                veces = self.aristas.get(self._arista(celda, vecino), 0)
                if veces and evitar_usadas and vecino[0] not in columnas_propias:
                    continue
                paso = (1 + veces * castigo_tramo
                        + self.usado.get(vecino, 0) * castigo_cruce)
                nueva_dir = (dc, dn)
                if direccion is not None and nueva_dir != direccion:
                    paso += castigo_vuelta
                nuevo = costo + paso
                clave = (vecino, nueva_dir)
                if nuevo < visto.get(clave, 1 << 30):
                    visto[clave] = nuevo
                    padre[clave] = (celda, direccion)
                    heapq.heappush(abierto, (nuevo + heuristica(vecino), nuevo,
                                             vecino, nueva_dir))
        return None

    def camino_libre(self, origen, destino):
        """Primero sin compartir un solo tramo; si no hay paso, cobrandolo."""
        camino = self.buscar_camino(origen, destino, evitar_usadas=True)
        if camino is None:
            camino = self.buscar_camino(origen, destino, evitar_usadas=False)
        return camino

    def marcar_camino(self, camino):
        for celda in camino:
            self.usado[celda] = self.usado.get(celda, 0) + 1
        for a, b in zip(camino, camino[1:]):
            arista = self._arista(a, b)
            self.aristas[arista] = self.aristas.get(arista, 0) + 1
