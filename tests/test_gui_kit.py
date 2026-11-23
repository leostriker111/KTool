"""La ventana del kit, la calculadora y los menus nuevos.

Necesita pantalla (Tk). Donde no hay, como en la CI, se salta solo.
"""

import os
import unittest
from unittest import mock

from ktool import ejemplos

from test_gui_resultados import VentanaBase


class VentanaDelKit(VentanaBase):

    def abrir(self):
        from ktool.gui.kit_ventana import FuenteTabla, VentanaKit
        v = VentanaKit(self.root, self.panel.kit_config, FuenteTabla(self.app),
                       al_cambiar=self.panel._al_cambiar_kit)
        v.win.withdraw()
        self.root.update()
        return v

    def test_usar_y_soltar_una_plataforma(self):
        v = self.abrir()
        self.assertIn("max2", self.panel.kit_config.elegidas)
        v._alternar("max2")
        self.assertNotIn("max2", self.panel.kit_config.elegidas)
        self.assertEqual(v.arbol.set("max2", "usar"), "[ ]")
        v._alternar("gal22v10")
        self.assertIn("gal22v10", self.panel.kit_config.elegidas)
        self.assertEqual(v.arbol.set("gal22v10", "estado"), "listo")

    def test_sin_pines_fijos_el_planificador_muestra_los_de_ktool(self):
        v = self.abrir()
        v.arbol.selection_set("max2")
        self.root.update()
        pines = self.panel.kit_config.pines["max2"]
        self.assertEqual(set(pines), {"A", "B", "Y_AND", "Y_XOR"})

    def test_un_ajuste_llega_al_codigo(self):
        v = self.abrir()
        v.arbol.selection_set("pic18f45k50")
        self.root.update()
        v._al_cambiar_ajuste("salidas", "activas en bajo")
        v._rearmar()
        self.assertIn("^ 1u", v.kit.archivos["pic/pic18f45k50.c"])

    def test_un_numero_mal_escrito_se_dice_sin_ventana(self):
        v = self.abrir()
        v.arbol.selection_set("max2")
        self.root.update()
        v._al_cambiar_ajuste("frecuencia_hz", "uno")
        self.assertIn("no es un numero", v.ajustes_estado.cget("text"))

    def test_editar_restaurar_y_escribir(self):
        v = self.abrir()
        v.arbol.selection_set("python")
        self.root.update()
        v.notebook.select(v.tab_archivos)
        self.root.update()
        v.texto.delete("1.0", "end")
        v.texto.insert("1.0", "# corregido a mano\n")
        v._guardar_archivo()
        self.assertEqual(self.panel.kit_config.editados["python/simular.py"],
                         "# corregido a mano\n")
        self.assertIn("(editado)", v.lista_archivos.get(0))

        carpeta = os.path.join(self.dir.name, "kit")
        v.carpeta.set(carpeta)
        v.escribir()
        with open(os.path.join(carpeta, "python", "simular.py"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "# corregido a mano\n")

        with mock.patch("ktool.gui.kit_ventana.messagebox.askyesno", return_value=True):
            v._restaurar_archivo()
        self.assertNotIn("python/simular.py", self.panel.kit_config.editados)

    def test_el_documento_describe_la_configuracion(self):
        config = self.panel.kit_config
        config.elegidas = ["max2"]
        config.ajustes["max2"] = {"salidas": "activas en bajo"}
        config.editados["fpga/circuito.qsf"] = "# a mano\n"
        self.panel.generar_carpeta.set(self.dir.name)
        self.panel.generar_todo()
        with open(os.path.join(self.dir.name, "resultados_ktool", "resultados_ktool.html"),
                  encoding="utf-8") as f:
            html = f.read()
        self.assertIn("<h3>Intel/Altera MAX II EPM240T100C5</h3>", html)
        self.assertIn("activas en bajo", html)
        self.assertIn("(editado a mano)", html)
        self.assertNotIn("Frecuencia de la maquina", html)   # solo en maquinas de estado


class Calculadora(VentanaBase):

    def test_divisor_y_usar_en_el_kit(self):
        from ktool.gui.calculadora import VentanaCalculadora
        usados = []
        c = VentanaCalculadora(self.root, f_entrada=50e6, f_salida=1,
                               al_usar=lambda f, e: usados.append((f, e)))
        c.win.withdraw()
        self.assertEqual(c.calculo.cuenta_medio_periodo, 25000000)
        c.pedir.set("periodo")
        c.valor.set("3")
        self.assertEqual(c.calculo.cuenta_medio_periodo, 75000000)
        self.assertIn("entity divisor is", c._textos_codigo["VHDL (MAX II)"].get("1.0", "end"))
        c._usar()
        self.assertAlmostEqual(usados[0][0], 1 / 3)
        self.assertEqual(usados[0][1], 50e6)

    def test_un_dato_a_medio_escribir_no_truena(self):
        from ktool.gui.calculadora import VentanaCalculadora
        c = VentanaCalculadora(self.root)
        c.win.withdraw()
        c.valor.set("1.")
        c.valor.set("abc")
        self.assertIn("no se entiende", c.estado.cget("text"))

    def test_leer_numero_con_prefijos(self):
        from ktool.gui.calculadora import leer_numero
        self.assertEqual(leer_numero("50M"), 50e6)
        self.assertEqual(leer_numero("50 MHz"), 50e6)
        self.assertAlmostEqual(leer_numero("10u"), 10e-6)
        self.assertEqual(leer_numero("3 s"), 3)
        self.assertEqual(leer_numero("2,5k"), 2500)


class Menus(VentanaBase):

    def test_un_ejemplo_de_display_abre_con_su_display(self):
        for _g, lista in ejemplos.CATALOGO:
            for titulo, hacer in lista:
                if titulo.startswith("Mensaje"):
                    with mock.patch("ktool.gui.app.messagebox.askyesnocancel",
                                    return_value=False):
                        self.app.abrir_ejemplo(hacer)
                    self.assertEqual([d.kind for d in self.app.displays], ["16seg"])
                    return
        self.fail("no hay ejemplo de mensaje")

    def test_los_displays_se_guardan_con_sus_nombres(self):
        self.app.insert_display("barra10")
        datos = self.app.serializar()["displays"]
        self.assertEqual(datos[0]["kind"], "barra10")
        self.app.aplicar(dict(self.app.serializar()))
        self.assertEqual([d.kind for d in self.app.displays], ["barra10"])


if __name__ == "__main__":
    unittest.main()
