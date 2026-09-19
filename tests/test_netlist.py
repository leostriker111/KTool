"""El netlist y la protoboard: que lo dibujado se pueda armar y funcione.

La prueba que importa: se arma el netlist, se **evalua como circuito** --pin por
pin, compuerta por compuerta-- y se compara contra la tabla de verdad que lo
origino. Si el netlist dice otra cosa que las ecuaciones, aqui se cae.
"""

import itertools
import random
import unittest
import xml.etree.ElementTree as ET

from ktool.core.simplify import solve_output
from ktool.core.table import TruthTable
from ktool.proto import chips, netlist, rejilla, seleccion, tablero

FORMAS = ("sop", "pos", "nand", "nor")
CAJON = ["7400", "7402", "7404", "7408", "7432"]


def bcd_siete_segmentos():
    digitos = {0: "abcdef", 1: "bc", 2: "abdeg", 3: "abcdg", 4: "bcfg",
               5: "acdfg", 6: "acdefg", 7: "abc", 8: "abcdefg", 9: "abcdfg"}
    salidas = {s: ["x" if i > 9 else (1 if s in digitos[i] else 0) for i in range(16)]
               for s in "abcdefg"}
    return TruthTable(4, outputs=salidas)


def soluciones(tabla, forma):
    return [(n, solve_output(v, tabla.variables)[forma])
            for n, v in tabla.outputs.items()]


class HaceLoQueDicenLasEcuaciones(unittest.TestCase):
    """La prueba de fuego: evaluar el netlist contra la tabla de verdad."""

    def test_decodificador_bcd_en_toda_combinacion(self):
        tabla = bcd_siete_segmentos()
        for forma in FORMAS:
            sols = soluciones(tabla, forma)
            for modo, forzados in ((seleccion.FIEL, None),
                                   (seleccion.AUTOMATICO, None),
                                   (seleccion.FORZADO, CAJON)):
                net = netlist.construir(sols, forma, modo, forzados,
                                        extremos="7seg_cc")
                problemas = netlist.comprobar(net, tabla)
                self.assertEqual(problemas, [],
                                 f"{forma} en modo {modo}: {problemas[:3]}")
                self.assertTrue(net["completo"])

    def test_tablas_chicas_exhaustivas(self):
        """Todas las tablas de 2 variables con dos salidas, en las 4 formas."""
        for a in itertools.product([0, 1, "x"], repeat=4):
            for b in ([1, 0, 0, 1], [0, 0, 1, 1]):
                tabla = TruthTable(2, outputs={"Y0": list(a), "Y1": b})
                for forma in FORMAS:
                    net = netlist.construir(soluciones(tabla, forma), forma)
                    self.assertEqual(netlist.comprobar(net, tabla), [],
                                     f"{forma} con {a}")

    def test_al_azar_de_tres_y_cuatro_variables(self):
        random.seed(77)
        for n in (3, 4):
            for _ in range(15):
                salidas = {f"Y{k}": [random.choice([0, 1, "x"]) for _ in range(1 << n)]
                           for k in range(3)}
                tabla = TruthTable(n, outputs=salidas)
                for forma in FORMAS:
                    net = netlist.construir(soluciones(tabla, forma), forma)
                    self.assertEqual(netlist.comprobar(net, tabla), [], f"{forma}")


class LaCascadaConservaLaLogica(unittest.TestCase):
    """Partir una compuerta ancha no puede cambiar lo que hace."""

    def test_forzar_chips_angostos_no_cambia_la_funcion(self):
        tabla = bcd_siete_segmentos()
        for forma in FORMAS:
            net = netlist.construir(soluciones(tabla, forma), forma,
                                    seleccion.FORZADO, ["7400", "7402", "7404",
                                                        "7408", "7432"])
            self.assertEqual(netlist.comprobar(net, tabla), [], forma)

    def test_con_chips_angostos_hacen_falta_mas_compuertas(self):
        tabla = bcd_siete_segmentos()
        anchos = netlist.construir(soluciones(tabla, "sop"), "sop", seleccion.FIEL)
        angostos = netlist.construir(soluciones(tabla, "sop"), "sop",
                                     seleccion.FORZADO, ["7408", "7432", "7404"])
        self.assertGreater(len(angostos["plan"].compuertas),
                           len(anchos["plan"].compuertas))


