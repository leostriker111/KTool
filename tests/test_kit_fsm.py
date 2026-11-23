"""El kit de maquinas de estado (hw/kit_fsm.py) y el ensamblador de la maquina
(asm.pic18_maquina).

La compilacion real (XC8, pic-as, arduino-cli) y la simulacion con GHDL se
corren afuera; aqui se revisa que la tabla escrita en cada archivo sea la de
Machine.next_state, que los pines y ajustes lleguen al texto y que lo que no
aplica salga bloqueado con su motivo.
"""

import json
import os
import re
import unittest

from ktool import ejemplos
from ktool.fsm import Machine
from ktool.fsm.contadores import simular
from ktool.hw import kit_fsm
from ktool.hw.configuracion import ConfigKit
from ktool.hw.vhdl_fsm import estimulo_completo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def maquinas():
    """Los 8 contadores de ejemplos.py y las dos maquinas de ejemplos/."""
    lista = [(t, f()) for t, f in dict(ejemplos.CATALOGO)["Contadores (maquinas de estado)"]]
    for nombre in ("contador_decimal", "letrero_tool"):
        with open(os.path.join(RAIZ, "ejemplos", nombre, "maquina.json"), encoding="utf-8") as f:
            lista.append((nombre, json.load(f)))
    return lista


def config(elegidas, ajustes=None, pines=None, editados=None):
    c = ConfigKit()
    c.elegidas = list(elegidas)
    c.ajustes = ajustes or {}
    c.pines = pines or {}
    c.editados = editados or {}
    return c


def con_paro():
    return ejemplos.mod8_secuencia_con_paro()


def numeros_de_arreglo(texto, nombre):
    """Los numeros de `nombre[...] = { ... };` de un .c o .ino (sin comentarios)."""
    cuerpo = texto[texto.index(nombre + "["):]
    cuerpo = cuerpo[cuerpo.index("{") + 1:cuerpo.index("};")]
    cuerpo = re.sub(r"//[^\n]*", "", cuerpo)
    return [int(n, 16) for n in re.findall(r"0x[0-9A-Fa-f]+", cuerpo)]


def numeros_de_db(texto, etiqueta):
    """Los bytes de los `db` que siguen a `etiqueta:` en un .S."""
    renglones = texto[texto.index("\n" + etiqueta + ":") + 1:].splitlines()[1:]
    numeros = []
    for r in renglones:
        if not r.strip().startswith("db"):
            break
        numeros += [int(n, 16) for n in re.findall(r"0x[0-9A-Fa-f]+", r.split(";")[0])]
    return numeros


def esperado(fuente):
    """El siguiente estado de cada (codigo, entradas), directo de Machine.next_state."""
    m = Machine.from_dict(fuente)
    por_nombre = {st.name: st for st in m.states}
    tabla = kit_fsm.TablaMaquina(fuente)
    res = {}
    for st in m.states:
        for combo in m.input_combos():
            t = m.next_state(st.name, combo)
            fila = (int(st.code, 2) << len(m.inputs)) | (int(combo, 2) if combo else 0)
            res[fila] = int(por_nombre[t.dst].code, 2) if t else tabla.inicial
    return res


class Senales(unittest.TestCase):

    def test_entradas_bits_y_salidas(self):
        s = kit_fsm.senales(ejemplos.mod16_con_x_y())
        self.assertEqual(s, [("X", "entrada"), ("Y", "entrada"), ("Q3", "salida"),
                             ("Q2", "salida"), ("Q1", "salida"), ("Q0", "salida")])

    def test_la_max2_agrega_reloj_y_reset(self):
        s = kit_fsm.senales(con_paro(), "max2")
        self.assertEqual(s[:2], [("clk", "reloj"), ("rst", "reset")])
        self.assertNotIn(("clk", "reloj"), kit_fsm.senales(con_paro(), "pic18f45k50"))

    def test_salidas_moore(self):
        fuente = maquinas()[-1][1]           # letrero: a..g despues de los bits
        nombres = [n for n, _d in kit_fsm.senales(fuente)]
        self.assertEqual(nombres, ["Q2", "Q1", "Q0", "a", "b", "c", "d", "e", "f", "g"])


