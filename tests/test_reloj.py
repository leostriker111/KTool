"""Frecuencias y retardos (ktool/hw/reloj.py).

Como en test_hw, aqui no se corren compiladores (GHDL, XC8, pic-as y
arduino-cli se probaron a mano). Lo que se revisa es la aritmetica: las
cuentas de la practica de Multivibradores, los valores de registro, el texto
generado y, para la subrutina de lazos en ensamblador, un simulador minimo
de PIC18 que ejecuta el texto generado y cuenta los ciclos uno por uno.
"""

import random
import re
import unittest
import xml.etree.ElementTree as ET

from ktool.hw import reloj


# ------------------------------------------------------------ simulador PIC18

def ciclos_simulados(texto, etiqueta):
    """Ejecuta la subrutina generada y devuelve los ciclos de `call etiqueta`.

    Solo entiende lo que genera asm_pic18_retardo con metodo "subrutina":
    movlw, movwf, decfsz, bra, nop y return. Tiempos de un PIC18: decfsz 1
    ciclo (2 si salta sobre una instruccion de una palabra), bra/call/return 2.
    """
    instrucciones = []
    etiquetas = {}
    for linea in texto.splitlines():
        linea = linea.split(";")[0].rstrip()
        if not linea.strip() or linea.split()[0].upper() == "PSECT":
            continue
        if not linea.startswith(" "):
            nombre, _, resto = linea.partition(":")
            if resto.strip().startswith("DS"):
                continue               # variable en udata_acs
            etiquetas[nombre.strip()] = len(instrucciones)
            continue
        partes = linea.split(None, 1)
        argumentos = [a.strip() for a in partes[1].split(",")] if len(partes) > 1 else []
        instrucciones.append((partes[0].lower(), argumentos))

    ram = {}
    w = 0
    pc = etiquetas[etiqueta]
    ciclos = 2                          # el call
    while True:
        operacion, argumentos = instrucciones[pc]
        if operacion == "movlw":
            w = int(argumentos[0]) & 0xFF
            ciclos += 1
            pc += 1
        elif operacion == "movwf":
            ram[argumentos[0]] = w
            ciclos += 1
            pc += 1
        elif operacion == "decfsz":
            valor = (ram[argumentos[0]] - 1) & 0xFF
            ram[argumentos[0]] = valor
            if valor == 0:
                ciclos += 2
                pc += 2
            else:
                ciclos += 1
                pc += 1
        elif operacion == "bra":
            ciclos += 2
            pc = etiquetas[argumentos[0]]
        elif operacion == "nop":
            ciclos += 1
            pc += 1
        elif operacion == "return":
            return ciclos + 2
        else:
            raise AssertionError(f"instruccion inesperada: {operacion}")


def es_ascii(texto):
    return all(ord(c) < 128 for c in texto)


# ------------------------------------------------------------------ formato

class TestFormato(unittest.TestCase):
    def test_prefijos(self):
        self.assertEqual(reloj.formato(0.0005, "s"), "500 us")
        self.assertEqual(reloj.formato(0.5, "s"), "500 ms")
        self.assertEqual(reloj.formato(1.5, "s"), "1.5 s")
        self.assertEqual(reloj.formato(50e6, "Hz"), "50 MHz")
        self.assertEqual(reloj.formato(4700, "Ohm"), "4.7 kOhm")
        self.assertEqual(reloj.formato(100e-9, "F"), "100 nF")
        self.assertEqual(reloj.formato(0, "s"), "0 s")

    def test_redondeo_cambia_de_prefijo(self):
        self.assertEqual(reloj.formato(0.9999999, "s"), "1 s")

    def test_miles(self):
        self.assertEqual(reloj.formato(25000000, ""), "25 000 000")
        self.assertEqual(reloj.formato(25000000, "ciclos"), "25 000 000 ciclos")
        self.assertEqual(reloj.formato(999, ""), "999")
        self.assertEqual(reloj.formato(8333333.3333, ""), "8 333 333.333")

    def test_porcentaje_sin_exponente(self):
        self.assertEqual(reloj.formato(4e-6, "%"), "0.000004 %")
        self.assertEqual(reloj.formato(-0.0002, "%"), "-0.0002 %")
        self.assertEqual(reloj.formato(50, "%"), "50 %")


