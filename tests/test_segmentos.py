"""Displays de segmentos: tipografias, tablas de mensajes, barra y dibujos.

La parte de la ventana necesita pantalla (Tk); donde no hay, se salta sola.
"""

import tkinter as tk
import unittest
import xml.etree.ElementTree as ET

from ktool import ejemplos
from ktool import segmentos as seg
from ktool.hw.modelo import validar_nombres

SVG_NS = "{http://www.w3.org/2000/svg}"


def fila(proyecto, n):
    """{salida: valor} de la fila n de un proyecto."""
    return {s: col[n] for s, col in zip(proyecto["output_names"], proyecto["values"])}


class Tipografias(unittest.TestCase):

    def test_los_digitos_de_7_son_los_de_la_practica(self):
        for n in range(10):
            obtenido = "".join(str(v) for v in seg.segmentos(str(n), "7seg").values())
            self.assertEqual(obtenido, ejemplos.SIETE_SEG[n], n)

    def test_las_letras_hexadecimales_de_7_coinciden(self):
        for n, letra in zip(range(10, 16), "ABCDEF"):
            obtenido = "".join(str(v) for v in seg.segmentos(letra, "7seg").values())
            self.assertEqual(obtenido, ejemplos.SIETE_SEG[n], letra)

    def test_cada_caracter_usa_solo_segmentos_del_tipo(self):
        for tipo, tipografia in seg.TIPOGRAFIAS.items():
            for caracter, lista in tipografia.items():
                for nombre in lista.split():
                    self.assertIn(nombre, seg.TIPOS[tipo], (tipo, caracter))

    def test_14_y_16_traen_el_alfabeto_completo(self):
        for tipo in ("14seg", "16seg"):
            disponibles = seg.soportados(tipo)
            for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_=+*/":
                self.assertIn(c, disponibles, (tipo, c))

    def test_las_letras_no_distinguen_mayusculas(self):
        self.assertEqual(seg.segmentos("h", "16seg"), seg.segmentos("H", "16seg"))

    def test_un_caracter_que_no_existe_da_un_error_claro(self):
        with self.assertRaises(ValueError) as ctx:
            seg.segmentos("M", "7seg")
        self.assertIn("14 o 16 segmentos", str(ctx.exception))
        with self.assertRaises(ValueError):
            seg.segmentos("#", "14seg")
        with self.assertRaises(ValueError):
            seg.segmentos("A", "9seg")
        self.assertEqual(seg.no_soportados("MAMA", "7seg"), "M")

    def test_los_nombres_de_segmentos_compilan(self):
        for tipo, nombres in seg.TIPOS.items():
            validar_nombres(["N2", "N1", "N0"], nombres + [seg.PUNTO])
        validar_nombres(["V3", "V2", "V1", "V0"], seg.BARRA10)

    def test_el_punto_se_pega_al_caracter_anterior(self):
        digitos = seg.texto("3.14", "7seg", con_punto=True)
        self.assertEqual(len(digitos), 3)
        self.assertEqual([d[seg.PUNTO] for d in digitos], [1, 0, 0])


class Mensajes(unittest.TestCase):

    def test_cada_fila_es_su_caracter(self):
        for tipo in seg.TIPOS:
            cadena = "HOLA 15"
            p = seg.proyecto_mensaje(cadena, tipo)
            self.assertEqual(p["input_names"], ["N2", "N1", "N0"])
            self.assertEqual(p["output_names"], seg.TIPOS[tipo])
            validar_nombres(p["input_names"], p["output_names"])
            for n, caracter in enumerate(cadena):
                self.assertEqual(fila(p, n), seg.segmentos(caracter, tipo), (tipo, n))
            self.assertEqual(set(fila(p, 7).values()), {"x"})

    def test_minimo_dos_entradas_y_maximo_64_caracteres(self):
        self.assertEqual(seg.proyecto_mensaje("A", "7seg")["nvars"], 2)
        self.assertEqual(seg.proyecto_mensaje("A" * 64, "16seg")["nvars"], 6)
        with self.assertRaises(ValueError):
            seg.proyecto_mensaje("A" * 65, "16seg")
        with self.assertRaises(ValueError):
            seg.proyecto_mensaje("", "7seg")

    def test_anodo_comun_invierte_y_conserva_los_no_importa(self):
        catodo = seg.proyecto_mensaje("HOLA1", "14seg")
        anodo = seg.proyecto_mensaje("HOLA1", "14seg", anodo_comun=True)
        for col_c, col_a in zip(catodo["values"], anodo["values"]):
            for c, a in zip(col_c, col_a):
                self.assertEqual(a, "x" if c == "x" else 1 - c)

    def test_nombres_de_entrada_propios(self):
        p = seg.proyecto_mensaje("HOLA", "7seg", nombres_entrada=["S1", "S0"])
        self.assertEqual(p["input_names"], ["S1", "S0"])
        with self.assertRaises(ValueError):       # "a" chocaria con el segmento a
            seg.proyecto_mensaje("HOLA", "7seg", nombres_entrada=["A", "B"])
        with self.assertRaises(ValueError):       # faltan nombres
            seg.proyecto_mensaje("HOLA", "7seg", nombres_entrada=["S0"])


