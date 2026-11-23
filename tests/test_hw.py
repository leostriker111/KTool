"""Kit de hardware: que cada archivo generado haga lo que dice la tabla.

Aqui no hay compiladores (eso se hizo a mano con XC8, arduino-cli, GHDL e
Icarus; ver docs/HARDWARE.md). Lo que se prueba es la LOGICA de cada salida,
evaluada fila por fila contra la tabla original:

  - la ecuacion en C, con un evaluador que respeta la precedencia de C
  - las comparaciones de mascara del PIC, interpretadas renglon por renglon
  - el main.py de MicroPython, corrido con un `machine` de mentira
  - la simulacion en Python, corrida tal cual
y ademas los bloqueos (pines, memoria, macroceldas) y los pines elegidos.
"""

import os
import random
import re
import subprocess
import sys
import tempfile
import types
import unittest

from ktool.core.table import TruthTable
from ktool.hw import kit, logica, micros, placas
from ktool.hw.modelo import (Bloqueo, Circuito, asignar_pines, con_pines, ecuacion,
                             leer_pines)


def tabla_al_azar(semilla, n, salidas, con_dc=True):
    azar = random.Random(semilla)
    opciones = [0, 1, "x"] if con_dc else [0, 1]
    return TruthTable(n, outputs={
        f"S{k}": [azar.choice(opciones) for _ in range(1 << n)] for k in range(salidas)})


def casos():
    """Tablas de 2 a 6 variables en las cuatro formas, mas XOR y constantes."""
    for semilla in range(6):
        for n in (2, 3, 4, 5, 6):
            for forma in ("auto", "sop", "pos", "nand", "nor"):
                yield f"{semilla}-{n}-{forma}", tabla_al_azar(semilla * 10 + n, n, 3), forma
    paridad = [bin(i).count("1") % 2 for i in range(16)]
    yield "xor", TruthTable(4, outputs={"P": paridad, "Q": [1 - v for v in paridad]}), "auto"
    yield "constantes", TruthTable(2, outputs={"UNO": [1] * 4, "CERO": [0] * 4,
                                               "Y": [0, 1, 1, 0]}), "auto"


def revisar(prueba, circuito, evaluar, que):
    """evaluar(fila, entradas) -> {salida: 0/1}; se compara con la tabla."""
    for i, entradas in circuito.filas():
        obtenido = evaluar(i, entradas)
        for s in circuito.salidas:
            esperado = circuito.esperado[s][i]
            if esperado == "x":
                continue
            prueba.assertEqual(obtenido[s], esperado,
                               f"{que}: {s} en la fila {i} da {obtenido[s]}, se esperaba {esperado}")


# ------------------------------------------------- un evaluador de C minimo

def evaluar_c(texto, variables):
    """Evalua una expresion de C con & | ^ ! y parentesis, con la precedencia
    de C: ! > & > ^ > |. Si el generador dependiera de una precedencia
    distinta, aqui sale el error."""
    fichas = re.findall(r"[A-Za-z_]\w*|\d+|[()&|^!]", texto)
    pos = [0]

    def ver():
        return fichas[pos[0]] if pos[0] < len(fichas) else None

    def tomar():
        pos[0] += 1
        return fichas[pos[0] - 1]

    def primario():
        f = tomar()
        if f == "!":
            return 0 if primario() else 1
        if f == "(":
            v = o()
            assert tomar() == ")"
            return v
        return int(f) if f.isdigit() else variables[f]

    def y():
        v = primario()
        while ver() == "&":
            tomar()
            v &= primario()
        return v

    def ox():
        v = y()
        while ver() == "^":
            tomar()
            v ^= y()
        return v

    def o():
        v = ox()
        while ver() == "|":
            tomar()
            v |= ox()
        return v

    resultado = o()
    assert pos[0] == len(fichas), f"sobraron fichas en {texto!r}"
    return resultado