# ------------------------------------------------------------------ divisor

class TestCalcular(unittest.TestCase):
    def test_practica_multivibradores(self):
        """Los casos de la practica con el oscilador de 50 MHz de la MAX II."""
        casos = [  # (f_salida, cuenta de T/2, bits)
            (1, 25000000, 25), (0.5, 50000000, 26), (2, 12500000, 24), (3, 8333333, 23)]
        for f, cuenta, bits in casos:
            c = reloj.calcular(50e6, f)
            self.assertEqual(c.cuenta_medio_periodo, cuenta, f)
            self.assertEqual(c.bits_contador, bits, f)
            self.assertEqual(c.cuenta_alto, c.cuenta_bajo)
            self.assertAlmostEqual(c.ciclo_pct, 50)
        tres_segundos = reloj.calcular(50e6, periodo=3)
        self.assertEqual(tres_segundos.cuenta_medio_periodo, 75000000)
        self.assertAlmostEqual(tres_segundos.periodo, 3)
        self.assertAlmostEqual(tres_segundos.t_alto, 1.5)

    def test_error_por_redondeo(self):
        c = reloj.calcular(50e6, 3)
        self.assertAlmostEqual(c.f_real, 50e6 / (2 * 8333333))
        self.assertAlmostEqual(c.error_pct, (c.f_real - 3) / 3 * 100)
        self.assertGreater(c.error_pct, 0)
        self.assertEqual(reloj.calcular(50e6, 1).error_pct, 0)

    def test_ciclo_distinto_de_50(self):
        c = reloj.calcular(50e6, 1, ciclo=25)
        self.assertEqual(c.cuenta_alto, 12500000)
        self.assertEqual(c.cuenta_bajo, 37500000)
        self.assertEqual(c.cuenta_periodo, 50000000)
        self.assertEqual(c.bits_contador, 26)
        self.assertAlmostEqual(c.t_alto, 0.25)
        self.assertAlmostEqual(c.ciclo_pct, 25)

    def test_limites(self):
        self.assertEqual(reloj.calcular(1000, 500).cuenta_medio_periodo, 1)
        with self.assertRaises(ValueError):
            reloj.calcular(1000, 501)
        with self.assertRaises(ValueError):
            reloj.calcular(1000)
        with self.assertRaises(ValueError):
            reloj.calcular(1000, 1, periodo=1)
        with self.assertRaises(ValueError):
            reloj.calcular(1000, 0)
        with self.assertRaises(ValueError):
            reloj.calcular(1000, 1, ciclo=100)
        with self.assertRaises(ValueError):
            reloj.calcular(10, 2.5, ciclo=10)   # 4 ciclos por periodo: minimo 25 %

    def test_renglones(self):
        filas = reloj.calcular(50e6, 1).renglones()
        for fila in filas:
            self.assertEqual(len(fila), 3)
            self.assertTrue(all(isinstance(x, str) and es_ascii(x) for x in fila))
            self.assertNotIn(" ", fila[2])      # el valor para copiar va limpio
        por_etiqueta = {f[0]: f for f in filas}
        self.assertEqual(por_etiqueta["Medio periodo (T/2)"][1:], ("500 ms", "0.5"))
        self.assertEqual(por_etiqueta["Cuenta del divisor"][1:], ("25 000 000 ciclos", "25000000"))
        self.assertEqual(por_etiqueta["Bits del contador"][2], "25")
        asimetrico = {f[0] for f in reloj.calcular(50e6, 1, ciclo=25).renglones()}
        self.assertIn("Tiempo en alto", asimetrico)
        self.assertIn("Cuenta en bajo", asimetrico)
        self.assertNotIn("Medio periodo (T/2)", asimetrico)


# ------------------------------------------------------------------ 555