class Barra(unittest.TestCase):

    def test_modo_nivel(self):
        p = seg.proyecto_barra(10, "nivel")
        self.assertEqual(p["input_names"], ["V3", "V2", "V1", "V0"])
        self.assertEqual(p["output_names"], seg.BARRA10)
        for valor in range(11):
            esperado = {f"L{k}": int(k < valor) for k in range(10)}
            self.assertEqual(fila(p, valor), esperado, valor)
        for valor in range(11, 16):
            self.assertEqual(set(fila(p, valor).values()), {"x"})

    def test_modo_punto(self):
        p = seg.proyecto_barra(10, "punto")
        for valor in range(10):
            encendidos = [s for s, v in fila(p, valor).items() if v == 1]
            self.assertEqual(encendidos, [f"L{valor}"])
        for valor in range(10, 16):
            self.assertEqual(set(fila(p, valor).values()), {"x"})

    def test_errores(self):
        with self.assertRaises(ValueError):
            seg.proyecto_barra(10, "otro")
        with self.assertRaises(ValueError):
            seg.proyecto_barra(40)


class Dibujos(unittest.TestCase):

    def test_svg_de_un_digito_es_xml_valido(self):
        for tipo in seg.TIPOS:
            raiz = ET.fromstring(seg.svg(tipo, seg.segmentos("8", tipo)))
            self.assertEqual(raiz.tag, SVG_NS + "svg")
            poligonos = raiz.findall(SVG_NS + "polygon")
            self.assertEqual(len(poligonos), len(seg.TIPOS[tipo]))   # sin dp
            rellenos = {p.get("fill") for p in poligonos}
            self.assertIn(seg.SVG_ENCENDIDO, rellenos)

    def test_svg_con_punto_y_barra(self):
        digito = seg.segmentos("1", "7seg", con_punto=True)
        raiz = ET.fromstring(seg.svg("7seg", digito, ancho=56))
        self.assertEqual(len(raiz.findall(SVG_NS + "polygon")), 8)
        self.assertEqual(raiz.get("width"), "56")
        barra = {f"L{k}": int(k < 3) for k in range(10)}
        raiz = ET.fromstring(seg.svg("barra10", barra))
        encendidos = [p for p in raiz.findall(SVG_NS + "polygon")
                      if p.get("fill") == seg.SVG_ENCENDIDO]
        self.assertEqual(len(encendidos), 3)

    def test_svg_texto_pone_los_digitos_lado_a_lado(self):
        raiz = ET.fromstring(seg.svg_texto("HOLA", "16seg"))
        self.assertEqual(len(raiz.findall(SVG_NS + "polygon")), 4 * 16)
        _poligonos, w, h = seg.geometria("16seg")
        self.assertEqual(raiz.get("viewBox"), f"0 0 {4 * w} {h}")


class AppFalsa:
    """Lo que DisplayWidget usa de la ventana principal."""

    def __init__(self, root):
        self.root = root
        self.displays = []
        self.refrescos = 0

    def _refresh_displays(self):
        self.refrescos += 1


class Ventana(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin pantalla para Tk")
        self.root.withdraw()

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.update_idletasks()   # corre los after_idle antes de cerrar
            self.root.destroy()

    def test_los_displays_se_crean_encienden_y_guardan_sus_nombres(self):
        from ktool.gui.displays import DisplayWidget, display_desde_dict, nombres_por_omision
        app = AppFalsa(self.root)
        for kind in ("7seg", "14seg", "16seg", "barra10", "led"):
            d = DisplayWidget(app, self.root, kind)
            self.assertEqual(d.nombres(), nombres_por_omision(kind))
            d.relight({d.nombres()[0]: 1})
            guardado = d.a_dict()
            self.assertEqual(guardado["kind"], kind)
            nombres = [f"S{k}" for k in range(len(guardado["nombres"]))]
            otro = display_desde_dict(app, self.root, {"kind": kind, "nombres": nombres})
            self.assertEqual(otro.nombres(), nombres)
        self.assertEqual(nombres_por_omision("14seg"), seg.TIPOS["14seg"] + [seg.PUNTO])
        # formato viejo (solo el tipo) y tipo desconocido
        self.assertEqual(display_desde_dict(app, self.root, "7seg").nombres()[:7],
                         seg.TIPOS["7seg"])
        self.assertIsNone(display_desde_dict(app, self.root, "99seg"))

    def test_la_ventana_de_texto_crea_la_tabla(self):
        from ktool.gui.texto_segmentos import VentanaTextoASegmentos
        creados = []
        v = VentanaTextoASegmentos(self.root, creados.append)
        v.tipo.set("7seg")
        v.texto.set("HOLA M")
        self.root.update()
        self.assertIn("'M'", v.estado.cget("text"))
        self.assertIn("disabled", v.boton_crear.state())
        v.crear()
        self.assertEqual(creados, [])
        v.tipo.set("16seg")
        v.anodo.set(True)
        self.root.update()
        self.assertNotIn("disabled", v.boton_crear.state())
        v.crear()
        self.assertEqual(len(creados), 1)
        esperado = seg.proyecto_mensaje("HOLA M", "16seg", anodo_comun=True)
        self.assertEqual(creados[0]["values"], esperado["values"])


if __name__ == "__main__":
    unittest.main()