class NadaAlAire(unittest.TestCase):
    def test_toda_pastilla_alimentada_y_sin_pines_sueltos(self):
        tabla = bcd_siete_segmentos()
        for forma in FORMAS:
            net = netlist.construir(soluciones(tabla, forma), forma)
            conectados = {(c["ref"], c["pin"])
                          for cs in net["nodos"].values() for c in cs}
            for p in net["pastillas"]:
                vcc, gnd = chips.alimentacion(p["chip"])
                self.assertIn((p["ref"], vcc), conectados, f"{p['ref']} sin VCC")
                self.assertIn((p["ref"], gnd), conectados, f"{p['ref']} sin GND")
                for hueco in chips.compuertas(p["chip"]):
                    for pin in hueco["entradas"]:
                        self.assertIn((p["ref"], pin), conectados,
                                      f"{p['ref']} pin {pin} al aire")

    def test_una_senal_una_sola_fuente(self):
        tabla = bcd_siete_segmentos()
        for forma in FORMAS:
            net = netlist.construir(soluciones(tabla, forma), forma)
            salidas = [g.salida for g in net["plan"].compuertas]
            self.assertEqual(len(salidas), len(set(salidas)), forma)


class Extremos(unittest.TestCase):
    def test_los_leds_llevan_su_resistencia(self):
        tabla = TruthTable(2, outputs={"Y": [0, 1, 1, 0]})
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="led")
        tipos = [c["tipo"] for c in net["componentes"]]
        self.assertIn("led", tipos)
        self.assertIn("resistencia", tipos)

    def test_el_display_de_catodo_comun_va_a_GND(self):
        tabla = bcd_siete_segmentos()
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="7seg_cc")
        display = next(c for c in net["componentes"] if c["tipo"] == "display")
        comun = [c for c in net["nodos"]["GND"] if c["ref"] == display["ref"]]
        self.assertTrue(comun, "el comun del display deberia ir a GND")

    def test_el_anodo_comun_va_a_VCC_y_avisa_de_la_polaridad(self):
        tabla = bcd_siete_segmentos()
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="7seg_ca")
        display = next(c for c in net["componentes"] if c["tipo"] == "display")
        self.assertTrue([c for c in net["nodos"]["VCC"] if c["ref"] == display["ref"]])
        self.assertTrue(any("BAJO" in a for a in net["avisos"]),
                        "tiene que avisar que el anodo comun enciende en bajo")

    def test_si_faltan_segmentos_lo_dice(self):
        tabla = TruthTable(2, outputs={"a": [0, 1, 1, 0], "b": [1, 0, 0, 1]})
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="7seg_cc")
        self.assertTrue(any("segmentos" in a for a in net["avisos"]))


