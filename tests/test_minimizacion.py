"""El motor: que la respuesta sea correcta, minima, y que no se atore."""

import itertools
import random
import time
import unittest

from ktool.core import qm
from ktool.core.simplify import solve_output

VARIABLES = ["A", "B", "C", "D", "E", "F"]

# Las tres tablas de 6 variables del issue #2. Con Petrick tardaban
# 18 s, 2 s y 27 s (una cuarta paso de 100 s y se corto la medicion).
TABLAS_LENTAS = [
    "10010x00x011x1x1x1100x10001xx11111001x1010xxx1x110x0100101010xxx",
    "xx0011x00xx010x11x1x1x10110110x1x00x1x0x00111x10x00100x1xx1xxx00",
    "11x10x11xxxx1x000xx10x011x1x10xxx1x00xxx100110xx01x1xx11x0xx0x01",
]


def vector(texto):
    return [int(c) if c in "01" else "x" for c in texto]


def vale_sop(patrones, i, n):
    bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
    for p in patrones:
        if all(c == "-" or int(c) == bits[k] for k, c in enumerate(p)):
            return 1
    return 0


def vale_pos(patrones, i, n):
    bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
    for p in patrones:
        if all(c == "-" or int(c) == bits[k] for k, c in enumerate(p)):
            return 0
    return 1


def costo(patrones):
    return (len(patrones), sum(qm.literal_count(p) for p in patrones))


def optimo_por_fuerza_bruta(minterminos, dontcares, n):
    """El costo minimo real, probando todos los subconjuntos de primos."""
    primos = list(qm.prime_implicants(set(minterminos) | set(dontcares), n))
    obligatorios = set(minterminos)
    mejor = None
    for k in range(1, len(primos) + 1):
        if mejor is not None and k > mejor[0]:
            break
        for combo in itertools.combinations(primos, k):
            cubierto = set()
            for p in combo:
                cubierto |= qm.pattern_minterms(p)
            if obligatorios <= cubierto:
                c = costo(combo)
                if mejor is None or c < mejor:
                    mejor = c
    return mejor


class CasosConocidos(unittest.TestCase):
    def test_ejemplo_del_leeme(self):
        # ktool -n 3 -m 1,4,5,6 -d 2,7  ->  minterminos 1,4,5,6 y don't cares 2,7
        r = solve_output(vector("01x0111x"), VARIABLES[:3])
        self.assertEqual(r["sop"].equation, "B'C + A")

    def test_sin_dont_cares_la_respuesta_cambia(self):
        # la misma tabla pero con 2 y 7 en cero: ya hacen falta dos literales mas
        r = solve_output(vector("01001110"), VARIABLES[:3])
        self.assertEqual(r["sop"].equation, "B'C + AC'")

    def test_paridad_de_dos_variables_gana_el_xor(self):
        # B ^ D sobre 4 variables: SOP y POS cuestan 3 compuertas, el XOR 1
        vals = [(b ^ d) for a in (0, 1) for b in (0, 1) for c in (0, 1) for d in (0, 1)]
        r = solve_output(vals, VARIABLES[:4])
        self.assertEqual(r["best"].form, "xor")
        self.assertEqual(r["best"].equation, "B ^ D")

    def test_constante_cero(self):
        r = solve_output([0] * 8, VARIABLES[:3])
        self.assertEqual(r["sop"].equation, "0")

    def test_constante_uno(self):
        r = solve_output([1] * 8, VARIABLES[:3])
        self.assertEqual(r["sop"].equation, "1")

    def test_los_dont_cares_se_aprovechan(self):
        # sin el don't care en 3 harian falta dos terminos; con el, uno solo
        sin_dc = solve_output(vector("00110010"), VARIABLES[:3])
        con_dc = solve_output(vector("0011001x"), VARIABLES[:3])
        self.assertLess(con_dc["sop"].cost(), sin_dc["sop"].cost())


