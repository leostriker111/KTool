"""Entradas invalidas: mensaje claro y salida distinta de cero, nunca un traceback."""

import contextlib
import io
import unittest

from ktool import cli
from ktool.core import table
from ktool.core.parser import parse
from ktool.core.table import TruthTable


def correr(*argv):
    """Corre la CLI y devuelve (codigo, texto). codigo 0 = salio bien."""
    salida = io.StringIO()
    try:
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
            cli.main(list(argv))
        return 0, salida.getvalue()
    except SystemExit as e:
        return (e.code if isinstance(e.code, int) else 1), f"{salida.getvalue()}{e}"


class NumeroDeVariables(unittest.TestCase):
    """MIN_VARS/MAX_VARS existian pero solo la GUI los respetaba."""

    def test_demasiadas(self):
        codigo, texto = correr("-n", "9", "-m", "1", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("entre 2 y 6", texto)

    def test_muy_pocas(self):
        codigo, texto = correr("-n", "1", "-m", "1", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("entre 2 y 6", texto)

    def test_vector_de_siete_variables(self):
        codigo, texto = correr("-n", "7", "--truth", "01" * 64, "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("entre 2 y 6", texto)

    def test_expresion_de_siete_variables(self):
        codigo, texto = correr("-e", "A*B*C*D*E*F*G", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("maximo son 6", texto)

    def test_validar_nvars_acepta_el_rango(self):
        for n in range(table.MIN_VARS, table.MAX_VARS + 1):
            self.assertEqual(table.validar_nvars(n), n)

    def test_validar_nvars_rechaza_lo_que_no_es_entero(self):
        with self.assertRaises(ValueError):
            table.validar_nvars("3")


class IndicesFueraDeRango(unittest.TestCase):
    def test_mintermino_muy_grande(self):
        codigo, texto = correr("-n", "3", "-m", "9", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("no existe con 3 variables", texto)

    def test_mintermino_negativo(self):
        """El peor de todos: -1 se envolvia al 7 y daba otra tabla en silencio."""
        codigo, texto = correr("-n", "3", "-m", "-1", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertNotIn("ABC", texto)

    def test_dont_care_fuera_de_rango(self):
        codigo, texto = correr("-n", "3", "-m", "1", "-d", "20", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("don't care 20", texto)

    def test_indice_en_minterminos_y_en_dont_cares(self):
        codigo, texto = correr("-n", "3", "-m", "1", "-d", "1", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("a la vez", texto)

    def test_desde_el_nucleo_tambien(self):
        with self.assertRaises(ValueError):
            TruthTable.from_minterms(3, [9])
        with self.assertRaises(ValueError):
            TruthTable.from_minterms(3, [-1])


class ExpresionesRotas(unittest.TestCase):
    def test_operador_sin_operando(self):
        codigo, texto = correr("-e", "A+", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("mal formada", texto)

    def test_parentesis_sin_cerrar(self):
        codigo, texto = correr("-e", "(A+B", "--text")
        self.assertNotEqual(codigo, 0)

    def test_solo_espacios(self):
        with self.assertRaises(ValueError):
            parse("   ", letras_sueltas=True)

    def test_caracter_invalido(self):
        codigo, texto = correr("-e", "A $ B", "--text")
        self.assertNotEqual(codigo, 0)

    def test_traducir_expresion_rota(self):
        codigo, texto = correr("-e", "A+", "--to", "verilog")
        self.assertNotEqual(codigo, 0)
        self.assertIn("mal formada", texto)


class FaltanArgumentos(unittest.TestCase):
    def test_sin_nada(self):
        codigo, texto = correr("--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("nada que resolver", texto)

    def test_minterminos_sin_n(self):
        codigo, texto = correr("-m", "1,2", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("-n/--vars", texto)

    def test_dont_cares_sin_minterminos(self):
        codigo, texto = correr("-n", "3", "-d", "1", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("-m/--minterms", texto)

    def test_vector_vacio(self):
        codigo, texto = correr("--truth", "", "--text")
        self.assertNotEqual(codigo, 0)

    def test_vector_que_no_es_potencia_de_dos(self):
        codigo, texto = correr("--truth", "0110 1", "--text")
        self.assertNotEqual(codigo, 0)
        self.assertIn("potencia de 2", texto)


class LoQueSiDebeFuncionar(unittest.TestCase):
    """Validar no puede romper lo que ya servia."""

    def test_el_ejemplo_del_leeme(self):
        codigo, texto = correr("-n", "3", "-m", "1,4,5,6", "-d", "2,7", "--text")
        self.assertEqual(codigo, 0)
        self.assertIn("B'C + A", texto)

    def test_expresion_de_una_sola_letra(self):
        codigo, texto = correr("-e", "A", "--text")
        self.assertEqual(codigo, 0)

    def test_bases_mezcladas(self):
        codigo, _ = correr("-n", "4", "-m", "0x1,0b11,5", "--text")
        self.assertEqual(codigo, 0)

    def test_seis_variables(self):
        codigo, _ = correr("-n", "6", "-m", "0,1,2,63", "--text")
        self.assertEqual(codigo, 0)

    def test_vector_con_dont_cares(self):
        codigo, _ = correr("-n", "3", "--truth", "01x011x1", "--text")
        self.assertEqual(codigo, 0)


if __name__ == "__main__":
    unittest.main()