def evaluar_pasos_pic(lineas, x):
    """Interpreta los renglones que genera _pasos_pic para un valor de x."""
    valor = None
    for linea in lineas:
        linea = linea.strip()
        if linea.startswith("//") or linea == "}" or linea.startswith("out_") and "^= 1" in linea:
            continue
        m = re.match(r"uint8_t out_\w+ = (\d+);", linea)
        if m:
            valor = int(m.group(1))
            continue
        m = re.match(r"if \(\(fila__ & 0x(\w+)\) == 0x(\w+)\) out_\w+ = (\d);", linea)
        if m:
            if x & int(m.group(1), 16) == int(m.group(2), 16):
                valor = int(m.group(3))
            continue
        m = re.match(r"for \(uint8_t m__ = \(uint8_t\)\(fila__ & 0x(\w+)\);", linea)
        if m:
            valor ^= bin(x & int(m.group(1), 16)).count("1") % 2
            continue
        raise AssertionError(f"renglon que la prueba no sabe leer: {linea!r}")
    return valor


class Ecuaciones(unittest.TestCase):

    def test_c_y_python_dan_la_tabla(self):
        for nombre, tabla, forma in casos():
            c = Circuito(tabla, forma)
            for s in c.salidas:
                texto_c = ecuacion(c.arboles[s], "c", "in_")
                texto_py = ecuacion(c.arboles[s], "python", "in_")
                for i, entradas in c.filas():
                    esperado = c.esperado[s][i]
                    if esperado == "x":
                        continue
                    nombres = {f"in_{k}": v for k, v in entradas.items()}
                    self.assertEqual(evaluar_c(texto_c, nombres), esperado,
                                     f"C, caso {nombre}, {s}, fila {i}: {texto_c}")
                    self.assertEqual(eval(texto_py, {}, nombres), esperado,
                                     f"Python, caso {nombre}, {s}, fila {i}: {texto_py}")

    def test_python_no_cae_en_la_trampa_de_not(self):
        # `not A ^ B` en Python es `not (A ^ B)`; el generador no usa `not`
        arbol = ("xor", ("not", ("var", "A")), ("var", "B"))
        self.assertNotIn("not", ecuacion(arbol, "python"))
        self.assertEqual(eval(ecuacion(arbol, "python"), {}, {"A": 0, "B": 0}), 1)

    def test_vhdl_pone_parentesis_al_mezclar_operadores(self):
        # en VHDL "A and B or C" ni siquiera compila
        arbol = ("or", ("and", ("var", "A"), ("var", "B")), ("var", "C"))
        self.assertEqual(ecuacion(arbol, "vhdl"), "(A and B) or C")


class PIC(unittest.TestCase):

    def test_las_mascaras_dan_la_tabla(self):
        for nombre, tabla, forma in casos():
            c = Circuito(tabla, forma)
            for s in c.salidas:
                lineas = micros._pasos_pic(c, s)
                for i, _ in c.filas():
                    esperado = c.esperado[s][i]
                    if esperado == "x":
                        continue
                    # x tiene a la primera entrada como bit alto: es el numero de fila
                    self.assertEqual(evaluar_pasos_pic(lineas, i), esperado,
                                     f"PIC, caso {nombre}, {s}, fila {i}")

    def test_cada_entrada_se_lee_con_su_bit(self):
        c = Circuito(tabla_al_azar(1, 4, 1))
        renglones = asignar_pines(c, placas.PIC["pic18f4550"])
        texto = micros.pic(c, "pic18f4550", renglones)
        self.assertIn("if (PORTBbits.RB0) fila__ |= 0x08;   // A", texto)
        self.assertIn("if (PORTBbits.RB3) fila__ |= 0x01;   // D", texto)

    def test_el_877a_apaga_lo_analogico_con_0x06(self):
        c = Circuito(tabla_al_azar(1, 3, 1))
        texto = micros.pic(c, "pic16f877a", asignar_pines(c, placas.PIC["pic16f877a"]))
        self.assertIn("ADCON1 = 0x06;", texto)
        self.assertIn("PORT", texto)
        self.assertNotIn("LAT", texto)   # los PIC16 no tienen LAT

    def test_bloqueo_por_memoria_del_84a(self):
        paridad = [bin(i).count("1") % 2 for i in range(64)]
        tabla = TruthTable(6, outputs={f"S{k}": paridad for k in range(4)})
        with tempfile.TemporaryDirectory() as d:
            resumen = {p: (e, m) for p, e, m in kit.generar(tabla, d, "nand")}
        estado, motivo = resumen["PIC16F84A"]
        self.assertEqual(estado, "bloqueado")
        self.assertIn("palabras", motivo)
        self.assertEqual(resumen["PIC16F628A"][0], "listo")


