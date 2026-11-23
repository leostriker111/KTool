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

    def test_una_entrada_A0_no_choca_con_el_nucleo_de_arduino(self):
        # el nucleo de Arduino ya define PIN_A0..PIN_A7: el sketch nombra cada
        # pin pin_<senal>, en minusculas, para que una entrada A0 compile
        from ktool.core.table import TruthTable
        from ktool.hw import kit
        p = ejemplos.decodificador_2_a_4()
        tabla = TruthTable(p["nvars"], p["input_names"])
        for nombre, col in zip(p["output_names"], p["values"]):
            tabla.set_output(nombre, col)
        ino = kit.armar(tabla, elegidas=["uno_nano"]).archivos["arduino/uno_nano/uno_nano.ino"]
        self.assertNotIn("PIN_", ino)
        self.assertIn("pin_A0", ino)

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

    def test_compuertas_basicas_son_las_tablas_de_la_practica(self):
        # tablas de Compuertas logicas, filas A B = 00, 01, 10, 11
        p = ejemplos.compuertas_basicas()
        esperado = {"Y_NAND": [1, 1, 1, 0], "Y_NOR": [1, 0, 0, 0], "Y_NOT": [1, 1, 0, 0],
                    "Y_AND": [0, 0, 0, 1], "Y_OR": [0, 1, 1, 1], "Y_XOR": [0, 1, 1, 0]}
        for salida, columna_esperada in esperado.items():
            self.assertEqual(columna(p, salida), columna_esperada, salida)

    def test_alarma_del_refrigerador_es_la_tabla_2_3(self):
        p = ejemplos.alarma_refrigerador()
        self.assertEqual(columna(p, "F"), [0, 0, 1, 1, 0, 0, 0, 1])

    def test_sumador_y_restador_de_3_bits(self):
        s = ejemplos.sumador_3_bits()
        r = ejemplos.restador_3_bits_comparador()
        for a in range(8):
            for b in range(8):
                fila = a * 8 + b
                total = sum(columna(s, n)[fila] << k
                            for k, n in enumerate(["S0", "S1", "S2", "CS"]))
                self.assertEqual(total, a + b)
                d = sum(columna(r, n)[fila] << k for k, n in enumerate(["D0", "D1", "D2"]))
                ps = columna(r, "PS")[fila]
                self.assertEqual(d - 8 * ps, a - b)    # PS D2 D1 D0 en complemento a 2
                comparador = [columna(r, n)[fila] for n in ("MENOR", "IGUAL", "MAYOR")]
                self.assertEqual(comparador, [int(a < b), int(a == b), int(a > b)])

    def test_restador_decodificado_muestra_la_magnitud_y_el_signo(self):
        p = ejemplos.restador_3_bits_7_segmentos()
        siete = ["1111110", "0110000", "1101101", "1111001", "0110011",
                 "1011011", "1011111", "1110000"]
        for a in range(8):
            for b in range(8):
                fila = a * 8 + b
                patron = "".join(str(columna(p, s)[fila]) for s in "abcdefg")
                self.assertEqual(patron, siete[abs(a - b)], (a, b))
                self.assertEqual(columna(p, "SIGNO")[fila], int(a < b))

    def test_binario_a_octal(self):
        p = ejemplos.binario_a_octal_7_segmentos()
        self.assertEqual("".join(str(columna(p, s)[5]) for s in "abcdefg"), "1011011")
        self.assertEqual("".join(str(columna(p, s)[7]) for s in "abcdefg"), "1110000")

    def test_alu_de_2_bits(self):
        p = ejemplos.alu_2_bits()
        for operacion in range(4):
            for a in range(4):
                for b in range(4):
                    fila = operacion * 16 + a * 4 + b
                    arit = [columna(p, s)[fila] for s in ("ZA", "ZB", "ZC")]
                    logi = columna(p, "ZD")[fila] * 2 + columna(p, "ZE")[fila]
                    if operacion == 0:
                        self.assertEqual(arit[0] * 4 + arit[1] * 2 + arit[2], a + b)
                    elif operacion == 1:
                        self.assertEqual(arit[1] * 2 + arit[2] - 4 * arit[0], a - b)
                    elif operacion == 2:
                        self.assertEqual(arit, [int(a < b), int(a == b), int(a > b)])
                    else:
                        self.assertEqual(arit, [0, 0, 0])
                    self.assertEqual(logi, [a & b, a | b, a ^ b, 3 - a][operacion])

    def test_xor_de_tres_entradas(self):
        p = ejemplos.xor_de_tres_entradas()
        self.assertEqual(columna(p, "F"), [0, 1, 1, 0, 1, 0, 0, 1])

    def test_nombre_en_16_segmentos_tiene_seis_letras(self):
        p = ejemplos.nombre_16_segmentos()
        self.assertEqual(p["nvars"], 3)
        self.assertEqual(len(p["output_names"]), 16)
        # las filas 6 y 7 no tienen letra: no importan
        for col in p["values"]:
            self.assertEqual(col[6:], ["x", "x"])

    def test_el_multiplexor_se_simplifica_a_sus_cuatro_terminos(self):
        p = ejemplos.multiplexor_4_a_1()
        sol = solve_output(columna(p, "Y"), p["input_names"])
        self.assertEqual(len(sol["sop"].patterns), 4)
        self.assertIn("S1' S0' D0", sol["sop"].equation)


if __name__ == "__main__":
    unittest.main()
