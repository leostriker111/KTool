"""Maquinas de estado: contadores, flip-flops y VHDL por los tres metodos.

Sin GHDL (eso se corrio a mano: docs/HARDWARE.md). Aqui se revisa la logica:
que los contadores sigan la secuencia del enunciado, que las ecuaciones de
cada flip-flop, aplicadas con su ecuacion caracteristica, den el estado
siguiente correcto, y que el VHDL traiga lo que debe.
"""

import unittest

from ktool import ejemplos
from ktool.core.ast import evaluate
from ktool.core.simplify import solve_output
from ktool.fsm import Machine, contadores as c, flipflops
from ktool.hw import vhdl_fsm
from ktool.render.codegen import solution_to_ast
from ktool.render.fsm_report import build_fsm_report


def numeros(maquina, estados):
    m = Machine.from_dict(maquina)
    return [int(m._by_name[n].code, 2) for n in estados]


def todos_los_contadores():
    return [hacer() for _g, lista in ejemplos.CATALOGO for _t, hacer in lista
            if hacer().get("doc_type") == "fsm"]


class Contadores(unittest.TestCase):

    def test_mod13_descendente(self):
        d = c.contador("m13", {"": c.descendente(13)})
        self.assertEqual(numeros(d, c.simular(d, [""] * 14)),
                         [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 12, 11])

    def test_secuencia_propia_con_paro(self):
        d = c.contador("m8", {"0": [4, 7, 2, 6, 0, 3, 5, 1], "1": "paro"}, ["X"])
        self.assertEqual(numeros(d, c.simular(d, ["0", "0", "1", "1", "0"])),
                         [4, 7, 2, 2, 2, 6])

    def test_reinicio_set_y_entrar_a_otra_secuencia(self):
        d = c.contador("m16", {"00": c.ascendente(16), "01": "paro", "10": "set",
                               "11": [15, 12, 9, 6, 3, 0]}, ["X", "Y"])
        # va en 0,1,2; cambia a multiplos de 3: 2 no esta, entra por el 15
        self.assertEqual(numeros(d, c.simular(d, ["00", "00", "11", "11", "10", "00"])),
                         [0, 1, 2, 15, 12, 15, 0])
        r = c.contador("r", {"0": [3, 4, 5], "1": "reinicio"}, ["R"])
        self.assertEqual(numeros(r, c.simular(r, ["0", "0", "1"])), [3, 4, 5, 3])

    def test_leer_modo(self):
        self.assertEqual(c.leer_modo("0-3"), [0, 1, 2, 3])
        self.assertEqual(c.leer_modo("3-0"), [3, 2, 1, 0])
        self.assertEqual(c.leer_modo("4, 7,2"), [4, 7, 2])
        self.assertEqual(c.leer_modo(" Paro "), "paro")
        self.assertEqual(c.leer_modo("sigue", [1, 2]), [1, 2])
        for malo in ("", "hola", "sigue"):
            with self.assertRaises(ValueError):
                c.leer_modo(malo)

    def test_errores_que_se_explican(self):
        with self.assertRaises(ValueError):          # falta la combinacion 1
            c.contador("x", {"0": [0, 1]}, ["X"])
        with self.assertRaises(ValueError):          # numero repetido
            c.contador("x", {"": [0, 1, 0]})
        with self.assertRaises(ValueError):          # no cabe en 2 bits
            c.contador("x", {"": [0, 5]}, bits=2)


class FlipFlops(unittest.TestCase):
    """Las ecuaciones de excitacion, aplicadas con la ecuacion caracteristica
    del flip-flop, tienen que dar el estado siguiente de cada transicion."""

    def test_cada_flip_flop_lleva_al_estado_correcto(self):
        siguiente = {
            "D": lambda q, e: e["D"],
            "T": lambda q, e: q ^ e["T"],
            "JK": lambda q, e: (e["J"] & (1 - q)) | ((1 - e["K"]) & q),
            "SR": lambda q, e: e["S"] | ((1 - e["R"]) & q),
        }
        for fuente in todos_los_contadores():
            m = Machine.from_dict(fuente)
            variables = m.io_variables()
            for ff in flipflops.KINDS:
                arboles = {nombre: solution_to_ast(solve_output(col, variables)["best"])
                           for nombre, col in m.excitation_columns(ff).items()}
                for st in m.states:
                    for combo in m.input_combos():
                        destino = m._by_name[m.next_state(st.name, combo).dst]
                        entorno = dict(zip(variables, (int(b) for b in st.code + combo)))
                        for k, q in enumerate(m.state_bits):
                            suf = m._suffix(k)
                            e = {ltr: evaluate(arboles[f"{ltr}{suf}"], entorno)
                                 for ltr in flipflops.inputs(ff)}
                            self.assertEqual(siguiente[ff](int(st.code[k]), e),
                                             int(destino.code[k]),
                                             f"{fuente['name']} {ff} {st.label}/{combo} bit {q}")


class VHDL(unittest.TestCase):

    def setUp(self):
        self.d = c.contador("m8", {"0": [4, 7, 2, 6, 0, 3, 5, 1], "1": "paro"}, ["X"])

    def test_los_tres_metodos_comparten_entidad(self):
        for texto in (vhdl_fsm.por_ecuaciones(self.d, "JK"), vhdl_fsm.por_tabla(self.d),
                      vhdl_fsm.por_estados(self.d)):
            self.assertIn("entity maquina is", texto)
            self.assertIn("rising_edge(clk)", texto)
            self.assertIn("if rst = '1' then", texto)

    def test_el_reset_lleva_al_estado_inicial(self):
        self.assertIn('estado <= "100";', vhdl_fsm.por_tabla(self.d))      # el 4
        self.assertIn("actual <= S4;", vhdl_fsm.por_estados(self.d))

    def test_la_tabla_trae_cada_transicion(self):
        tabla = vhdl_fsm.por_tabla(self.d)
        self.assertIn('when "1000" => siguiente <= "111";', tabla)    # 4, X=0 -> 7
        self.assertIn('when "1001" => siguiente <= "100";', tabla)    # 4, X=1 -> 4

    def test_el_banco_de_prueba_espera_la_simulacion(self):
        tb = vhdl_fsm.banco_de_prueba(self.d, ["0", "0", "1"])
        self.assertIn('revisar("100", 0);', tb)
        self.assertIn('revisar("111", 1);', tb)
        self.assertIn('revisar("010", 2);', tb)
        self.assertIn('revisar("010", 3);', tb)

    def test_el_reporte_trae_los_tres_metodos(self):
        html = build_fsm_report(Machine.from_dict(self.d), "T", fuente=self.d)
        self.assertIn("VHDL por los tres metodos", html)
        self.assertIn("Metodo 3: diagrama de estados", html)


if __name__ == "__main__":
    unittest.main()
