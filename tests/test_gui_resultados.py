"""La ventana: el panel de Resultados, el proyecto y los ejemplos.

Necesita pantalla (Tk). Donde no hay, como en la CI, se salta solo.
"""

import json
import os
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from ktool import ejemplos


class VentanaBase(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin pantalla para Tk")
        self.root.withdraw()
        from ktool.gui.app import App
        self.dir = tempfile.TemporaryDirectory()
        # el autoguardado y la papelera de la prueba no van al LOCALAPPDATA real
        self._env = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.dir.name})
        self._env.start()
        self.app = App(self.root)
        self.app.nvars.set(2)
        self.app.nouts.set(2)
        self.app.apply_dims()
        self.app.output_names[:] = ["Y_AND", "Y_XOR"]
        self.app.values[0] = [0, 0, 0, 1]
        self.app.values[1] = [0, 1, 1, 0]
        self.app.rebuild_table()
        self.panel = self.app.resultados

    def tearDown(self):
        if hasattr(self, "_env"):
            self._env.stop()
            self.root.destroy()
            self.dir.cleanup()


class PanelResultados(VentanaBase):

    def test_las_ecuaciones_se_llenan_al_entrar(self):
        self.panel.mostrar("generar")
        self.root.update()
        self.panel.mostrar("ecuaciones")
        self.root.update()
        texto = self.panel.texto_ecuaciones.get("1.0", "end")
        self.assertIn("Y_XOR", texto)
        self.assertIn("mejor por costo", texto)

    def test_generar_todo_saca_todo_en_una_carpeta(self):
        self.panel.portada["titulo"].set("Compuertas basicas")
        self.panel.portada["reviso"].set("Quien revisa")
        self.panel.generar_carpeta.set(self.dir.name)
        self.panel.generar_todo()
        carpeta = os.path.join(self.dir.name, "compuertas_basicas")
        nombres = sorted(os.listdir(carpeta))
        self.assertEqual(nombres, ["compuertas_basicas.html", "compuertas_basicas.ktool.json",
                                   "compuertas_basicas_armado.html", "kit"])
        with open(os.path.join(carpeta, "compuertas_basicas.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn("<div class='portada'><h1>Compuertas basicas</h1>", html)
        self.assertIn("Quien revisa", html)
        for seccion in ("Tabla de verdad", "Armado en protoboard", "Kit de hardware"):
            self.assertIn(f"<h2>{seccion}", html)
        self.assertTrue(os.path.exists(os.path.join(carpeta, "kit", "pic", "pic18f45k50.c")))

    def test_lo_que_no_se_palomea_no_sale(self):
        for clave in ("kit", "proto", "armado_aparte", "kit_carpeta", "proyecto"):
            self.panel.contiene[clave].set(False)
        self.panel.generar_carpeta.set(self.dir.name)
        self.panel.generar_todo()
        carpeta = os.path.join(self.dir.name, "resultados_ktool")
        self.assertEqual(os.listdir(carpeta), ["resultados_ktool.html"])

    def test_un_chip_que_no_existe_avisa(self):
        self.panel.proto_modo.set("solo los chips que tengo")
        self.panel.proto_chips.set("7400, 9999")
        with mock.patch("ktool.gui.resultados.messagebox.showerror") as error:
            self.panel.generar_armado()
        self.assertIn("9999", error.call_args[0][1])

    def test_kit_con_pines_propios_y_uno_malo(self):
        carpeta = os.path.join(self.dir.name, "kit")
        self.panel.kit_carpeta.set(carpeta)
        self.panel.kit_placa.set("Intel/Altera MAX II EPM240T100C5")
        self.panel._al_cambiar_placa()
        self.panel.kit_pines.set("26,28,33,9")      # 9 es VCCIO
        with mock.patch("ktool.gui.resultados.messagebox.showerror") as error:
            self.panel.escribir_kit()
        self.assertIn("no es utilizable", error.call_args[0][1])
        self.assertFalse(os.path.exists(carpeta))
        self.panel.kit_pines.set("26,28,33,73")
        self.panel.escribir_kit()
        with open(os.path.join(carpeta, "fpga", "circuito.qsf"), encoding="utf-8") as f:
            self.assertIn("set_location_assignment PIN_73 -to Y_XOR", f.read())


class Proyecto(VentanaBase):

    def test_guardar_y_abrir_devuelve_todo(self):
        self.app.input_names[:2] = ["SEL", "EN"]
        self.app.rebuild_table()
        self.panel.portada["autor"].set("Quien firma")
        self.panel.proto_extremos.set("display 7 seg, anodo comun")
        self.panel.kit_placa.set("Arduino Uno / Nano (ATmega328P)")
        self.panel._al_cambiar_placa()
        self.panel.kit_pines.set("2,3,8,9")
        ruta = os.path.join(self.dir.name, "p.ktool.json")
        self.app._ruta = ruta
        self.assertTrue(self.app.guardar())
        guardado = self.app.serializar()

        self.app.nuevo()
        self.assertEqual(self.app.input_names, ["A", "B", "C"])
        self.app.abrir(ruta)
        self.assertEqual(json.dumps(self.app.serializar(), sort_keys=True),
                         json.dumps(guardado, sort_keys=True))
        self.assertFalse(self.app._hay_cambios())

    def test_descartar_sin_guardar_va_a_la_papelera(self):
        self.app.values[0] = [1, 1, 1, 1]
        with mock.patch("ktool.gui.app.messagebox.askyesnocancel", return_value=False):
            self.app.nuevo()
        papelera = os.path.join(self.dir.name, "ktool", "papelera")
        self.assertEqual(len(os.listdir(papelera)), 1)

    def test_cada_ejemplo_abre_y_resuelve(self):
        for _grupo, lista in ejemplos.CATALOGO:
            for titulo, hacer in lista:
                with mock.patch("ktool.gui.app.messagebox.askyesnocancel", return_value=False):
                    self.app.abrir_ejemplo(hacer)
                proyecto = hacer()
                self.assertEqual(self.app.input_names, proyecto["input_names"], titulo)
                self.assertEqual(self.panel.portada["titulo"].get(),
                                 proyecto["proyecto"]["titulo"])
                texto = self.panel.texto_ecuaciones.get("1.0", "end")
                for salida in proyecto["output_names"]:
                    self.assertIn(f"[{salida}]", texto, titulo)


class Entradas(VentanaBase):

    def test_renombrar_una_entrada_llega_a_todo(self):
        with mock.patch("ktool.gui.app.simpledialog.askstring", return_value="SEL"):
            self.app.rename_input(0)
        tabla = self.app._current_table()
        self.assertEqual(tabla.variables, ["SEL", "B"])
        self.panel.actualizar_ecuaciones()
        self.assertIn("SEL B", self.panel.texto_ecuaciones.get("1.0", "end"))

    def test_un_nombre_que_no_compila_se_rechaza(self):
        for malo in ("or", "2X", "Y_AND"):     # reservado, empieza con numero, ya es salida
            with mock.patch("ktool.gui.app.simpledialog.askstring", return_value=malo), \
                    mock.patch("ktool.gui.app.messagebox.showerror") as error:
                self.app.rename_input(0)
            self.assertTrue(error.called, malo)
        self.assertEqual(self.app.input_names[0], "A")

    def test_la_expresion_entiende_nombres_largos(self):
        self.app.input_names[:2] = ["SEL", "D0"]
        self.app.rebuild_table()
        self.app.expr_texto.set("SEL' D0")
        self.app.expr_target.set("Y_AND")
        self.app.fill_from_expr()
        self.assertEqual(self.app.values[0], [0, 1, 0, 0])


if __name__ == "__main__":
    unittest.main()
