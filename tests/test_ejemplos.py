"""Los ejemplos de Archivo > Ejemplos: cada tabla es lo que dice su titulo.

Se revisan contra los datos de los enunciados (los PDF de las practicas) y
contra la definicion del circuito, no contra la misma funcion que los arma.
"""

import unittest

from ktool import ejemplos
from ktool.core.simplify import solve_output
from ktool.hw.modelo import validar_nombres


def columna(proyecto, salida):
    return proyecto["values"][proyecto["output_names"].index(salida)]


class Ejemplos(unittest.TestCase):

    def test_todos_tienen_nombres_que_compilan_y_tablas_completas(self):
        for _grupo, lista in ejemplos.CATALOGO:
            for titulo, hacer in lista:
                p = hacer()
                if p.get("doc_type") == "fsm":      # los contadores: test_fsm.py
                    continue
                validar_nombres(p["input_names"], p["output_names"])
                filas = 1 << len(p["input_names"])
                for col in p["values"]:
                    self.assertEqual(len(col), filas, titulo)
                    self.assertTrue(set(col) <= {0, 1, "x"}, titulo)

    def test_bcd_a_7_segmentos_es_la_tabla_de_la_practica(self):
        p = ejemplos.bcd_a_7_segmentos()
        # tabla de Convertidores de codigo, catodo comun, a..g
        tabla = ["1111110", "0110000", "1101101", "1111001", "0110011",
                 "1011011", "1011111", "1110000", "1111111", "1111011"]
        for n, patron in enumerate(tabla):
            obtenido = "".join(str(columna(p, s)[n]) for s in "abcdefg")
            self.assertEqual(obtenido, patron, n)
        for n in range(10, 16):
            self.assertEqual({columna(p, s)[n] for s in "abcdefg"}, {"x"})

    def test_alarma_de_coche_da_la_ecuacion_de_la_guia(self):
        # Guia MAX II: AL = PI' + PD' + SW C'  (1 en todo salvo 1100, 1101, 1111)
        p = ejemplos.alarma_de_coche()
        ceros = [i for i, v in enumerate(columna(p, "AL")) if v == 0]
        self.assertEqual(ceros, [0b1100, 0b1101, 0b1111])

    def test_impares_menores_que_11(self):
        p = ejemplos.impares_menores_que_11()
        self.assertEqual([i for i, v in enumerate(columna(p, "F")) if v == 1], [1, 3, 5, 7, 9])

    def test_primos_de_5_bits(self):
        p = ejemplos.primos_5_bits()
        self.assertEqual([i for i, v in enumerate(columna(p, "L")) if v == 1],
                         [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31])

    def test_copiadora_y_sus_no_importa(self):
        p = ejemplos.copiadora()
        self.assertEqual([i for i, v in enumerate(columna(p, "Y")) if v == "x"], [9, 11, 13, 15])

    def test_sumador_y_restador(self):
        p = ejemplos.sumador_2_bits()
        for a in range(4):
            for b in range(4):
                fila = a * 4 + b
                total = sum(columna(p, s)[fila] << k for k, s in enumerate(["S0", "S1", "CS"]))
                self.assertEqual(total, a + b)
        r = ejemplos.restador_completo()
        for fila in range(8):
            a, b, bi = fila >> 2, (fila >> 1) & 1, fila & 1
            d, bo = columna(r, "D")[fila], columna(r, "BOUT")[fila]
            self.assertEqual(a - b - bi, d - 2 * bo)

    def test_gray_ida_y_vuelta(self):
        ida, vuelta = ejemplos.binario_a_gray(), ejemplos.gray_a_binario()
        for n in range(16):
            g = sum(columna(ida, f"G{k}")[n] << k for k in range(4))
            self.assertEqual(sum(columna(vuelta, f"B{k}")[g] << k for k in range(4)), n)

    def test_el_multiplexor_se_simplifica_a_sus_cuatro_terminos(self):
        p = ejemplos.multiplexor_4_a_1()
        sol = solve_output(columna(p, "Y"), p["input_names"])
        self.assertEqual(len(sol["sop"].patterns), 4)
        self.assertIn("S1' S0' D0", sol["sop"].equation)


if __name__ == "__main__":
    unittest.main()
