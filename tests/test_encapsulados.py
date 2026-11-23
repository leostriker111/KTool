"""El dibujo de cada placa (hw/encapsulados.py) contra el catalogo (hw/placas.py)
y el planificador de pines (gui/pin_planner.py).

Las pruebas del widget necesitan pantalla (Tk). Donde no hay, se saltan solas.
"""

import tkinter as tk
import unittest
import xml.etree.ElementTree as ET

from ktool.hw import encapsulados, placas


def _todos_los_dibujos():
    """(placa, dibujo) de cada dibujo de cada placa con pines."""
    for placa, dibujos in encapsulados.DIBUJOS_DE_PLACA.items():
        for dibujo in dibujos:
            yield placa, dibujo


def _numeros_en_lados(encapsulado):
    """Todas las patas que aparecen en los lados, con repeticiones."""
    numeros = []
    for lado, lista in encapsulado["lados"].items():
        for elemento in lista:
            if lado == "doble_derecha":
                numeros.extend(elemento)
            elif elemento is not None:
                numeros.append(elemento)
    return numeros


class CoherenciaConPlacas(unittest.TestCase):

    def test_cada_placa_con_pines_tiene_dibujo(self):
        self.assertEqual(set(encapsulados.DIBUJOS_DE_PLACA), set(placas.PLACAS_CON_PINES))
        for _placa, dibujo in _todos_los_dibujos():
            self.assertIn(dibujo, encapsulados.ENCAPSULADOS)

    def test_cada_pin_utilizable_esta_dibujado(self):
        for placa, dibujo in _todos_los_dibujos():
            info = placas.PLACAS_CON_PINES[placa]
            dibujados = {p.id for p in encapsulados.ENCAPSULADOS[dibujo]["patas"].values()}
            for pin in list(info["entradas"]) + list(info["salidas"]):
                self.assertIn(pin, dibujados, f"{dibujo}: falta el pin {pin!r}")

    def test_cada_id_dibujado_es_asignable(self):
        for placa, dibujo in _todos_los_dibujos():
            usables = encapsulados.asignables(placa)
            for pata in encapsulados.ENCAPSULADOS[dibujo]["patas"].values():
                if pata.id is not None:
                    self.assertIn(pata.id, usables, f"{dibujo}: pata {pata.numero}")

    def test_alimentacion_jtag_flash_usb_no_llevan_pin_utilizable(self):
        for placa, dibujo in _todos_los_dibujos():
            usables = encapsulados.asignables(placa)
            for pata in encapsulados.ENCAPSULADOS[dibujo]["patas"].values():
                if pata.tipo in encapsulados.TIPOS_SIN_SENAL:
                    self.assertFalse(pata.id is not None and pata.id in usables,
                                     f"{dibujo}: pata {pata.numero} es {pata.tipo}")

    def test_tipos_validos(self):
        for _placa, dibujo in _todos_los_dibujos():
            for pata in encapsulados.ENCAPSULADOS[dibujo]["patas"].values():
                self.assertIn(pata.tipo, encapsulados.TIPOS, f"{dibujo}: {pata}")

    def test_numeros_unicos_y_completos(self):
        for _placa, dibujo in _todos_los_dibujos():
            enc = encapsulados.ENCAPSULADOS[dibujo]
            numeros = sorted(enc["patas"])
            self.assertEqual(numeros, list(range(1, len(numeros) + 1)), dibujo)
            for numero, pata in enc["patas"].items():
                self.assertEqual(numero, pata.numero)
        self.assertEqual(sorted(encapsulados.ENCAPSULADOS["pic18f45k50"]["patas"]),
                         list(range(1, 41)))
        self.assertEqual(sorted(encapsulados.ENCAPSULADOS["pic16f84a"]["patas"]),
                         list(range(1, 19)))
        self.assertEqual(sorted(encapsulados.ENCAPSULADOS["max2"]["patas"]),
                         list(range(1, 101)))

    def test_los_lados_dibujan_cada_pata_una_vez(self):
        for _placa, dibujo in _todos_los_dibujos():
            enc = encapsulados.ENCAPSULADOS[dibujo]
            self.assertEqual(sorted(_numeros_en_lados(enc)), sorted(enc["patas"]), dibujo)

    def test_patas_de_placas_py_coinciden_con_el_dip(self):
        # placas.py guarda la pata DIP de cada puerto; donde el dibujo tiene ese
        # puerto como asignable, debe estar en el mismo numero
        for placa in ("pic18f4550", "pic18f45k50", "pic16f877a", "pic16f628a", "pic16f84a"):
            patas = placas.PLACAS_CON_PINES[placa]["patas"]
            for pin in encapsulados.asignables(placa):
                self.assertEqual(encapsulados.pata_de(placa, pin).numero, patas[pin],
                                 f"{placa} {pin}")