class TablaEmitida(unittest.TestCase):
    """La tabla de cada archivo coincide con Machine.next_state, renglon por renglon."""

    def test_c_asm_arduino_y_python(self):
        for titulo, fuente in maquinas():
            with self.subTest(maquina=titulo):
                k = kit_fsm.armar(fuente, config(["pic18f45k50", "uno_nano", "python"]))
                quiere = esperado(fuente)
                for ruta, leer in (("pic/pic18f45k50.c", lambda t: numeros_de_arreglo(t, "SIGUIENTE")),
                                   ("pic/pic18f45k50.S", lambda t: numeros_de_db(t, "tabla_siguiente")),
                                   ("arduino/uno_nano/uno_nano.ino",
                                    lambda t: numeros_de_arreglo(t, "SIGUIENTE"))):
                    tabla = leer(k.archivos[ruta])
                    for fila, destino in quiere.items():
                        self.assertEqual(tabla[fila], destino, f"{ruta} renglon {fila}")
                espacio = {"__name__": "simular_prueba"}
                exec(k.archivos["python/simular.py"], espacio)
                estimulo = estimulo_completo(fuente)
                self.assertEqual(espacio["simular"](estimulo), simular(fuente, estimulo))

    def test_salidas_moore_en_c_y_asm(self):
        fuente = maquinas()[-2][1]           # contador decimal con 7 segmentos
        k = kit_fsm.armar(fuente, config(["pic18f45k50"]))
        m = Machine.from_dict(fuente)
        c = numeros_de_arreglo(k.archivos["pic/pic18f45k50.c"], "SALIDAS")
        s = numeros_de_db(k.archivos["pic/pic18f45k50.S"], "tabla_salidas")
        for st in m.states:
            self.assertEqual(c[int(st.code, 2)], int(st.out, 2))
            self.assertEqual(s[int(st.code, 2)], int(st.out, 2))


class Pines(unittest.TestCase):

    def test_pines_del_planificador_y_el_resto_automatico(self):
        k = kit_fsm.armar(con_paro(), config(["max2"], pines={
            "max2": {"clk": 14, "rst": 26, "Q0": 81}}))
        qsf = k.archivos["fpga/maquina_max2.qsf"]
        self.assertIn("set_location_assignment PIN_14 -to clk", qsf)
        self.assertIn("set_location_assignment PIN_26 -to rst", qsf)
        self.assertIn("set_location_assignment PIN_81 -to Q0", qsf)
        self.assertEqual(qsf.count("set_location_assignment PIN_26 "), 1)   # solo el reset
        self.assertIn("-to X", qsf)
        self.assertIn('IO_STANDARD "3.3-V LVTTL" -to clk', qsf)

    def test_omision_de_reloj_y_reset(self):
        qsf = kit_fsm.armar(con_paro(), config(["max2"])).archivos["fpga/maquina_max2.qsf"]
        self.assertIn("PIN_12 -to clk", qsf)
        self.assertIn("PIN_44 -to rst", qsf)
        self.assertIn('RESERVE_ALL_UNUSED_PINS "AS INPUT TRI-STATED"', qsf)

    def test_reloj_fuera_de_gclk_es_error(self):
        with self.assertRaises(ValueError):
            kit_fsm.armar(con_paro(), config(["max2"], pines={"max2": {"clk": 26}}))
        with self.assertRaises(ValueError):    # una senal en la pata del reset
            kit_fsm.armar(con_paro(), config(["max2"], pines={"max2": {"rst": 26, "X": 26}}))

    def test_pic_y_arduino(self):
        k = kit_fsm.armar(con_paro(), config(["pic18f45k50", "uno_nano"], pines={
            "pic18f45k50": {"X": "RB3", "Q2": "RC0"}, "uno_nano": ["4", "13", "12", "11"]}))
        c = k.archivos["pic/pic18f45k50.c"]
        self.assertIn("PORTBbits.RB3", c)
        self.assertIn("LATC = ", c)
        ino = k.archivos["arduino/uno_nano/uno_nano.ino"]
        self.assertIn("const uint8_t PIN_X = 4;", ino)     # lista vieja: orden de senales
        self.assertIn("const uint8_t PIN_Q0 = 11;", ino)