class Pines(unittest.TestCase):

    def test_bloqueo_por_pines_dice_la_cuenta(self):
        c = Circuito(tabla_al_azar(2, 6, 10))
        with self.assertRaises(Bloqueo) as e:
            asignar_pines(c, placas.ESP32["esp32_c3"])
        self.assertIn("requiere 6 entradas + 10 salidas = 16 pines", str(e.exception))
        self.assertIn("13 utilizables (8 seguros + 5 de reserva)", str(e.exception))

    def test_el_uno_cede_al_mega(self):
        with tempfile.TemporaryDirectory() as d:
            resumen = {p: e for p, e, _ in kit.generar(tabla_al_azar(3, 6, 20), d)}
            self.assertEqual(resumen[placas.ARDUINO["uno_nano"]["titulo"]], "bloqueado")
            self.assertEqual(resumen[placas.ARDUINO["mega2560"]["titulo"]], "listo")
            self.assertTrue(os.path.exists(os.path.join(d, "arduino", "mega2560", "mega2560.ino")))

    def test_ninguna_placa_repite_pin_ni_saca_por_un_pin_de_entrada(self):
        todas = list(placas.PIC.values()) + list(placas.ESP32.values()) + \
            list(placas.ARDUINO.values()) + [placas.BLUEPILL, placas.PICO, placas.EPM240]
        for ne in range(2, 7):
            for ns in range(1, 33):
                c = Circuito(tabla_al_azar(ne * 100 + ns, ne, ns))
                for placa in todas:
                    try:
                        renglones = asignar_pines(c, placa)
                    except Bloqueo:
                        continue
                    pines = [r["pin"] for r in renglones]
                    self.assertEqual(len(pines), len(set(pines)), placa["titulo"])
                    for r in renglones:
                        if r["direccion"] == "salida":
                            self.assertNotIn(r["pin"], placa.get("solo_entrada", []),
                                             placa["titulo"])

    def test_la_flash_del_esp32_nunca_se_toca(self):
        for pin in range(6, 12):
            self.assertNotIn(pin, placas.ESP32["esp32_wroom32"]["entradas"])
            self.assertNotIn(pin, placas.ESP32["esp32_wroom32"]["salidas"])

    def test_pines_del_usuario_en_varias_placas(self):
        tabla = TruthTable(2, outputs={"Y_AND": [0, 0, 0, 1], "Y_OR": [0, 1, 1, 1]})
        armado = kit.armar(tabla, pines={
            "max2": [26, 28, 81, 77],
            "uno_nano": leer_pines("2, 3, a0 13", placas.ARDUINO["uno_nano"]),
            "pic16f628a": leer_pines("ra0 ra1 rb5 rb4", placas.PIC["pic16f628a"]),
        })
        qsf = armado.archivos["fpga/circuito.qsf"]
        for linea in ("PIN_26 -to A", "PIN_28 -to B", "PIN_81 -to Y_AND", "PIN_77 -to Y_OR"):
            self.assertIn("set_location_assignment " + linea, qsf)
        uno = armado.archivos["arduino/uno_nano/uno_nano.ino"]
        self.assertIn("const uint8_t PIN_Y_AND = A0;", uno)
        self.assertIn("const uint8_t PIN_Y_OR = 13;", uno)
        pic = armado.archivos["pic/pic16f628a.c"]
        self.assertIn("if (PORTAbits.RA1) fila__ |= 0x01;   // B", pic)
        self.assertIn("PORTB = (uint8_t)((out_Y_AND << 5) | (out_Y_OR << 4));", pic)
        # las placas sin pines propios siguen con su reparto de siempre
        self.assertIn("PIN_A = 32;", armado.archivos["esp32/esp32_wroom32/esp32_wroom32.ino"])

    def test_pines_que_no_sirven_dicen_por_que(self):
        c = Circuito(TruthTable(2, outputs={"Y": [0, 1, 1, 0]}))
        max2, wroom = placas.EPM240, placas.ESP32["esp32_wroom32"]
        for placa, malos, motivo in ((max2, [26, 28, 9], "alimentacion"),   # VCCIO1
                                     (max2, [26, 28, 22], "JTAG"),          # TMS
                                     (max2, [26, 28, 12], "GCLK0"),
                                     (max2, [26, 26, 33], "repite"),
                                     (max2, [26, 28], "hacen falta 3"),
                                     (wroom, [32, 33, 7], "no es utilizable"),  # flash
                                     (wroom, [32, 33, 34], "solo sirve de entrada")):
            with self.assertRaises(ValueError) as e:
                con_pines(c, placa, malos)
            self.assertIn(motivo, str(e.exception), malos)
        with self.assertRaises(ValueError):
            leer_pines("26, veintiocho", max2)
        with self.assertRaises(ValueError):
            kit.armar(TruthTable(2, outputs={"Y": [0, 1, 1, 0]}), pines={"zx81": [1, 2, 3]})

    def test_el_documento_trae_el_kit(self):
        from ktool.render.report import Options, build_report
        tabla = TruthTable(2, outputs={"Y": [0, 1, 1, 0]})
        html = build_report(tabla, Options(kit=True, kit_pines={"max2": [26, 28, 33]}))
        self.assertIn("<h2>Kit de hardware</h2>", html)
        self.assertIn("Pines: Intel/Altera MAX II EPM240T100C5", html)
        self.assertIn("<code>fpga/circuito.vhd</code>", html)
        self.assertNotIn("<h2>Kit de hardware</h2>", build_report(tabla, Options()))

    def test_la_max_ii_solo_usa_io_de_usuario(self):
        no_io = {9, 10, 11, 12, 13, 14, 22, 23, 24, 25, 31, 32, 43, 44, 45, 46,
                 59, 60, 62, 63, 64, 65, 79, 80, 93, 94}
        usadas = set(placas.EPM240_BANCO_1) | set(placas.EPM240_BANCO_2)
        self.assertEqual(len(usadas), 74)
        self.assertEqual(usadas & no_io, set())
        self.assertEqual(usadas | no_io, set(range(1, 101)))

    def test_nombres_que_no_compilan(self):
        # 'I' chocaria con el contador del banco de prueba VHDL (no distingue
        # mayusculas); 'label' y 'next' son reservadas de VHDL; 'posedge' de Verilog
        for malo in ("or", "SIGNAL", "2Y", "Y__1", "I", "label", "Next", "posedge", "Circuito"):
            with self.assertRaises(ValueError):
                Circuito(TruthTable(2, outputs={malo: [0, 1, 1, 0]}))
        with self.assertRaises(ValueError):   # VHDL no distingue a de A
            Circuito(TruthTable(2, outputs={"a": [0, 1, 1, 0]}))


