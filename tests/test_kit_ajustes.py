"""El kit con placas elegidas, ajustes por placa, pines por senal y archivos
editados a mano; y el ensamblador del PIC 18F.

El ensamblado real con pic-as y la compilacion con XC8 se corrieron a mano
(docs/HARDWARE.md): aqui se revisa que cada ajuste llegue al texto generado.
"""

import unittest

from ktool.core.table import TruthTable
from ktool.hw import ajustes, asm, kit
from ktool.hw.modelo import Circuito, asignar_pines
from ktool.hw import placas


def tabla_and_or():
    t = TruthTable(2, ["A", "B"])
    t.set_output("Y", [0, 0, 0, 1])     # A B
    t.set_output("Z", [0, 1, 1, 1])     # A + B
    return t


class Ajustes(unittest.TestCase):

    def test_omision_y_valores_viejos(self):
        v = ajustes.con_omision("pic18f45k50", {"oscilador": "33 MHz", "frecuencia_hz": "2,5"})
        self.assertEqual(v["oscilador"], "16 MHz")      # ya no existe: el de omision
        self.assertEqual(v["frecuencia_hz"], 2.5)        # coma decimal aceptada
        self.assertEqual(ajustes.con_omision("pico"), {})

    def test_numero_que_no_sirve(self):
        with self.assertRaises(ValueError):
            ajustes.con_omision("max2", {"reloj_hz": "cincuenta"})
        with self.assertRaises(ValueError):
            ajustes.con_omision("max2", {"frecuencia_hz": 0})

    def test_hz_ida_y_vuelta(self):
        for texto in ajustes.OSCILADOR_45K50 + ajustes.OSCILADOR_4550:
            self.assertEqual(ajustes.hz_texto(ajustes.hz(texto)), texto)


class KitElegido(unittest.TestCase):

    def test_solo_las_placas_elegidas(self):
        k = kit.armar(tabla_and_or(), elegidas=["pic18f45k50", "max2", "uno_nano"])
        rutas = set(k.archivos)
        self.assertIn("pic/pic18f45k50.c", rutas)
        self.assertIn("pic/pic18f45k50.S", rutas)          # C y ensamblador por omision
        self.assertIn("fpga/circuito.qsf", rutas)
        self.assertIn("fpga/circuito.vhd", rutas)          # la MAX II trae su VHDL
        self.assertIn("arduino/uno_nano/uno_nano.ino", rutas)
        self.assertNotIn("pic/pic16f84a.c", rutas)
        self.assertNotIn("fpga/circuito.v", rutas)         # el Verilog es de "hdl"

    def test_sin_eleccion_sale_todo_como_antes(self):
        k = kit.armar(tabla_and_or())
        self.assertIn("pic/pic16f84a.c", k.archivos)
        self.assertIn("fpga/circuito.v", k.archivos)
        self.assertNotIn("arduino/mega2560/mega2560.ino", k.archivos)   # cabe en el Uno

    def test_pines_por_senal_y_el_resto_automatico(self):
        k = kit.armar(tabla_and_or(), elegidas=["max2"], pines={"max2": {"A": 26, "Z": 81}})
        qsf = k.archivos["fpga/circuito.qsf"]
        self.assertIn("set_location_assignment PIN_26 -to A", qsf)
        self.assertIn("set_location_assignment PIN_81 -to Z", qsf)
        self.assertIn("-to B", qsf)                        # B tomo una pata libre
        self.assertIn("-to Y", qsf)

    def test_un_editado_sustituye_al_generado(self):
        k = kit.armar(tabla_and_or(), elegidas=["python"],
                      editados={"python/simular.py": "# mio\n", "no/existe.c": "x"})
        self.assertEqual(k.archivos["python/simular.py"], "# mio\n")
        self.assertEqual(k.editados, {"python/simular.py"})
        self.assertNotIn("no/existe.c", k.archivos)


class AjustesEnElCodigo(unittest.TestCase):

    def test_pic_entradas_y_salidas_activas_en_bajo(self):
        k = kit.armar(tabla_and_or(), elegidas=["pic18f45k50"], ajustes_por_placa={
            "pic18f45k50": {"entradas": "activas en bajo (boton a GND)",
                            "salidas": "activas en bajo", "oscilador": "8 MHz",
                            "mclr": "entrada RE3", "lenguaje": "C (XC8)"}})
        c = k.archivos["pic/pic18f45k50.c"]
        self.assertNotIn("pic/pic18f45k50.S", k.archivos)
        self.assertIn("if (!PORTBbits.RB0)", c)
        self.assertIn("^ 1u", c)
        self.assertIn("OSCCON = 0x60;", c)                 # IRCF = 110: 8 MHz
        self.assertIn("#define _XTAL_FREQ 8000000UL", c)
        self.assertIn("MCLRE = OFF", c)
        self.assertIn("INTCON2bits.nRBPU = 0;", c)

    def test_arduino_input_pullup(self):
        k = kit.armar(tabla_and_or(), elegidas=["uno_nano"], ajustes_por_placa={
            "uno_nano": {"entradas": "INPUT_PULLUP (boton a GND)", "salidas": "activas en bajo"}})
        ino = k.archivos["arduino/uno_nano/uno_nano.ino"]
        self.assertIn("INPUT_PULLUP", ino)
        self.assertIn("== LOW;", ino)
        self.assertIn("? LOW : HIGH", ino)

    def test_max2_envoltura_solo_si_hay_que_invertir(self):
        sin = kit.armar(tabla_and_or(), elegidas=["max2"])
        self.assertNotIn("fpga/circuito_max2.vhd", sin.archivos)
        self.assertIn("TOP_LEVEL_ENTITY circuito\n", sin.archivos["fpga/circuito.qsf"])
        con = kit.armar(tabla_and_or(), elegidas=["max2"], ajustes_por_placa={
            "max2": {"salidas": "activas en bajo"}})
        self.assertIn("Y <= not c_Y;", con.archivos["fpga/circuito_max2.vhd"])
        self.assertIn("TOP_LEVEL_ENTITY circuito_max2", con.archivos["fpga/circuito.qsf"])


class Ensamblador(unittest.TestCase):

    def setUp(self):
        self.c = Circuito(tabla_and_or())
        self.r = asignar_pines(self.c, placas.PIC["pic18f45k50"])

    def test_cada_termino_es_una_comparacion_de_mascara(self):
        s = asm.pic18_combinacional(self.c, "pic18f45k50", self.r)
        self.assertIn("PROCESSOR 18F45K50", s)
        self.assertIn("andlw   0x03", s)        # Y = AB mira los dos bits
        self.assertIn("xorlw   0x03", s)
        self.assertIn("btfsc   STATUS, 2, a", s)
        self.assertIn("END     resetVec", s)

    def test_la_configuracion_va_antes_del_include(self):
        s = asm.pic18_combinacional(self.c, "pic18f4550", asignar_pines(
            self.c, placas.PIC["pic18f4550"]))
        self.assertLess(s.index("CONFIG  BOR = ON"), s.index("#include <xc.inc>"))
        self.assertIn("CONFIG  CP0 = OFF", s)

    def test_nand_y_xor_se_escriben_como_sop(self):
        c = Circuito(tabla_and_or(), forma="xor")
        s = asm.pic18_combinacional(c, "pic18f45k50", self.r)
        self.assertIn("(SOP)", s)
        self.assertNotIn("(XOR)", s)


if __name__ == "__main__":
    unittest.main()