class Exactitud(unittest.TestCase):
    """Cada solucion se re-evalua contra la tabla que la origino."""

    def _revisar(self, vals, n):
        variables = VARIABLES[:n]
        r = solve_output(vals, variables)
        for forma in ("sop", "pos", "xor"):
            s = r[forma]
            if s is None:
                continue
            for i, v in enumerate(vals):
                if v == "x":
                    continue
                if s.const is not None:
                    dio = s.const
                elif forma == "sop":
                    dio = vale_sop(s.patterns, i, n)
                elif forma == "pos":
                    dio = vale_pos(s.patterns, i, n)
                else:
                    bits = {x: (i >> (n - 1 - k)) & 1 for k, x in enumerate(variables)}
                    dio = 0
                    for x in s.xor_vars:
                        dio ^= bits[x]
                    if s.xnor:
                        dio ^= 1
                self.assertEqual(dio, v, f"{forma} falla en la fila {i} de {vals}")

    def test_todas_las_tablas_de_dos_y_tres_variables(self):
        """Exhaustivo con don't cares: 3^4 + 3^8 = 6,642 tablas."""
        for n in (2, 3):
            for vals in itertools.product([0, 1, "x"], repeat=1 << n):
                self._revisar(list(vals), n)

    def test_tablas_al_azar_de_cuatro_y_cinco(self):
        random.seed(20)
        for n in (4, 5):
            for _ in range(300):
                self._revisar([random.choice([0, 1, "x"]) for _ in range(1 << n)], n)


class Minimalidad(unittest.TestCase):
    """No basta con cubrir: tiene que ser la cobertura mas barata que existe."""

    def test_coincide_con_la_fuerza_bruta(self):
        random.seed(21)
        casos = 0
        for n in (2, 3, 4):
            for _ in range(120):
                vals = [random.choice([0, 1, "x"]) for _ in range(1 << n)]
                mins = [i for i, v in enumerate(vals) if v == 1]
                dcs = [i for i, v in enumerate(vals) if v == "x"]
                if not mins:
                    continue
                casos += 1
                elegido = qm.minimize(mins, dcs, n, required=mins)
                self.assertEqual(costo(elegido), optimo_por_fuerza_bruta(mins, dcs, n),
                                 f"no es minimo para {vals}")
        self.assertGreater(casos, 200)


class NoSeAtora(unittest.TestCase):
    """Regresion del issue #2: con Petrick estas tablas tardaban de 2 a 100+ s."""

    def test_las_tablas_lentas_salen_rapido(self):
        for texto in TABLAS_LENTAS:
            t0 = time.time()
            r = solve_output(vector(texto), VARIABLES)
            tardo = time.time() - t0
            self.assertLess(tardo, 5.0, f"tardo {tardo:.1f}s con {texto}")
            # y ademas es correcta
            for i, v in enumerate(vector(texto)):
                if v != "x":
                    self.assertEqual(vale_sop(r["sop"].patterns, i, 6), v)

    def test_barrido_de_seis_variables(self):
        random.seed(22)
        t0 = time.time()
        for _ in range(25):
            solve_output([random.choice([0, 1, "x"]) for _ in range(64)], VARIABLES)
        self.assertLess(time.time() - t0, 10.0)


class Reduccion(unittest.TestCase):
    """Las piezas que evitan ramificar."""

    def test_los_esenciales_entran_siempre(self):
        # el mintermino 0 solo lo cubre un primo -> es esencial
        elegido = qm.minimize([0, 5, 7], [], 3, required=[0, 5, 7])
        self.assertIn("000", elegido)

    def test_funcion_ciclica_clasica(self):
        # sin esenciales: todo mintermino lo cubren dos primos. Se resuelve
        # por dominancia/ramificacion y la respuesta minima son 3 terminos.
        mins = [0, 1, 2, 5, 6, 7]
        elegido = qm.minimize(mins, [], 3, required=mins)
        self.assertEqual(len(elegido), 3)
        for i in range(8):
            self.assertEqual(vale_sop(elegido, i, 3), 1 if i in mins else 0)

    def test_cobertura_vacia(self):
        self.assertEqual(qm.cover({"000"}, set()), set())


if __name__ == "__main__":
    unittest.main()
