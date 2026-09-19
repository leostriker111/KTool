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
from ktool.proto import chips, netlist, seleccion, tablero

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