class Test555(unittest.TestCase):
    def test_formulas(self):
        d = reloj.astable_555(1000, 10000, 100e-6)
        self.assertAlmostEqual(d["t_alto"], 0.693 * 11000 * 100e-6)
        self.assertAlmostEqual(d["t_bajo"], 0.693 * 10000 * 100e-6)
        self.assertAlmostEqual(d["f"], 1 / (0.693 * 21000 * 100e-6))
        self.assertAlmostEqual(d["ciclo"], 11000 / 21000 * 100)

    def test_propuesta(self):
        e24 = {round(m * 10 ** k, 6) for k in range(3, 7) for m in reloj.SERIE_E24}
        for f, ciclo in ((1, None), (0.5, None), (1000, 60), (10, 75), (2, None)):
            d = reloj.astable_555_para(f, ciclo)
            self.assertIn(round(d["r1"], 6), e24)
            self.assertIn(round(d["r2"], 6), e24)
            self.assertLess(abs(d["error_pct"]), 3, (f, ciclo, d))
            self.assertGreater(d["ciclo"], 50)
            self.assertAlmostEqual(reloj.astable_555(d["r1"], d["r2"], d["c"])["f"], d["f"])
            if ciclo is not None:
                self.assertLess(abs(d["ciclo"] - ciclo), 3)

    def test_capacitor_fijo(self):
        d = reloj.astable_555_para(1, c=10e-6)
        self.assertEqual(d["c"], 10e-6)

    def test_ciclo_imposible(self):
        with self.assertRaises(ValueError):
            reloj.astable_555_para(1, ciclo=50)
        with self.assertRaises(ValueError):
            reloj.astable_555_para(1, ciclo=40)


# ------------------------------------------------------------------ PIC

