"""Lectura de expresiones: yuxtaposicion, precedencia y los dos modos del lexer."""

import unittest

from ktool.core.ast import build_output, collect_vars, evaluate
from ktool.core.lexer import tokenize
from ktool.core.parser import parse
from ktool.render import codegen


def variables_de(texto, letras_sueltas=True):
    usadas = set()
    collect_vars(parse(texto, letras_sueltas=letras_sueltas), usadas)
    return sorted(usadas)


def tabla(texto, nvars=None):
    """(variables, vector de salida) como los arma la CLI con -e."""
    return build_output(texto, nvars)


class YuxtaposicionEsAnd(unittest.TestCase):
    """El bug de #1: 'AB' se leia como UNA variable llamada AB."""

    def test_dos_letras_pegadas_son_dos_variables(self):
        self.assertEqual(variables_de("AB"), ["A", "B"])

    def test_minterminos_escritos_a_mano(self):
        variables, _ = tabla("A'BC'D + AB'CD' + A'B'C'D + ABCD'")
        self.assertEqual(variables, ["A", "B", "C", "D"])

    def test_todas_las_formas_de_and_son_iguales(self):
        esperado = tabla("A*B")
        for texto in ("AB", "A.B", "A&B", "A * B", "A  B"):
            self.assertEqual(tabla(texto), esperado, f"fallo con {texto!r}")

    def test_yuxtaposicion_con_parentesis(self):
        _, vals = tabla("A(B+C)")
        # A=1 y (B o C): minterminos 5, 6, 7 de tres variables
        self.assertEqual(vals, [0, 0, 0, 0, 0, 1, 1, 1])

    def test_producto_de_sumas(self):
        _, vals = tabla("(A+B)(C+D)")
        esperado = [1 if ((a or b) and (c or d)) else 0
                    for a in (0, 1) for b in (0, 1) for c in (0, 1) for d in (0, 1)]
        self.assertEqual(vals, esperado)

    def test_tres_letras_pegadas(self):
        variables, vals = tabla("ABC")
        self.assertEqual(variables, ["A", "B", "C"])
        self.assertEqual(vals, [0, 0, 0, 0, 0, 0, 0, 1])

    def test_pegadas_con_prima_en_medio(self):
        # este caso si funcionaba antes (la prima cortaba la corrida): que siga
        variables, vals = tabla("A'B")
        self.assertEqual(variables, ["A", "B"])
        self.assertEqual(vals, [0, 1, 0, 0])


class Precedencia(unittest.TestCase):
    """NOT > AND > XOR > OR, como dice el LEEME."""

    def test_and_liga_mas_que_or(self):
        self.assertEqual(tabla("AB + C"), tabla("(A*B) + C"))

    def test_and_liga_mas_que_xor(self):
        self.assertEqual(tabla("AB ^ C"), tabla("(A*B) ^ C"))

    def test_xor_liga_mas_que_or(self):
        self.assertEqual(tabla("A ^ B + C"), tabla("(A ^ B) + C"))

    def test_prima_aplica_al_parentesis(self):
        _, vals = tabla("(AB)'")
        self.assertEqual(vals, [1, 1, 1, 0])

    def test_prima_aplica_a_una_letra(self):
        _, vals = tabla("AB'")
        self.assertEqual(vals, [0, 0, 1, 0])

    def test_not_prefijo_y_postfijo_coinciden(self):
        self.assertEqual(tabla("!A B"), tabla("A'B"))
        self.assertEqual(tabla("~A B"), tabla("A'B"))


class ModoIdentificadoresLargos(unittest.TestCase):
    """Traducir una expresion libre (--to) NO debe partir los nombres."""

    def test_nombres_largos_siguen_enteros(self):
        self.assertEqual(variables_de("clk & enable", letras_sueltas=False),
                         ["clk", "enable"])

    def test_el_modo_por_omision_es_el_largo(self):
        self.assertEqual([t.val for t in tokenize("clk") if t.kind == "VAR"], ["clk"])

    def test_traducir_a_verilog_conserva_los_nombres(self):
        self.assertEqual(codegen.translate("clk & enable", "q", "Verilog"),
                         "assign q = clk & enable;")

    def test_traducir_yuxtaposicion_en_modo_largo(self):
        # 'AB' en modo largo es una sola senal llamada AB, y eso esta bien aqui
        self.assertEqual(variables_de("AB", letras_sueltas=False), ["AB"])


class RellenoDeVariables(unittest.TestCase):
    """-n mas grande que las variables de la expresion rellena con las que faltan."""

    def test_rellena_hasta_n(self):
        variables, vals = tabla("AB", nvars=4)
        self.assertEqual(variables, ["A", "B", "C", "D"])
        self.assertEqual(len(vals), 16)

    def test_el_relleno_no_cambia_la_funcion(self):
        _, vals = tabla("AB", nvars=4)
        # A y B son los dos bits mas significativos: vale 1 en la mitad alta
        self.assertEqual(vals, [0] * 12 + [1] * 4)


class Evaluacion(unittest.TestCase):
    def test_evaluate_respeta_el_arbol(self):
        ast = parse("AB + C", letras_sueltas=True)
        self.assertEqual(evaluate(ast, {"A": 1, "B": 1, "C": 0}), 1)
        self.assertEqual(evaluate(ast, {"A": 1, "B": 0, "C": 0}), 0)
        self.assertEqual(evaluate(ast, {"A": 0, "B": 0, "C": 1}), 1)


if __name__ == "__main__":
    unittest.main()