class ElTablero(unittest.TestCase):
    def _armar(self, forma="sop", columnas=tablero.COLUMNAS):
        tabla = bcd_siete_segmentos()
        net = netlist.construir(soluciones(tabla, forma), forma,
                                extremos="7seg_cc")
        svg, ruteo, tableros = tablero.dibujar(net, columnas)
        return net, svg, ruteo, tableros

    def test_ninguna_pastilla_se_encima(self):
        for forma in FORMAS:
            _, _, _, tableros = self._armar(forma)
            for t in tableros:
                ocupadas = {}
                for p in t["pastillas"]:
                    for col in range(p["col0"],
                                     p["col0"] + tablero.columnas_de(p["pines"])):
                        self.assertNotIn(col, ocupadas,
                                         f"{p['ref']} se encima con {ocupadas.get(col)}")
                        ocupadas[col] = p["ref"]

    def test_todo_cabe_en_el_tablero(self):
        for columnas in (30, 63):
            _, _, _, tableros = self._armar("sop", columnas)
            for t in tableros:
                for p in t["pastillas"]:
                    fin = p["col0"] + tablero.columnas_de(p["pines"]) - 1
                    self.assertLessEqual(fin, columnas, f"{p['ref']} se sale")
                    self.assertGreaterEqual(p["col0"], 1)

    def test_ningun_pin_se_queda_sin_agujero(self):
        for forma in FORMAS:
            _, _, ruteo, _ = self._armar(forma)
            self.assertEqual(ruteo["sueltos"], [], forma)

    def test_dos_senales_nunca_comparten_columna(self):
        """Sale de como esta hecha la protoboard, pero hay que fijarlo."""
        net, _, ruteo, _ = self._armar("sop")
        de_quien = {}
        for nodo, conexiones in net["nodos"].items():
            if nodo in ("VCC", "GND"):
                continue
            for c in conexiones:
                sitio = ruteo["mapa"].get((c["ref"], c["pin"]))
                if sitio is None:
                    continue
                if sitio in de_quien:
                    self.assertEqual(de_quien[sitio], nodo,
                                     f"la columna {sitio} la usan {de_quien[sitio]} y {nodo}")
                de_quien[sitio] = nodo

    def test_el_dibujo_es_xml_valido(self):
        for forma in FORMAS:
            _, svg, _, _ = self._armar(forma)
            ET.fromstring(svg)
            self.assertNotIn("nan", svg.lower())

    def test_con_un_tablero_chico_se_agregan_mas(self):
        _, _, _, muchos = self._armar("sop", 30)
        _, _, _, pocos = self._armar("sop", 63)
        self.assertGreater(len(muchos), len(pocos))

    def test_el_encapsulado_queda_a_caballo_del_canal(self):
        """La mitad de los pines de un lado del canal y la otra del otro."""
        for pines in (14, 16):
            lados = [tablero.posicion_del_pin(p, pines, 1)[1]
                     for p in range(1, pines + 1)]
            self.assertEqual(lados.count("abajo"), pines // 2)
            self.assertEqual(lados.count("arriba"), pines // 2)
        # el pin 1 y el ultimo comparten columna, en lados opuestos
        self.assertEqual(tablero.posicion_del_pin(1, 14, 5)[0],
                         tablero.posicion_del_pin(14, 14, 5)[0])


class CablesPlanchados(unittest.TestCase):
    """Nada de curvas ni diagonales, y nada de jalar de la patita del chip."""

    def _armar(self, forma="sop", salidas_color=None):
        tabla = bcd_siete_segmentos()
        net = netlist.construir(soluciones(tabla, forma), forma, extremos="7seg_cc")
        tableros = tablero.colocar(net)
        ruteo = tablero.rutear(net, tableros, salidas_color=salidas_color)
        return net, tablero.svg(net, tableros, ruteo), ruteo, tableros

    def test_ningun_tramo_va_en_diagonal(self):
        import re
        _, svg, _, _ = self._armar()
        caminos = re.findall(r'<path class="cable" d="(M [^"]*)"', svg)
        self.assertTrue(caminos, "no se dibujo ningun cable")
        for d in caminos:
            puntos = re.findall(r"([-\d.]+),([-\d.]+)", d)
            for (x1, y1), (x2, y2) in zip(puntos, puntos[1:]):
                recto = (abs(float(x1) - float(x2)) < 0.01
                         or abs(float(y1) - float(y2)) < 0.01)
                self.assertTrue(recto, f"tramo en diagonal: {d[:90]}")

    def test_no_quedan_curvas(self):
        _, svg, _, _ = self._armar()
        self.assertNotIn(" Q ", svg, "quedo una curva de Bezier")
        self.assertNotIn(" C ", svg)

    def test_ningun_cable_sale_de_la_patita(self):
        """La fila 0 es del pin. El cable toma un agujero libre de la misma
        columna, que electricamente es lo mismo."""
        for forma in FORMAS:
            _, _, ruteo, _ = self._armar(forma)
            for cable in ruteo["cables"]:
                for extremo in (cable["a1"], cable["a2"]):
                    self.assertGreaterEqual(
                        extremo[3], 1, f"{cable['etiqueta']} sale de la patita")

    def test_todos_los_cables_encuentran_camino(self):
        for forma in FORMAS:
            _, _, ruteo, _ = self._armar(forma)
            for cable in ruteo["cables"]:
                self.assertTrue(cable["tramos"], f"sin camino: {cable['etiqueta']}")

    def test_dos_cables_no_se_clavan_en_el_mismo_agujero(self):
        for forma in FORMAS:
            _, _, ruteo, _ = self._armar(forma)
            usados = {}
            for cable in ruteo["cables"]:
                for extremo in (cable["a1"], cable["a2"]):
                    previo = usados.get(extremo)
                    if previo is not None and previo != cable["nodo"]:
                        self.fail(f"{extremo}: lo usan {previo} y {cable['nodo']}")
                    usados[extremo] = cable["nodo"]

    def test_de_una_columna_pueden_salir_varios_cables(self):
        """Una columna tiene cuatro agujeros libres: hay que aprovecharlos."""
        _, _, ruteo, _ = self._armar()
        porcolumna = {}
        for cable in ruteo["cables"]:
            for (tab, lado, col, fila) in (cable["a1"], cable["a2"]):
                porcolumna.setdefault((tab, lado, col), set()).add(fila)
        self.assertTrue(any(len(f) > 1 for f in porcolumna.values()),
                        "ninguna columna presto mas de un agujero")

    def test_el_cuerpo_de_una_pieza_no_se_atraviesa(self):
        _, _, ruteo, _ = self._armar()
        for rej in ruteo["rejillas"].values():
            for celda in rej.usado:
                self.assertNotIn(celda, rej.bloqueado,
                                 f"un cable paso por {celda}, que esta bloqueado")


class LaRejilla(unittest.TestCase):
    """La matriz: de quien es cada columna y por donde se puede pasar."""

    def _rejilla(self):
        return rejilla.Rejilla({"indice": 0, "piezas": []}, 20, filas=5, aire=4)

    def test_los_renglones_alternan_agujero_y_medio(self):
        r = self._rejilla()
        tipos = [n[0] for n in r.niveles]
        self.assertIn(rejilla.CANAL, tipos)
        self.assertEqual(tipos.count(rejilla.AGUJERO), 10)

    def test_el_agujero_libre_es_el_mas_cercano_y_nunca_el_del_pin(self):
        r = self._rejilla()
        r.clavar("abajo", 3, 0, "U1-1", "G1")
        self.assertEqual(r.agujero_libre("abajo", 3), 1)
        r.clavar("abajo", 3, 1, "cable", "G1")
        self.assertEqual(r.agujero_libre("abajo", 3), 2)

    def test_cuando_se_acaban_los_agujeros_avisa(self):
        r = self._rejilla()
        for fila in range(5):
            r.clavar("abajo", 3, fila, "algo", "G1")
        self.assertIsNone(r.agujero_libre("abajo", 3))

    def test_una_columna_vacia_es_la_salida(self):
        """Estirar el nodo a una columna sin dueno da cinco agujeros mas."""
        r = self._rejilla()
        r.clavar("abajo", 3, 0, "U1-1", "G1")
        vacia = r.columna_vacia(3, "abajo")
        self.assertIsNotNone(vacia)
        self.assertNotEqual(vacia, 3)
        self.assertEqual(r.agujero_libre("abajo", vacia), 1)

    def test_el_camino_rodea_lo_bloqueado(self):
        r = self._rejilla()
        nivel = r.nivel_de[("abajo", 2)]
        for col in range(4, 9):
            r.bloqueado.add((col, nivel))
        camino = r.buscar_camino((2, nivel), (12, nivel))
        self.assertIsNotNone(camino)
        for celda in camino:
            self.assertNotIn(celda, r.bloqueado)

    def test_un_cable_ya_puesto_encarece_pero_no_prohibe(self):
        r = self._rejilla()
        nivel = r.nivel_de[("abajo", 2)]
        directo = r.buscar_camino((2, nivel), (10, nivel))
        for col in range(3, 10):
            r.usado[(col, nivel)] = 1
        rodeo = r.buscar_camino((2, nivel), (10, nivel))
        self.assertIsNotNone(rodeo)
        self.assertNotEqual(directo, rodeo, "no busco otro camino")


class LosColoresDicenAlgo(unittest.TestCase):
    def test_lo_que_entra_a_una_compuerta_va_del_mismo_color(self):
        tabla = bcd_siete_segmentos()
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="7seg_cc")
        tableros = tablero.colocar(net)
        ruteo = tablero.rutear(net, tableros)
        chip_de = {p["ref"]: p["chip"] for p in net["pastillas"]}
        for g in net["plan"].compuertas:
            if g.chip is None:
                continue
            hueco = chips.compuertas(chip_de[g.chip])[g.hueco]
            entradas = {f"{g.chip}-{pin}" for pin in hueco["entradas"]}
            # ojo: comparar exacto, que "U2-1" es subcadena de "U2-13"
            colores = {c["color"] for c in ruteo["cables"]
                       if c["etiqueta"].split(" -> ")[-1] in entradas}
            self.assertLessEqual(len(colores), 1,
                                 f"la compuerta {g.id} recibe {len(colores)} colores")

    def test_el_color_de_salida_se_puede_fijar(self):
        tabla = TruthTable(2, outputs={"Y": [0, 1, 1, 0]})
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="led")
        tableros = tablero.colocar(net)
        ruteo = tablero.rutear(net, tableros, salidas_color="#0b6e4f")
        hacia = [c for c in ruteo["cables"]
                 if "R1-" in c["etiqueta"] or "D1-" in c["etiqueta"]]
        self.assertTrue(hacia)
        for c in hacia:
            self.assertEqual(c["color"], "#0b6e4f")

    def test_acepta_nombre_y_hex_con_o_sin_gato(self):
        self.assertEqual(tablero._resolver_color("red", 0), "red")
        self.assertEqual(tablero._resolver_color("1f77b4", 0), "#1f77b4")
        self.assertEqual(tablero._resolver_color("#1f77b4", 0), "#1f77b4")
        arcoiris = {tablero._resolver_color("arcoiris", k) for k in range(5)}
        self.assertGreater(len(arcoiris), 1, "arcoiris deberia variar")