class TestPic(unittest.TestCase):
    def test_osccon(self):
        self.assertEqual(reloj.osccon_pic18f45k50(16000000)[0], 0x72)
        self.assertEqual(reloj.osccon_pic18f45k50(8000000)[0], 0x62)
        self.assertEqual(reloj.osccon_pic18f45k50(1000000)[0], 0x32)
        self.assertEqual(reloj.osccon_pic18f45k50(31000)[0], 0x02)
        self.assertEqual(reloj.osccon_pic18f45k50(31250)[0], 0x02)
        valor, comentario = reloj.osccon_pic18f45k50(16e6)
        self.assertIn("IRCF = 111", comentario)
        self.assertTrue(es_ascii(comentario))
        with self.assertRaises(ValueError):
            reloj.osccon_pic18f45k50(48000000)

    def test_c_delay(self):
        t = reloj.c_pic18_retardo(16e6, 1)
        self.assertIn("#define _XTAL_FREQ 16000000UL", t["definiciones"])
        self.assertIn("__delay_ms(500);", t["esperar_medio_periodo"])
        self.assertEqual(t["error_pct"], 0)
        t = reloj.c_pic18_retardo(16e6, 3)
        self.assertIn("__delay_ms(166);", t["esperar_medio_periodo"])
        self.assertIn("__delay_us(667);", t["esperar_medio_periodo"])
        self.assertLess(abs(t["error_pct"]), 0.001)

    def test_c_delay_largo_se_parte(self):
        # 50 s de medio periodo a 16 MHz son 200 millones de ciclos: XC8 acepta 50 463 240
        t = reloj.c_pic18_retardo(16e6, 0.01)
        self.assertIn("__delay_ms(1000);", t["esperar_medio_periodo"])
        self.assertIn("50u", t["esperar_medio_periodo"])
        self.assertNotIn("__delay_ms(50000)", t["esperar_medio_periodo"])

    def test_c_timer0(self):
        t = reloj.c_pic18_retardo(16e6, 1, "timer0")
        self.assertIn("T0CON = 0x84;", t["configurar"])          # 1:32
        self.assertIn("#define PRECARGA_TMR0 3036u", t["definiciones"])
        self.assertIn("#define VUELTAS_TMR0 1u", t["definiciones"])
        self.assertIn("INTCONbits.TMR0IF", t["esperar_medio_periodo"])
        self.assertEqual(t["error_pct"], 0)
        largo = reloj.c_pic18_retardo(16e6, 0.01, "timer0")      # 50 s: varias vueltas
        self.assertNotIn("VUELTAS_TMR0 1u", largo["definiciones"])
        self.assertLess(abs(largo["error_pct"]), 0.01)
        with self.assertRaises(ValueError):
            reloj.c_pic18_retardo(16e6, 1, "otro")

    def test_plan_timer0(self):
        for ciclos in (100, 1000, 65536, 2000000, 666666.7, 16777216, 1e9):
            prescala, cuentas, vueltas = reloj._plan_timer0(ciclos)
            self.assertIn(prescala, reloj.PRESCALAS_TMR0)
            self.assertTrue(1 <= cuentas <= 65536)
            self.assertLess(abs(prescala * cuentas * vueltas - ciclos) / ciclos, 0.001)

    def test_formula_de_lazos_contra_simulador(self):
        """La formula del comentario coincide con los ciclos que da el simulador."""
        casos = [(16e6, 100e-6), (16e6, 10e-3), (31000, 0.5), (16e6, 50e-3),
                 (4e6, 2379e-6), (4e6, 0.2), (16e6, 3e-6)]
        for fosc, segundos in casos:
            texto = reloj.asm_pic18_retardo(fosc, segundos, etiqueta="espera")
            esperado = int(round(segundos * fosc / 4))
            self.assertEqual(ciclos_simulados(texto, "espera"), esperado, (fosc, segundos))
            self.assertIn("Total = bloques", texto)
            self.assertIn(reloj.formato(esperado), texto)
            self.assertTrue(es_ascii(texto))

    def test_bloques_en_serie(self):
        texto = reloj.asm_pic18_retardo(4e6, 2379e-6, etiqueta="espera")
        self.assertIn("espera_l1b:", texto)
        self.assertEqual(ciclos_simulados(texto, "espera"), 2379)

    def test_plan_exacto_en_todo_el_rango(self):
        azar = random.Random(7)
        objetivos = [9, 10, 11, 12, 766, 767, 771, 196101, 50000000, 120000000]
        objetivos += [azar.randint(9, 60000000) for _ in range(12)]
        for ciclos in objetivos:
            bloques, nops = reloj._plan_lazos(ciclos)
            self.assertEqual(reloj.ciclos_lazos_pic18(bloques, nops), ciclos)
            self.assertLessEqual(nops, 3)
            for cuentas in bloques:
                self.assertTrue(all(1 <= v <= 255 for v in cuentas))

    def test_asm_limites(self):
        with self.assertRaises(ValueError):
            reloj.asm_pic18_retardo(16e6, 1e-6)         # 4 ciclos: ni la subrutina vacia
        with self.assertRaises(ValueError):
            reloj.asm_pic18_retardo(16e6, 1, etiqueta="mal nombre")
        with self.assertRaises(ValueError):
            reloj.asm_pic18_retardo(16e6, 1, metodo="otro")

    def test_asm_timer0(self):
        texto = reloj.asm_pic18_retardo(16e6, 0.5, "timer0")
        self.assertIn("movlw   0x84", texto)
        self.assertIn("high(3036)", texto)
        self.assertIn("low(3036)", texto)
        self.assertIn("INTCON_TMR0IF_POSN", texto)
        self.assertIn("PSECT udata_acs", texto)
        self.assertTrue(es_ascii(texto))


# ------------------------------------------------------------------ Arduino

class TestArduino(unittest.TestCase):
    def test_delay(self):
        t = reloj.arduino_retardo(1)
        self.assertIn("delay(500);", t["en_loop"])
        self.assertNotIn("delayMicroseconds", t["en_loop"])
        t = reloj.arduino_retardo(3, accion="digitalWrite(13, HIGH);")
        self.assertIn("delay(166);", t["en_loop"])
        self.assertIn("delayMicroseconds(667);", t["en_loop"])
        self.assertIn("  digitalWrite(13, HIGH);", t["en_loop"])

    def test_millis(self):
        t = reloj.arduino_retardo(1, "millis")
        self.assertIn("500UL", t["variables"])
        self.assertIn("millis()", t["en_loop"])
        t = reloj.arduino_retardo(3, "millis")
        self.assertIn("166667UL", t["variables"])
        self.assertIn("micros()", t["en_loop"])
        self.assertIn("ultimo_us = micros();", t["setup"])

    def test_limites(self):
        with self.assertRaises(ValueError):
            reloj.arduino_retardo(100000)
        with self.assertRaises(ValueError):
            reloj.arduino_retardo(1, "otro")