class GAL(unittest.TestCase):

    def test_cada_salida_cabe_en_su_macrocelda(self):
        for semilla in range(30):
            c = Circuito(tabla_al_azar(semilla, 5, 4))
            try:
                texto = logica.gal22v10(c)
            except Bloqueo:
                continue
            patas = dict(re.findall(r"PIN (\d+) = (\w+) ;  /\*", texto))
            patas = {s: int(p) for p, s in patas.items()}
            for s in c.salidas:
                cuerpo = re.search(rf"^!?{s} = (.*?);", texto, re.S | re.M).group(1)
                terminos = cuerpo.count("#") + 1
                self.assertLessEqual(terminos, placas.GAL22V10["terminos_por_pata"][patas[s]])

    def test_once_salidas_no_caben(self):
        with self.assertRaises(Bloqueo):
            logica.gal22v10(Circuito(tabla_al_azar(1, 3, 11)))


class Archivos(unittest.TestCase):
    """El kit completo, escrito en disco y ejecutado donde se puede."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.tabla = tabla_al_azar(42, 4, 3)
        cls.resumen = kit.generar(cls.tabla, cls.dir.name, "auto")
        cls.circuito = Circuito(cls.tabla)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def ruta(self, *partes):
        return os.path.join(self.dir.name, *partes)

    def test_todo_listo_en_un_circuito_chico(self):
        for plataforma, estado, detalle in self.resumen:
            self.assertEqual(estado, "listo", f"{plataforma}: {detalle}")

    def test_la_simulacion_en_python_pasa(self):
        r = subprocess.run([sys.executable, self.ruta("python", "simular.py")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_micropython_con_un_machine_de_mentira(self):
        for archivo in (("pico", "main.py"), ("esp32", "esp32_wroom32", "main.py"),
                        ("esp32", "esp32_s3", "main.py"), ("esp32", "esp32_c3", "main.py")):
            pines = {}

            class Pin:
                IN, OUT, PULL_DOWN = "in", "out", "pd"

                def __init__(self, numero, modo, pull=None):
                    self.numero, self.v = numero, 0
                    pines[numero] = self

                def value(self, v=None):
                    if v is None:
                        return self.v
                    self.v = v

            falso = types.ModuleType("machine")
            falso.Pin = Pin
            sys.modules["machine"] = falso
            try:
                entorno = {"__name__": "prueba"}
                with open(self.ruta(*archivo), encoding="utf-8") as f:
                    exec(compile(f.read(), "/".join(archivo), "exec"), entorno)
            finally:
                del sys.modules["machine"]

            def evaluar(i, entradas):
                for e, valor in entradas.items():
                    entorno[f"pin_{e}"].v = valor
                entorno["evaluar"]()
                return {s: entorno[f"pin_{s}"].v for s in self.circuito.salidas}

            revisar(self, self.circuito, evaluar, "/".join(archivo))

    def test_cada_archivo_trae_su_tabla_de_pines(self):
        for ruta in (("pic", "pic16f628a.c"), ("arduino", "uno_nano", "uno_nano.ino"),
                     ("stm32", "bluepill", "bluepill.ino"), ("fpga", "circuito.qsf")):
            with open(self.ruta(*ruta), encoding="utf-8") as f:
                texto = f.read()
            self.assertIn("Senal", texto, ruta)
            self.assertIn("Direccion", texto, ruta)

    def test_materiales_ttl(self):
        with open(self.ruta("ttl", "MATERIALES.md"), encoding="utf-8") as f:
            texto = f.read()
        self.assertRegex(texto, r"\| \d+ \| (74LS|CD)\d+ \|")
        self.assertIn("compuertas usadas de", texto)
        self.assertIn("## Conexiones pin a pin", texto)

    def test_la_cli_genera_el_kit(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, "-m", "ktool", "-e", "A'B + C", "--hw", d],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("PIC16F84A", r.stdout)
            self.assertTrue(os.path.exists(os.path.join(d, "LEEME.md")))


if __name__ == "__main__":
    unittest.main()
