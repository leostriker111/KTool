"""Reparto de compuertas en encapsulados: los tres modos y sus bordes."""

import unittest

from ktool.core.simplify import solve_output
from ktool.core.table import TruthTable
from ktool.proto import chips, seleccion

VARIABLES = ["A", "B", "C", "D"]


def solucion(valores, forma, nvars=3):
    v = VARIABLES[:nvars]
    return [("Y", solve_output(valores, v)[forma])]


def bcd_siete_segmentos():
    """El caso de verdad: 4 entradas, 7 salidas, digitos 10-15 don't care."""
    digitos = {0: "abcdef", 1: "bc", 2: "abdeg", 3: "abcdg", 4: "bcfg",
               5: "acdfg", 6: "acdefg", 7: "abc", 8: "abcdefg", 9: "abcdfg"}
    salidas = {}
    for s in "abcdefg":
        salidas[s] = ["x" if i > 9 else (1 if s in digitos[i] else 0) for i in range(16)]
    return TruthTable(4, outputs=salidas)


class Cascada(unittest.TestCase):
    """Armar una compuerta ancha con encapsulados angostos."""

    def test_si_cabe_es_una_sola(self):
        self.assertEqual(seleccion._cascada(chips.AND, 2, 2), 1)
        self.assertEqual(seleccion._cascada(chips.AND, 3, 4), 1)

    def test_asociativas_encadenan(self):
        # una AND de 4 con AND de 2: tres compuertas
        self.assertEqual(seleccion._cascada(chips.AND, 4, 2), 3)
        # una OR de 5 con OR de 3: dos
        self.assertEqual(seleccion._cascada(chips.OR, 5, 3), 2)

    def test_nand_y_nor_no_son_asociativas(self):
        """NAND(a,b,c) con NAND de 2 son TRES: opera, deshace, y opera negando."""
        self.assertEqual(seleccion._cascada(chips.NAND, 3, 2), 3)
        self.assertEqual(seleccion._cascada(chips.NAND, 4, 2), 5)
        self.assertEqual(seleccion._cascada(chips.NOR, 3, 2), 3)
        # y siempre cuesta mas que la asociativa del mismo ancho
        for n in (3, 4, 5, 6):
            self.assertGreater(seleccion._cascada(chips.NAND, n, 2),
                               seleccion._cascada(chips.AND, n, 2))

    def test_un_inversor_no_ensancha_nada(self):
        self.assertIsNone(seleccion._cascada(chips.NOT, 3, 1))
        self.assertFalse(seleccion.puede_cascada(chips.NOT))


class QueCompuertasHacenFalta(unittest.TestCase):
    def test_sop_de_dos_terminos(self):
        # Y = AB + BC : dos AND de 2 y un OR de 2
        vals = [0, 0, 0, 1, 0, 0, 1, 1]
        nec, negados = seleccion.compuertas_necesarias(solucion(vals, "sop"))
        self.assertEqual(nec[(chips.AND, 2)], 2)
        self.assertEqual(nec[(chips.OR, 2)], 1)
        self.assertEqual(negados, set())

    def test_los_literales_negados_se_apuntan(self):
        nec, negados = seleccion.compuertas_necesarias(solucion([1, 0, 0, 0], "sop", 2))
        self.assertEqual(negados, {"A'", "B'"})

    def test_un_termino_compartido_se_cuenta_una_vez(self):
        """Dos salidas con el mismo producto son la MISMA compuerta fisica."""
        v = VARIABLES[:3]
        vals = [0, 0, 0, 1, 0, 0, 1, 1]
        una = solve_output(vals, v)["sop"]
        nec1, _ = seleccion.compuertas_necesarias([("Y0", una)])
        nec2, _ = seleccion.compuertas_necesarias([("Y0", una), ("Y1", una)])
        self.assertEqual(nec1[(chips.AND, 2)], nec2[(chips.AND, 2)])

    def test_una_constante_no_pide_compuertas(self):
        nec, _ = seleccion.compuertas_necesarias(solucion([1, 1, 1, 1], "sop", 2))
        self.assertEqual(sum(nec.values()), 0)

    def test_en_nand_el_literal_suelto_pide_inversor(self):
        # Y = AB + C : la C suelta se invierte antes del NAND final
        vals = [0, 1, 0, 1, 0, 1, 1, 1]
        nec, _ = seleccion.compuertas_necesarias(solucion(vals, "nand"))
        self.assertGreaterEqual(nec[(chips.NOT, 1)], 1)