# ------------------------------------------------------------------ VHDL

class TestVhdl(unittest.TestCase):
    def test_divisor(self):
        texto = reloj.vhdl_divisor(50e6, 1)
        self.assertIn("entity divisor is", texto)
        self.assertIn("constant N : integer := 25000000;", texto)
        self.assertIn("signal cuenta : integer range 0 to N - 1;", texto)
        self.assertIn("rising_edge(clk_in)", texto)
        self.assertIn("if rst = '1' then", texto)
        self.assertIn("25 000 000 ciclos", texto)
        self.assertTrue(es_ascii(texto))

    def test_divisor_redondeado(self):
        texto = reloj.vhdl_divisor(50e6, 3, nombre="div3")
        self.assertIn("entity div3 is", texto)
        self.assertIn("redondeado a 8 333 333", texto)
        self.assertIn("error", texto)

    def test_divisor_errores(self):
        with self.assertRaises(ValueError):
            reloj.vhdl_divisor(50e6, 1, nombre="process")
        with self.assertRaises(ValueError):
            reloj.vhdl_divisor(50e6, 1, nombre="2mal")
        with self.assertRaises(ValueError):
            reloj.vhdl_divisor(1e10, 1)           # N = 5e9: no cabe en integer
        with self.assertRaises(ValueError):
            reloj.vhdl_divisor(50e6, 30e6)

    def test_divisores(self):
        texto = reloj.vhdl_divisores(50e6, {"hz1": 1, "hz2": 2, "s3": 1 / 3})
        for puerto, n in (("hz1", 25000000), ("hz2", 12500000), ("s3", 75000000)):
            self.assertIn(f"{puerto} : out std_logic", texto)
            self.assertIn(f"constant n_{puerto} : integer := {n};", texto)
            self.assertIn(f"end process dividir_{puerto};", texto)
        self.assertIn("0.333333", texto)
        self.assertTrue(es_ascii(texto))

    def test_divisores_choques(self):
        with self.assertRaises(ValueError):
            reloj.vhdl_divisores(50e6, {"a1": 1, "A1": 2})
        with self.assertRaises(ValueError):
            reloj.vhdl_divisores(50e6, {"x": 1, "cuenta_x": 2})
        with self.assertRaises(ValueError):
            reloj.vhdl_divisores(50e6, {"clk_in": 1})
        with self.assertRaises(ValueError):
            reloj.vhdl_divisores(50e6, {})


# ------------------------------------------------------------------ SVG

class TestSvg(unittest.TestCase):
    def test_onda(self):
        svg = reloj.onda_svg(reloj.calcular(50e6, 1))
        raiz = ET.fromstring(svg)
        self.assertTrue(raiz.tag.endswith("svg"))
        self.assertEqual(raiz.get("width"), "520")
        self.assertIn("T = 1 s", svg)
        self.assertIn("t alto = 500 ms", svg)
        self.assertIn("t bajo = 500 ms", svg)
        self.assertTrue(es_ascii(svg))
        # solo negro y grises: cada color #rgb o #rrggbb con los tres canales iguales
        for color in re.findall(r"#([0-9a-fA-F]{3,6})\b", svg):
            if len(color) == 3:
                self.assertTrue(color[0] == color[1] == color[2], color)
            else:
                self.assertTrue(color[0:2] == color[2:4] == color[4:6], color)

    def test_onda_del_555(self):
        svg = reloj.onda_svg(reloj.astable_555(1000, 10000, 10e-6), ancho=400, alto=100)
        ET.fromstring(svg)
        self.assertIn('width="400"', svg)


class TestCodigoAscii(unittest.TestCase):
    def test_fuente_ascii(self):
        with open(reloj.__file__, encoding="utf-8") as f:
            self.assertTrue(es_ascii(f.read()))


if __name__ == "__main__":
    unittest.main()