class DatosDeLasHojas(unittest.TestCase):

    def test_la_pata_18_cambia_entre_los_pic_de_40(self):
        def pata_18(dibujo):
            return encapsulados.ENCAPSULADOS[dibujo]["patas"][18]
        self.assertEqual(pata_18("pic18f45k50").etiqueta, "VUSB3V3")
        self.assertEqual(pata_18("pic18f4550").etiqueta, "VUSB")
        self.assertEqual(pata_18("pic16f877a").etiqueta, "RC3")
        self.assertEqual(pata_18("pic16f877a").id, "RC3")

    def test_alimentacion_y_jtag_de_la_max2(self):
        patas = encapsulados.ENCAPSULADOS["max2"]["patas"]
        esperado = {
            "VCCIO1": [9, 31, 45], "VCCIO2": [59, 80, 94], "VCCINT": [13, 63],
            "GNDINT": [11, 65], "GNDIO": [10, 32, 46, 60, 79, 93],
            "TMS": [22], "TDI": [23], "TCK": [24], "TDO": [25],
            "GCLK0": [12], "GCLK1": [14], "GCLK2": [62], "GCLK3": [64],
            "DEV_OE": [43], "DEV_CLRn": [44],
        }
        for etiqueta, numeros in esperado.items():
            self.assertEqual(sorted(n for n, p in patas.items() if p.etiqueta == etiqueta),
                             numeros, etiqueta)
        for numero in placas.EPM240_BANCO_1:
            self.assertEqual(patas[numero].etiqueta, "B1")
        for numero in placas.EPM240_BANCO_2:
            self.assertEqual(patas[numero].etiqueta, "B2")

    def test_posicion_en_cabezal(self):
        self.assertEqual(encapsulados.posicion("esp32_wroom32", 24), "J3-5")
        self.assertEqual(encapsulados.posicion("pic18f45k50", 33), "pata 33")
        self.assertEqual(encapsulados.posicion("pico", 40), "pata 40")


class Reglas(unittest.TestCase):

    def test_salida_en_pin_solo_entrada(self):
        puede, texto = encapsulados.puede_ir("esp32_wroom32", 34, "salida")
        self.assertFalse(puede)
        self.assertIn("solo sirve de entrada", texto)
        puede, texto = encapsulados.puede_ir("esp32_wroom32", 34, "entrada")
        self.assertTrue(puede)
        self.assertIn("10 kOhm", texto)

    def test_pin_de_reserva_pasa_con_aviso(self):
        puede, texto = encapsulados.puede_ir("pic16f628a", "RB6", "salida")
        self.assertTrue(puede)
        self.assertIn("PGC", texto)

    def test_pines_especiales_de_la_max2(self):
        self.assertTrue(encapsulados.puede_ir("max2", 12, "reloj")[0])
        self.assertFalse(encapsulados.puede_ir("max2", 12, "entrada")[0])
        self.assertTrue(encapsulados.puede_ir("max2", 44, "reset")[0])
        self.assertFalse(encapsulados.puede_ir("max2", 44, "salida")[0])
        self.assertFalse(encapsulados.puede_ir("max2", 9, "entrada")[0])   # VCCIO1

    def test_reloj_en_pin_normal_cuenta_como_entrada(self):
        self.assertTrue(encapsulados.puede_ir("uno_nano", "2", "reloj")[0])


class Svg(unittest.TestCase):

    def test_cada_dibujo_es_xml_valido(self):
        for placa, dibujo in _todos_los_dibujos():
            usables = list(encapsulados.asignables(placa))
            asignacion = {usables[0]: "A", usables[1]: "Y_1"}
            texto = encapsulados.svg(placa, asignacion, dibujo=dibujo)
            raiz = ET.fromstring(texto)
            self.assertTrue(raiz.tag.endswith("svg"), dibujo)
            textos = [t.text for t in raiz.iter("{http://www.w3.org/2000/svg}text")]
            self.assertIn("A", textos, dibujo)
            self.assertIn("Y_1", textos, dibujo)

    def test_titulo_propio_y_caracteres_escapados(self):
        texto = encapsulados.svg("max2", {26: "A<B"}, titulo="Mi practica & co")
        raiz = ET.fromstring(texto)
        textos = [t.text for t in raiz.iter("{http://www.w3.org/2000/svg}text")]
        self.assertIn("Mi practica & co", textos)
        self.assertIn("A<B", textos)


