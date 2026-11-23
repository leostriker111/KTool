"""El panel de Resultados de la ventana: cada pestana hace lo que dice.

Necesita pantalla (Tk). Donde no hay, como en la CI, se salta solo.
"""

import os
import tempfile
import tkinter as tk
import unittest
from unittest import mock


def _guardar_sin_abrir(html, ruta, open_browser=False):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
    return ruta


class PanelResultados(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin pantalla para Tk")
        self.root.withdraw()
        from ktool.gui.app import App
        self.app = App(self.root)
        self.app.nvars.set(2)
        self.app.nouts.set(2)
        self.app.apply_dims()
        self.app.output_names[:] = ["Y_AND", "Y_XOR"]
        self.app.values[0] = [0, 0, 0, 1]
        self.app.values[1] = [0, 1, 1, 0]
        self.app.rebuild_table()
        self.panel = self.app.resultados
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        if hasattr(self, "dir"):
            self.dir.cleanup()
        self.root.destroy()

    def test_las_ecuaciones_se_llenan_al_entrar(self):
        self.panel.mostrar("documento")
        self.root.update()
        self.panel.mostrar("ecuaciones")
        self.root.update()
        texto = self.panel.texto_ecuaciones.get("1.0", "end")
        self.assertIn("Y_XOR", texto)
        self.assertIn("mejor por costo", texto)

    def test_el_documento_trae_todo_de_entrada(self):
        ruta = os.path.join(self.dir.name, "doc.html")
        with mock.patch("ktool.gui.resultados.filedialog.asksaveasfilename", return_value=ruta), \
                mock.patch("ktool.gui.resultados.save_report", side_effect=_guardar_sin_abrir):
            self.panel.generar_documento()
        with open(ruta, encoding="utf-8") as f:
            html = f.read()
        for seccion in ("Tabla de verdad", "Armado en protoboard",
                        "Ecuaciones en varios lenguajes", "Kit de hardware"):
            self.assertIn(f"<h2>{seccion}", html)

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
        self.assertIn("de 16 listos", self.panel.kit_resumen.get("1.0", "end"))


if __name__ == "__main__":
    unittest.main()