class LasPiezasSeVenComoSon(unittest.TestCase):
    """Una resistencia ocupa dos columnas, no dos 'salidas' sueltas."""

    def test_la_resistencia_y_el_led_ocupan_dos_columnas(self):
        tabla = TruthTable(2, outputs={"Y": [0, 1, 1, 0]})
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="led")
        piezas = {p["tipo"]: p for t in tablero.colocar(net) for p in t["piezas"]}
        self.assertEqual(piezas["resistencia"]["ancho"], 2)
        self.assertEqual(piezas["led"]["ancho"], 2)

    def test_el_display_va_a_caballo_del_canal(self):
        tabla = bcd_siete_segmentos()
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="7seg_cc")
        display = next(p for t in tablero.colocar(net) for p in t["piezas"]
                       if p["tipo"] == "display")
        self.assertEqual(display["montaje"], "canal")
        self.assertEqual(display["ancho"], 4)   # 8 pines

    def test_ningun_tablero_queda_vacio(self):
        """No se abre una protoboard de adorno."""
        for forma in FORMAS:
            tabla = bcd_siete_segmentos()
            net = netlist.construir(soluciones(tabla, forma), forma,
                                    extremos="7seg_cc")
            for t in tablero.colocar(net):
                self.assertTrue(t["piezas"], f"{forma}: tablero vacio")


class UnaProtoPorSalida(unittest.TestCase):
    def test_cada_salida_arma_su_propio_tablero(self):
        tabla = bcd_siete_segmentos()
        total = 0
        for nombre, valores in tabla.outputs.items():
            una = TruthTable(4, outputs={nombre: valores})
            net = netlist.construir(soluciones(una, "sop"), "sop", extremos="led")
            self.assertEqual(netlist.comprobar(net, una), [], nombre)
            total += len(net["pastillas"])
        junto = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="led")
        # por separado sale mas material: no se comparten compuertas
        self.assertGreater(total, len(junto["pastillas"]))


class LaListaDeCables(unittest.TestCase):
    def test_hay_un_cable_por_cada_union(self):
        tabla = bcd_siete_segmentos()
        net = netlist.construir(soluciones(tabla, "sop"), "sop", extremos="7seg_cc")
        cables = netlist.lista_de_cables(net)
        self.assertGreater(len(cables), 20)
        for c in cables:
            self.assertIn("-", c["de"])
            self.assertIn("-", c["a"])
            self.assertNotEqual(c["de"], c["a"])


if __name__ == "__main__":
    unittest.main()
