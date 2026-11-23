"""`--agregar-al-path`: la carpeta entra una sola vez y el resto del PATH no cambia."""

import unittest

from ktool.ruta import path_con


class PathCon(unittest.TestCase):

    def test_agrega_al_final(self):
        nuevo, ya = path_con(r"C:\uno;C:\dos", r"C:\tres")
        self.assertEqual(nuevo, r"C:\uno;C:\dos;C:\tres")
        self.assertFalse(ya)

    def test_no_la_repite_aunque_cambien_mayusculas_o_la_diagonal(self):
        for como_estaba in (r"C:\Py\Scripts", r"c:\py\scripts", "C:\\Py\\Scripts\\"):
            nuevo, ya = path_con(r"C:\uno;" + como_estaba, r"C:\Py\Scripts")
            self.assertTrue(ya, como_estaba)
            self.assertEqual(nuevo.count(";"), 1)

    def test_las_variables_se_quedan_sin_expandir(self):
        crudo = r"%USERPROFILE%\AppData\Local\Microsoft\WindowsApps;C:\uno"
        nuevo, _ = path_con(crudo, r"C:\Py\Scripts")
        self.assertTrue(nuevo.startswith(r"%USERPROFILE%\AppData"))

    def test_path_vacio_o_con_huecos(self):
        self.assertEqual(path_con("", r"C:\x")[0], r"C:\x")
        self.assertEqual(path_con(r"C:\a;;C:\b;", r"C:\x")[0], r"C:\a;C:\b;C:\x")


if __name__ == "__main__":
    unittest.main()
