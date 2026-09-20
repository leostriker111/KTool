"""Catalogo de circuitos integrados: pinouts verificados contra hoja de datos.

**Cada pinout de aqui se leyo de su datasheet, no de memoria.** Un pin
equivocado le cuesta la practica a quien siga el diagrama, asi que cada entrada
trae `fuente` (de donde salio) y `lectura` (como se comprobo). Las que se
leyeron de dos documentos independientes que coinciden lo dicen.

La estructura de compuertas **no se escribe a mano**: se deduce de los nombres
de los pines, que son los verificados. `1A`, `1B`, `1Y` son la compuerta 1 con
entradas A y B y salida Y. Asi no hay una segunda copia del dato que se pueda
desincronizar.

Para agregar un chip: una entrada mas en CHIPS con su pinout y su fuente. No hay
codigo que tocar, ni un dibujo que hacer -- el encapsulado se calcula (ver dip.py).
"""

from __future__ import annotations

import re

# tipos de compuerta que sabemos armar
AND, OR, NAND, NOR, XOR, XNOR, NOT = "and", "or", "nand", "nor", "xor", "xnor", "not"

# El complemento de cada tipo, para las realizaciones universales.
NEGADA = {AND: NAND, OR: NOR, NAND: AND, NOR: OR, XOR: XNOR, XNOR: XOR}

TI = "https://www.ti.com/lit/ds/symlink/"


CHIPS = {
    "7400": {
        "descripcion": "cuatro NAND de 2 entradas",
        "tipo": NAND, "entradas": 2, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "1Y", 4: "2A", 5: "2B", 6: "2Y", 7: "GND",
                   8: "3Y", 9: "3A", 10: "3B", 11: "4Y", 12: "4A", 13: "4B", 14: "VCC"},
        "fuente": TI + "sn7400.pdf",
        "lectura": "dibujo y tabla del datasheet coinciden; confirmado ademas con sn74hc00",
    },
    "7402": {
        "descripcion": "cuatro NOR de 2 entradas",
        "tipo": NOR, "entradas": 2, "pines": 14,
        "pinout": {1: "1Y", 2: "1A", 3: "1B", 4: "2Y", 5: "2A", 6: "2B", 7: "GND",
                   8: "3A", 9: "3B", 10: "3Y", 11: "4A", 12: "4B", 13: "4Y", 14: "VCC"},
        "fuente": TI + "sn74hc02.pdf",
        "lectura": "dibujo del datasheet (ojo: las salidas van primero, al reves del 7400)",
    },
    "7404": {
        "descripcion": "seis inversores",
        "tipo": NOT, "entradas": 1, "pines": 14,
        "pinout": {1: "1A", 2: "1Y", 3: "2A", 4: "2Y", 5: "3A", 6: "3Y", 7: "GND",
                   8: "4Y", 9: "4A", 10: "5Y", 11: "5A", 12: "6Y", 13: "6A", 14: "VCC"},
        "fuente": TI + "sn7404.pdf",
        "lectura": "dibujo del datasheet",
    },
    "7408": {
        "descripcion": "cuatro AND de 2 entradas",
        "tipo": AND, "entradas": 2, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "1Y", 4: "2A", 5: "2B", 6: "2Y", 7: "GND",
                   8: "3Y", 9: "3A", 10: "3B", 11: "4Y", 12: "4A", 13: "4B", 14: "VCC"},
        "fuente": TI + "sn74hc08.pdf",
        "lectura": "dibujo del datasheet",
    },
    "7410": {
        "descripcion": "tres NAND de 3 entradas",
        "tipo": NAND, "entradas": 3, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "2A", 4: "2B", 5: "2C", 6: "2Y", 7: "GND",
                   8: "3Y", 9: "3A", 10: "3B", 11: "3C", 12: "1Y", 13: "1C", 14: "VCC"},
        "fuente": TI + "sn74hc10.pdf",
        "lectura": "dibujo del datasheet",
    },
    "7411": {
        "descripcion": "tres AND de 3 entradas",
        "tipo": AND, "entradas": 3, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "2A", 4: "2B", 5: "2C", 6: "2Y", 7: "GND",
                   8: "3Y", 9: "3A", 10: "3B", 11: "3C", 12: "1Y", 13: "1C", 14: "VCC"},
        "fuente": TI + "sn74hc11.pdf",
        "lectura": "dibujo del datasheet",
    },
    "7420": {
        "descripcion": "dos NAND de 4 entradas",
        "tipo": NAND, "entradas": 4, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "NC", 4: "1C", 5: "1D", 6: "1Y", 7: "GND",
                   8: "2Y", 9: "2A", 10: "2B", 11: "NC", 12: "2C", 13: "2D", 14: "VCC"},
        "fuente": TI + "sn74hc20.pdf",
        "lectura": "dibujo del datasheet",
    },
    "7421": {
        "descripcion": "dos AND de 4 entradas",
        "tipo": AND, "entradas": 4, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "NC", 4: "1C", 5: "1D", 6: "1Y", 7: "GND",
                   8: "2Y", 9: "2A", 10: "2B", 11: "NC", 12: "2C", 13: "2D", 14: "VCC"},
        "fuente": TI + "sn74hc21.pdf",
        "lectura": "dibujo del datasheet",
    },
    "7427": {
        "descripcion": "tres NOR de 3 entradas",
        "tipo": NOR, "entradas": 3, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "2A", 4: "2B", 5: "2C", 6: "2Y", 7: "GND",
                   8: "3Y", 9: "3A", 10: "3B", 11: "3C", 12: "1Y", 13: "1C", 14: "VCC"},
        "fuente": TI + "sn74hc27.pdf",
        "lectura": "dibujo del datasheet",
    },
    "7432": {
        "descripcion": "cuatro OR de 2 entradas",
        "tipo": OR, "entradas": 2, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "1Y", 4: "2A", 5: "2B", 6: "2Y", 7: "GND",
                   8: "3Y", 9: "3A", 10: "3B", 11: "4Y", 12: "4A", 13: "4B", 14: "VCC"},
        "fuente": TI + "sn74hc32.pdf",
        "lectura": "dibujo del datasheet",
    },
    "7486": {
        "descripcion": "cuatro XOR de 2 entradas",
        "tipo": XOR, "entradas": 2, "pines": 14,
        "pinout": {1: "1A", 2: "1B", 3: "1Y", 4: "2A", 5: "2B", 6: "2Y", 7: "GND",
                   8: "3Y", 9: "3A", 10: "3B", 11: "4Y", 12: "4A", 13: "4B", 14: "VCC"},
        "fuente": TI + "sn74ahc86.pdf",
        "lectura": "tabla de dos datasheets independientes que coinciden (sn74ahc86 y sn74lvc86a)",
    },
    "4075": {
        "descripcion": "tres OR de 3 entradas",
        "tipo": OR, "entradas": 3, "pines": 14,
        "pinout": {1: "2A", 2: "2B", 3: "1A", 4: "1B", 5: "1C", 6: "1Y", 7: "GND",
                   8: "2C", 9: "2Y", 10: "3Y", 11: "3A", 12: "3B", 13: "3C", 14: "VCC"},
        "fuente": TI + "cd74hc4075.pdf",
        "lectura": "dibujo del datasheet. Tapa el hueco de la serie 74xx, que no "
                   "trae OR de 3 entradas; ojo que su pinout no sigue el patron",
    },
}


