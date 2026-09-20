"""Realizaciones NAND-only y NOR-only: misma funcion, otra compuerta."""

import itertools
import random
import unittest
import xml.etree.ElementTree as ET

from ktool.core.ast import evaluate
from ktool.core.simplify import Solution, complemento, solve_output
from ktool.render import codegen
from ktool.render.circuit import circuit_svg

VARIABLES = ["A", "B", "C", "D", "E", "F"]


def da_la_misma_funcion(prueba, valores, n):
    """Las cuatro realizaciones evaluadas fila por fila contra la tabla."""
    variables = VARIABLES[:n]
    r = solve_output(valores, variables)
    for forma in ("sop", "pos", "nand", "nor"):
        arbol = codegen.solution_to_ast(r[forma])
        for i, v in enumerate(valores):
            if v == "x":
                continue
            entorno = {x: (i >> (n - 1 - k)) & 1 for k, x in enumerate(variables)}
            prueba.assertEqual(
                evaluate(arbol, entorno), v,
                f"{forma} falla en la fila {i} de {valores}: {r[forma].equation}",
            )


class MismaFuncion(unittest.TestCase):
    def test_todas_las_tablas_de_dos_y_tres_variables(self):
        for n in (2, 3):
            for valores in itertools.product([0, 1, "x"], repeat=1 << n):
                da_la_misma_funcion(self, list(valores), n)

    def test_tablas_al_azar_hasta_seis(self):
        random.seed(31)
        for n in (4, 5, 6):
            for _ in range(60):
                da_la_misma_funcion(
                    self, [random.choice([0, 1, "x"]) for _ in range(1 << n)], n)


class ComoSeEscribe(unittest.TestCase):
    def test_complemento_de_un_literal(self):
        self.assertEqual(complemento("A"), "A'")
        self.assertEqual(complemento("A'"), "A")

    def test_nand_de_dos_terminos(self):
        r = solve_output([0, 0, 0, 1, 0, 1, 0, 1], VARIABLES[:3])
        self.assertEqual(r["sop"].equation, "BC + AC")
        self.assertEqual(r["nand"].equation, "((BC)'(AC)')'")

    def test_nor_de_dos_terminos(self):
        r = solve_output([0, 0, 0, 1, 0, 1, 0, 1], VARIABLES[:3])
        self.assertEqual(r["pos"].equation, "(C)(A + B)")
        self.assertEqual(r["nor"].equation, "(C' + (A + B)')'")

    def test_literal_suelto_se_invierte(self):
        # Y = AB + C : la C suelta necesita inversion antes del NAND final
        valores = [1 if ((a and b) or c) else 0
                   for a in (0, 1) for b in (0, 1) for c in (0, 1)]
        r = solve_output(valores, VARIABLES[:3])
        self.assertIn("C'", r["nand"].equation)


class TerminoUnico(unittest.TestCase):
    """El caso que mas se presta a equivocarse: las inversiones se cancelan."""

    def test_un_literal_no_necesita_compuertas(self):
        # Y = B
        r = solve_output([0, 1, 0, 1], VARIABLES[:2])
        self.assertEqual(r["nand"].equation, "B")
        self.assertEqual(r["nand"].cost()[0], 0)

    def test_un_producto_necesita_dos_compuertas(self):
        # Y = AB : una NAND y otra que deshace la inversion
        r = solve_output([0, 0, 0, 1], VARIABLES[:2])
        self.assertEqual(r["nand"].equation, "((AB)')'")
        self.assertEqual(r["nand"].cost()[0], 2)

    def test_el_dibujo_coincide_con_la_ecuacion(self):
        """Regresion: el diagrama dibujaba una inversion de mas o de menos y la
        salida quedaba complementada."""
        casos = [
            ([0, 1, 0, 1], 0),      # Y = B, ninguna compuerta
            ([0, 0, 0, 1], 2),      # Y = AB, compuerta + inversor
        ]
        for valores, bolitas in casos:
            svg = circuit_svg(solve_output(valores, VARIABLES[:2])["nand"], "Y")
            self.assertEqual(svg.count('fill="white"'), bolitas, f"con {valores}")


class Dibujo(unittest.TestCase):
    def test_el_svg_es_xml_valido(self):
        random.seed(32)
        for n in (2, 3, 4, 5):
            for _ in range(20):
                valores = [random.choice([0, 1, "x"]) for _ in range(1 << n)]
                r = solve_output(valores, VARIABLES[:n])
                for forma in ("sop", "pos", "nand", "nor"):
                    svg = circuit_svg(r[forma], "Y")
                    ET.fromstring(svg)
                    self.assertNotIn("nan", svg.lower())

    def test_las_universales_llevan_bolita(self):
        r = solve_output([0, 0, 0, 1, 0, 1, 0, 1], VARIABLES[:3])
        self.assertEqual(circuit_svg(r["sop"], "Y").count('fill="white"'), 0)
        self.assertGreater(circuit_svg(r["nand"], "Y").count('fill="white"'), 0)
        self.assertGreater(circuit_svg(r["nor"], "Y").count('fill="white"'), 0)


class Lenguajes(unittest.TestCase):
    def test_los_siete_lenguajes_aceptan_nand_y_nor(self):
        r = solve_output([0, 0, 0, 1, 0, 1, 0, 1], VARIABLES[:3])
        for forma in ("nand", "nor"):
            for lang in codegen.LANG_ORDER:
                linea = codegen.render(r[forma], "Y", lang)
                self.assertTrue(linea.strip(), f"{forma} en {lang} salio vacio")

    def test_verilog_del_nand(self):
        r = solve_output([0, 0, 0, 1, 0, 1, 0, 1], VARIABLES[:3])
        self.assertEqual(codegen.render(r["nand"], "Y", "Verilog"),
                         "assign Y = ~(~(B & C) & ~(A & C));")


class ElReporteMuestraLaEcuacion(unittest.TestCase):
    """Regresion: `--form nand` dibujaba el circuito NAND pero nunca imprimia
    su ecuacion, asi que el diagrama no se podia leer."""

    def _ecuaciones(self, forma):
        import re

        from ktool.core.table import TruthTable
        from ktool.render.report import Options, build_report
        tabla = TruthTable(3, outputs={"Y": [0, 0, 0, 1, 0, 1, 0, 1]})
        html = build_report(tabla, Options(form=forma))
        return set(re.findall(r"<b>(SOP|POS|NAND|NOR):</b>", html))

    def test_form_nand_imprime_la_ecuacion_nand(self):
        self.assertIn("NAND", self._ecuaciones("nand"))

    def test_form_nor_imprime_la_ecuacion_nor(self):
        self.assertIn("NOR", self._ecuaciones("nor"))

    def test_el_reporte_normal_no_se_llena_de_formas(self):
        salen = self._ecuaciones("auto")
        self.assertNotIn("NAND", salen)
        self.assertNotIn("NOR", salen)
        self.assertEqual(salen, {"SOP", "POS"})


class Constantes(unittest.TestCase):
    def test_funcion_constante(self):
        for valores, esperado in (([0] * 8, "0"), ([1] * 8, "1")):
            r = solve_output(valores, VARIABLES[:3])
            self.assertEqual(r["nand"].equation, esperado)
            self.assertEqual(r["nor"].equation, esperado)

    def test_formas_declaradas(self):
        for forma in ("sop", "pos", "xor", "nand", "nor"):
            self.assertIn(forma, Solution.FORMAS)


if __name__ == "__main__":
    unittest.main()