class Modos(unittest.TestCase):
    def test_fiel_usa_el_ancho_exacto(self):
        # una AND de 3 pide el 7411, no dos 7408
        vals = [0] * 7 + [1]
        r = seleccion.repartir(solucion(vals, "sop"), seleccion.FIEL)
        self.assertIn("7411", r["chips"])
        self.assertTrue(r["completo"])

    def test_automatico_uniforma_al_ancho_mayor(self):
        tabla = bcd_siete_segmentos()
        sols = {n: solve_output(v, tabla.variables) for n, v in tabla.outputs.items()}
        lista = [(n, sols[n]["sop"]) for n in tabla.outputs]
        auto = seleccion.repartir(lista, seleccion.AUTOMATICO)
        # todas las AND caen en un solo encapsulado, el del ancho mayor
        ands = [c for c in auto["chips"] if chips.CHIPS[c]["tipo"] == chips.AND]
        self.assertEqual(len(ands), 1, f"esperaba un solo tipo de AND, hay {ands}")

    def test_forzado_respeta_la_lista(self):
        tabla = bcd_siete_segmentos()
        sols = {n: solve_output(v, tabla.variables) for n, v in tabla.outputs.items()}
        lista = [(n, sols[n]["sop"]) for n in tabla.outputs]
        permitidos = ["7408", "7432", "7404"]
        r = seleccion.repartir(lista, seleccion.FORZADO, permitidos)
        self.assertTrue(set(r["chips"]) <= set(permitidos), f"uso {set(r['chips'])}")
        self.assertTrue(r["completo"])

    def test_forzado_sin_lista_es_error(self):
        with self.assertRaises(ValueError):
            seleccion.repartir(solucion([0, 0, 0, 1], "sop", 2), seleccion.FORZADO)

    def test_forzado_con_un_chip_inventado_es_error(self):
        with self.assertRaises(ValueError):
            seleccion.repartir(solucion([0, 0, 0, 1], "sop", 2),
                               seleccion.FORZADO, ["74999"])

    def test_si_falta_el_tipo_lo_dice(self):
        """Sin ningun chip OR no se puede armar un SOP, y tiene que avisarse."""
        vals = [0, 1, 1, 1]
        r = seleccion.repartir(solucion(vals, "sop", 2), seleccion.FORZADO, ["7408"])
        self.assertFalse(r["completo"])
        self.assertTrue(r["sin_armar"])


class UnTotalIncompletoNoEsUnCosto(unittest.TestCase):
    """Un numero mas chico que no se puede construir es peor que ningun numero."""

    def test_el_incompleto_no_gana(self):
        vals = [0, 1, 1, 1]
        sols = solve_output(vals, VARIABLES[:2])
        repartos = {
            "sop": seleccion.repartir([("Y", sols["sop"])], seleccion.FORZADO, ["7408"]),
            "pos": seleccion.repartir([("Y", sols["pos"])], seleccion.FIEL),
        }
        self.assertFalse(repartos["sop"]["completo"])
        self.assertEqual(seleccion.mas_barata(repartos), "pos")

    def test_si_ninguna_se_puede_no_inventa_ganador(self):
        vals = [0, 1, 1, 1]
        sols = solve_output(vals, VARIABLES[:2])
        repartos = {"sop": seleccion.repartir([("Y", sols["sop"])],
                                              seleccion.FORZADO, ["7408"])}
        self.assertIsNone(seleccion.mas_barata(repartos))


class DecodificadorBCD(unittest.TestCase):
    """El caso real, en las cuatro realizaciones y los tres modos."""

    def setUp(self):
        self.tabla = bcd_siete_segmentos()
        sols = {n: solve_output(v, self.tabla.variables)
                for n, v in self.tabla.outputs.items()}
        self.por_forma = {f: [(n, sols[n][f]) for n in self.tabla.outputs]
                          for f in ("sop", "pos", "nand", "nor")}

    def test_con_el_catalogo_completo_todo_se_puede_armar(self):
        for modo in (seleccion.FIEL, seleccion.AUTOMATICO):
            for forma, lista in self.por_forma.items():
                r = seleccion.repartir(lista, modo)
                self.assertTrue(r["completo"],
                                f"{forma} en modo {modo} quedo incompleto: {r['sin_armar']}")
                self.assertGreater(r["total_chips"], 0)

    def test_con_un_cajon_basico_tambien(self):
        cajon = ["7400", "7402", "7404", "7408", "7432"]
        for forma, lista in self.por_forma.items():
            r = seleccion.repartir(lista, seleccion.FORZADO, cajon)
            self.assertTrue(r["completo"], f"{forma}: {r['sin_armar']}")

    def test_siempre_hacen_falta_inversores(self):
        """Los literales negados no existen en la protoboard: van con 7404."""
        r = seleccion.repartir(self.por_forma["sop"], seleccion.FIEL)
        self.assertIn("7404", r["chips"])
        self.assertTrue(r["negados"])

    def test_el_inventario_cuadra(self):
        for forma, lista in self.por_forma.items():
            r = seleccion.repartir(lista, seleccion.FIEL)
            for nombre, info in r["chips"].items():
                por_chip = len(chips.compuertas(nombre))
                self.assertEqual(info["compuertas_totales"], info["cuantos"] * por_chip)
                self.assertEqual(info["libres"],
                                 info["compuertas_totales"] - info["compuertas_usadas"])
                self.assertGreaterEqual(info["libres"], 0, f"{forma}/{nombre}")
                self.assertLess(info["libres"], por_chip,
                                f"{forma}/{nombre}: sobra un chip entero sin usar")


if __name__ == "__main__":
    unittest.main()