class Planificador(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin pantalla para Tk")
        self.root.withdraw()
        from ktool.gui.pin_planner import PinPlanner
        self.PinPlanner = PinPlanner
        self.cambios = []

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def planner(self, placa, senales, asignacion=None):
        p = self.PinPlanner(self.root, placa, senales, asignacion,
                            al_cambiar=self.cambios.append)
        p.pack()
        self.root.update_idletasks()
        return p

    def test_asignar_y_soltar(self):
        p = self.planner("pic18f45k50", [("A", "entrada"), ("Y", "salida")])
        self.assertTrue(p.asignar("A", 33))
        self.assertEqual(p.obtener(), {"A": "RB0"})
        self.assertEqual(self.cambios[-1], {"A": "RB0"})
        self.assertEqual(p.soltar(33), "A")
        self.assertEqual(p.obtener(), {})
        self.assertEqual(self.cambios[-1], {})

    def test_clic_en_la_pata(self):
        p = self.planner("pic18f45k50", [("A", "entrada"), ("Y", "salida")])
        p._dibujar()
        zonas = {numero: (x0, y0, x1, y1) for x0, y0, x1, y1, numero in p._zonas}

        class Evento:
            pass

        def clic(numero):
            x0, y0, x1, y1 = zonas[numero]
            evento = Evento()
            evento.x, evento.y = (x0 + x1) / 2, (y0 + y1) / 2
            p._al_clic(evento)

        clic(34)            # A estaba en la mano
        clic(19)            # luego pasa sola a Y
        self.assertEqual(p.obtener(), {"A": "RB1", "Y": "RD0"})
        clic(34)            # clic en una pata ocupada: la suelta
        self.assertEqual(p.obtener(), {"Y": "RD0"})
        clic(11)            # VDD no responde
        self.assertEqual(p.obtener(), {"Y": "RD0"})

    def test_rechaza_salida_en_pin_solo_entrada(self):
        p = self.planner("esp32_wroom32", [("A", "entrada"), ("Y", "salida")])
        numero = encapsulados.pata_de("esp32_wroom32", 34).numero
        self.assertFalse(p.asignar("Y", numero))
        self.assertIn("solo sirve de entrada", p.estado.cget("text"))
        self.assertEqual(p.obtener(), {})
        self.assertTrue(p.asignar("A", numero))
        self.assertIn("Aviso", p.estado.cget("text"))

    def test_pata_de_alimentacion_no_se_asigna(self):
        p = self.planner("max2", [("A", "entrada")])
        self.assertFalse(p.asignar("A", 9))
        self.assertFalse(p.asignar("A", 22))
        self.assertEqual(p.obtener(), {})

    def test_reserva_se_acepta_con_aviso(self):
        p = self.planner("pic16f628a", [("Y", "salida")])
        self.assertTrue(p.asignar("Y", 12))
        self.assertEqual(p.obtener(), {"Y": "RB6"})
        self.assertIn("PGC", p.estado.cget("text"))

    def test_que_ktool_las_elija(self):
        p = self.planner("max2", [("clk", "reloj"), ("rst", "reset"),
                                  ("A", "entrada"), ("Y", "salida")])
        p.elegir_automatico()
        self.assertEqual(p.obtener(), {"clk": 12, "rst": 44,
                                       "A": placas.EPM240_BANCO_1[0],
                                       "Y": placas.EPM240_BANCO_2[0]})
        p.soltar_todas()
        self.assertEqual(p.obtener(), {})

    def test_no_alcanzan_los_pines(self):
        senales = [(f"E{k}", "entrada") for k in range(8)]
        p = self.planner("pic16f84a", senales)
        p.elegir_automatico()
        self.assertEqual(p.obtener(), {})
        self.assertIn("No alcanzan", p.estado.cget("text"))

    def test_asignacion_inicial_invalida_se_descarta(self):
        p = self.planner("esp32_wroom32", [("A", "entrada"), ("Y", "salida")],
                         {"A": 32, "Y": 34})
        self.assertEqual(p.obtener(), {"A": 32})
        self.assertIn("Y", p.estado.cget("text"))

    def test_uno_y_nano_comparten_la_asignacion(self):
        p = self.planner("uno_nano", [("A", "entrada")], {"A": "2"})
        p.vista.set(encapsulados.ENCAPSULADOS["nano"]["titulo"])
        p._al_cambiar_vista()
        self.assertEqual(p.dibujo, "nano")
        self.assertEqual(p.obtener(), {"A": "2"})
        self.assertIn("J1-5", p.lista.item("A", "values")[2])


if __name__ == "__main__":
    unittest.main()