# --------------------------------------------------------------- estructura

_PIN = re.compile(r"^(\d+)([A-Z])$")


def compuertas(nombre):
    """Las compuertas del chip, deducidas de los nombres de sus pines.

    Devuelve [{'indice': 1, 'entradas': [pines], 'salida': pin}, ...] en orden.
    Las entradas van como conjunto ordenado por pin: en una compuerta simetrica
    da igual cual es la A y cual la B, y asi no importa que dos datasheets las
    etiqueten al reves.
    """
    chip = CHIPS[nombre]
    juntas = {}
    for pin, senal in chip["pinout"].items():
        m = _PIN.match(senal)
        if not m:
            continue                      # VCC, GND, NC
        indice, letra = int(m.group(1)), m.group(2)
        juntas.setdefault(indice, {"indice": indice, "entradas": [], "salida": None})
        if letra == "Y":
            juntas[indice]["salida"] = pin
        else:
            juntas[indice]["entradas"].append(pin)
    salida = []
    for indice in sorted(juntas):
        g = juntas[indice]
        g["entradas"].sort()
        salida.append(g)
    return salida


def alimentacion(nombre):
    """(pin de VCC, pin de GND)."""
    pinout = CHIPS[nombre]["pinout"]
    vcc = next(p for p, s in pinout.items() if s == "VCC")
    gnd = next(p for p, s in pinout.items() if s == "GND")
    return vcc, gnd


def por_tipo(tipo, entradas=None):
    """Los chips que dan esa compuerta, del mas angosto al mas ancho."""
    salida = [n for n, c in CHIPS.items()
              if c["tipo"] == tipo and (entradas is None or c["entradas"] == entradas)]
    return sorted(salida, key=lambda n: (CHIPS[n]["entradas"], n))


def anchos(tipo):
    """Anchos de compuerta disponibles para un tipo, de menor a mayor."""
    return sorted({CHIPS[n]["entradas"] for n in CHIPS if CHIPS[n]["tipo"] == tipo})
