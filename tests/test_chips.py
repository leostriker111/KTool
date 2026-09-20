"""El catalogo de chips y el molde del encapsulado.

Estas pruebas no comprueban que el pinout sea el correcto --eso se hizo contra
la hoja de datos-- sino que sea *coherente*: que no falte ni sobre un pin, que
ninguna compuerta se pise con otra, y que cada entrada diga de donde salio.
"""

import unittest
import xml.etree.ElementTree as ET

from ktool.proto import chips, dip


class Catalogo(unittest.TestCase):
    def test_todo_chip_dice_de_donde_salio(self):
        for nombre, c in chips.CHIPS.items():
            self.assertTrue(c.get("fuente", "").startswith("http"), f"{nombre} sin fuente")
            self.assertTrue(c.get("lectura"), f"{nombre} no dice como se leyo")

    def test_el_pinout_esta_completo(self):
        for nombre, c in chips.CHIPS.items():
            pines = c["pines"]
            self.assertEqual(sorted(c["pinout"]), list(range(1, pines + 1)), nombre)

    def test_la_alimentacion_sigue_la_convencion(self):
        for nombre, c in chips.CHIPS.items():
            vcc, gnd = chips.alimentacion(nombre)
            self.assertEqual(vcc, c["pines"], f"{nombre}: VCC deberia ir en el ultimo pin")
            self.assertEqual(gnd, c["pines"] // 2, f"{nombre}: GND deberia ir a la mitad")


class Compuertas(unittest.TestCase):
    """La estructura se deduce de los nombres: no hay copia que se desincronice."""

    def test_cada_compuerta_tiene_sus_entradas_y_una_salida(self):
        for nombre, c in chips.CHIPS.items():
            for g in chips.compuertas(nombre):
                self.assertEqual(len(g["entradas"]), c["entradas"],
                                 f"{nombre} compuerta {g['indice']}")
                self.assertIsNotNone(g["salida"], f"{nombre} compuerta {g['indice']} sin salida")

    def test_ningun_pin_se_usa_dos_veces(self):
        for nombre in chips.CHIPS:
            usados = []
            for g in chips.compuertas(nombre):
                usados.extend(g["entradas"])
                usados.append(g["salida"])
            self.assertEqual(len(usados), len(set(usados)), f"{nombre} repite pines")

    def test_no_sobra_ni_falta_un_pin(self):
        for nombre, c in chips.CHIPS.items():
            usados = set()
            for g in chips.compuertas(nombre):
                usados |= set(g["entradas"]) | {g["salida"]}
            libres = {p for p, s in c["pinout"].items() if s in ("VCC", "GND", "NC")}
            self.assertEqual(usados | libres, set(range(1, c["pines"] + 1)), nombre)

    def test_las_compuertas_no_se_pisan_con_la_alimentacion(self):
        for nombre in chips.CHIPS:
            vcc, gnd = chips.alimentacion(nombre)
            for g in chips.compuertas(nombre):
                self.assertNotIn(vcc, g["entradas"] + [g["salida"]], nombre)
                self.assertNotIn(gnd, g["entradas"] + [g["salida"]], nombre)

    def test_casos_conocidos(self):
        # el 7400 trae cuatro NAND de dos; el 7404, seis inversores
        self.assertEqual(len(chips.compuertas("7400")), 4)
        self.assertEqual(len(chips.compuertas("7404")), 6)
        self.assertEqual(len(chips.compuertas("7420")), 2)
        # primera compuerta del 7400: entradas 1 y 2, salida 3
        g = chips.compuertas("7400")[0]
        self.assertEqual((g["entradas"], g["salida"]), ([1, 2], 3))

    def test_busqueda_por_tipo(self):
        self.assertIn("7408", chips.por_tipo(chips.AND, entradas=2))
        self.assertIn("7411", chips.por_tipo(chips.AND, entradas=3))
        self.assertEqual(chips.anchos(chips.AND), [2, 3, 4])
        # la serie 74xx no trae OR de 4; que el catalogo no se lo invente
        self.assertNotIn(4, chips.anchos(chips.OR))


class MoldeDelEncapsulado(unittest.TestCase):
    """Un solo molde calculado, no un dibujo por chip."""

    def test_las_columnas_son_la_mitad_de_los_pines(self):
        for pines in (4, 6, 8, 14, 16, 20, 24, 28, 40):
            self.assertEqual(dip.geometria(pines)["columnas"], pines // 2)

    def test_el_largo_se_parece_al_real(self):
        # un DIP-14 mide 19.3 mm de largo segun la hoja de datos
        self.assertAlmostEqual(dip.geometria(14)["largo_mm"], 19.3, delta=0.5)

    def test_los_anchos_cambian_a_las_24_patas(self):
        self.assertEqual(dip.geometria(20)["entre_hileras_mm"], dip.ANGOSTO_MM)
        self.assertEqual(dip.geometria(24)["entre_hileras_mm"], dip.ANCHO_MM)

    def test_rechaza_lo_que_no_es_un_dip(self):
        for malo in (0, 2, 7, 15, -4):
            with self.assertRaises(ValueError, msg=f"acepto {malo} pines"):
                dip.geometria(malo)

    def test_la_numeracion_va_en_herradura(self):
        # pin 1 arriba a la izquierda, ultimo pin arriba a la derecha
        self.assertEqual(dip.lado(1, 14), "izq")
        self.assertEqual(dip.fila(1, 14), 0)
        self.assertEqual(dip.lado(14, 14), "der")
        self.assertEqual(dip.fila(14, 14), 0)
        self.assertEqual(dip.fila(7, 14), 6)
        self.assertEqual(dip.fila(8, 14), 6)

    def test_lado_y_fila_se_pueden_deshacer(self):
        for pines in (4, 8, 14, 16, 40):
            for pin in range(1, pines + 1):
                self.assertEqual(
                    dip.pin_en(dip.lado(pin, pines), dip.fila(pin, pines), pines), pin)

    def test_el_dibujo_es_xml_valido_para_cualquier_tamano(self):
        for pines in (4, 8, 14, 16, 20, 24, 40):
            svg = dip.svg(pines, etiquetas={1: "1A"}, nombre="prueba")
            ET.fromstring(f"<svg xmlns='http://www.w3.org/2000/svg'>{svg}</svg>")
            self.assertNotIn("nan", svg.lower())

    def test_todos_los_pines_se_dibujan(self):
        for pines in (8, 14, 40):
            svg = dip.svg(pines)
            self.assertEqual(svg.count('fill="#c9ccd1"'), pines)

    def test_el_relieve_se_puede_apagar(self):
        con = dip.svg(14, relieve=True)
        sin = dip.svg(14, relieve=False)
        self.assertGreater(len(con), len(sin))

    def test_el_catalogo_entero_se_dibuja(self):
        for nombre, c in chips.CHIPS.items():
            svg = dip.svg(c["pines"], etiquetas=c["pinout"], nombre=nombre)
            ET.fromstring(f"<svg xmlns='http://www.w3.org/2000/svg'>{svg}</svg>")


if __name__ == "__main__":
    unittest.main()