class Ajustes(unittest.TestCase):

    def test_pic_timer0_oscilador_e_inversiones(self):
        k = kit_fsm.armar(con_paro(), config(["pic18f45k50"], ajustes={"pic18f45k50": {
            "retardo": "Timer0", "oscilador": "8 MHz", "lenguaje": "C (XC8)",
            "entradas": "activas en bajo (boton a GND)", "salidas": "activas en bajo",
            "frecuencia_hz": 2, "mclr": "entrada RE3"}}))
        self.assertNotIn("pic/pic18f45k50.S", k.archivos)
        c = k.archivos["pic/pic18f45k50.c"]
        self.assertIn("T0CON = ", c)
        self.assertIn("OSCCON = 0x60;", c)
        self.assertIn("if (!PORTBbits.RB0)", c)
        self.assertIn("^ 1u", c)
        self.assertIn("INTCON2bits.nRBPU = 0;", c)
        self.assertIn("MCLRE = OFF", c)
        self.assertIn("T/2 = 250 ms", c)

    def test_asm_subrutina_o_timer0(self):
        sub = kit_fsm.armar(con_paro(), config(["pic18f4550"]))
        self.assertIn("medio_periodo_l1:", sub.archivos["pic/pic18f4550.S"])
        t0 = kit_fsm.armar(con_paro(), config(["pic18f4550"], ajustes={
            "pic18f4550": {"retardo": "Timer0", "lenguaje": "Ensamblador (pic-as)"}}))
        s = t0.archivos["pic/pic18f4550.S"]
        self.assertNotIn("pic/pic18f4550.c", t0.archivos)
        self.assertIn("movwf   T0CON, a", s)
        self.assertIn("tblrd*", s)
        self.assertLess(s.index("CONFIG  BOR = ON"), s.index("#include <xc.inc>"))

    def test_arduino_millis_serial_y_pullup(self):
        k = kit_fsm.armar(con_paro(), config(["uno_nano"], ajustes={"uno_nano": {
            "tiempo": "millis()", "serial": "si (9600 baudios)",
            "entradas": "INPUT_PULLUP (boton a GND)", "salidas": "activas en bajo"}}))
        ino = k.archivos["arduino/uno_nano/uno_nano.ino"]
        self.assertIn("millis() - ultimo_ms", ino)
        self.assertIn("Serial.begin(9600);", ino)
        self.assertIn("INPUT_PULLUP", ino)
        self.assertIn("? LOW : HIGH", ino)
        self.assertIn("PROGMEM", ino)

    def test_max2_metodo_reset_e_inversiones(self):
        k = kit_fsm.armar(con_paro(), config(["max2"], ajustes={"max2": {
            "metodo": "tabla de estados", "reset": "activo en alto",
            "entradas": "activas en bajo (botones de la tarjeta)", "salidas": "activas en bajo",
            "frecuencia_hz": 2}}))
        self.assertIn("architecture tabla of maquina", k.archivos["fpga/maquina.vhd"])
        top = k.archivos["fpga/maquina_max2.vhd"]
        self.assertIn("rst_interno <= rst;", top)
        self.assertIn("ent_X <= not X;", top)
        self.assertIn("Q0 <= not sal_Q0;", top)
        self.assertIn("constant N : integer := 12500000;", k.archivos["fpga/divisor.vhd"])
        self.assertIn("entity tb_maquina", k.archivos["fpga/tb_maquina.vhd"])

    def test_max2_boton_activo_en_bajo_y_sin_reset(self):
        bajo = kit_fsm.armar(con_paro(), config(["max2"]))
        self.assertIn("rst_interno <= not rst;", bajo.archivos["fpga/maquina_max2.vhd"])
        self.assertIn("architecture ecuaciones", bajo.archivos["fpga/maquina.vhd"])
        sin = kit_fsm.armar(con_paro(), config(["max2"], ajustes={"max2": {"reset": "sin reset"}}))
        self.assertIn("rst_interno <= '0';", sin.archivos["fpga/maquina_max2.vhd"])
        self.assertNotIn("-to rst", sin.archivos["fpga/maquina_max2.qsf"])


class EditadosYBloqueos(unittest.TestCase):

    def test_un_editado_sustituye_al_generado(self):
        k = kit_fsm.armar(con_paro(), config(["python"], editados={
            "python/simular.py": "# mio\n", "no/existe.c": "x"}))
        self.assertEqual(k.archivos["python/simular.py"], "# mio\n")
        self.assertEqual(k.editados, {"python/simular.py"})
        self.assertNotIn("no/existe.c", k.archivos)

    def test_plataformas_sin_maquinas_de_estado(self):
        k = kit_fsm.armar(con_paro(), config(["pic16f84a", "esp32_wroom32", "hdl", "python"]))
        estados = {p: (e, d) for p, e, d in k.resumen}
        for plataforma, (estado, detalle) in estados.items():
            if plataforma == "Simulacion en Python":
                self.assertEqual(estado, "listo")
            else:
                self.assertEqual(estado, "bloqueado")
                self.assertIn(kit_fsm.MOTIVO_NO_FSM, detalle)
        self.assertIn("LEEME.md", k.archivos)

    def test_frecuencia_imposible_bloquea_la_placa(self):
        k = kit_fsm.armar(con_paro(), config(["uno_nano", "pic18f45k50"], ajustes={
            "uno_nano": {"frecuencia_hz": 100000}, "pic18f45k50": {"oscilador": "31 kHz",
                                                                   "frecuencia_hz": 10000}}))
        self.assertTrue(all(e == "bloqueado" for _p, e, _d in k.resumen))
        self.assertEqual(k.pines, {})


class Documento(unittest.TestCase):

    def test_seccion_reloj_por_placa(self):
        c = config(["pic18f45k50", "max2", "uno_nano", "python"])
        extra = kit_fsm.seccion_reloj(con_paro(), c)
        self.assertEqual(set(extra), {"PIC18F45K50", "Intel/Altera MAX II EPM240T100C5",
                                      "Arduino Uno / Nano (ATmega328P)"})
        self.assertIn("<svg", extra["Intel/Altera MAX II EPM240T100C5"])
        self.assertIn("25 000 000", extra["Intel/Altera MAX II EPM240T100C5"])
        self.assertIn("Fosc/4", extra["PIC18F45K50"])


if __name__ == "__main__":
    unittest.main()
