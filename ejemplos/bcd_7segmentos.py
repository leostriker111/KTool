"""Decodificador de BCD a 7 segmentos, con su armado en protoboard.

Es el ejemplo grande de la funcion nueva: cuatro entradas, siete salidas que
comparten terminos, y los digitos 10 a 15 como don't care. Sale un documento
con las siete ecuaciones, sus mapas, el circuito combinado y el protoboard
armado --chips, cables y puentes-- con un display de catodo comun en la salida.

    python ejemplos/bcd_7segmentos.py

Para la version de anodo comun basta cambiar EXTREMOS a '7seg_ca': el segmento
enciende en BAJO, asi que ktool minimiza los ceros en vez de los unos.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ktool.core.table import TruthTable
from ktool.render import report

# que segmentos enciende cada digito
DIGITOS = {
    0: "abcdef", 1: "bc",     2: "abdeg",  3: "abcdg", 4: "bcfg",
    5: "acdfg",  6: "acdefg", 7: "abc",    8: "abcdefg", 9: "abcdfg",
}
SEGMENTOS = "abcdefg"
EXTREMOS = "7seg_cc"        # catodo comun: el segmento enciende con 1


def tabla():
    salidas = {}
    for seg in SEGMENTOS:
        # los digitos 10..15 no existen en BCD: don't care, y salen mas baratas
        salidas[seg] = ["x" if i > 9 else (1 if seg in DIGITOS[i] else 0)
                        for i in range(16)]
    return TruthTable(4, outputs=salidas)


def main():
    opciones = report.Options(
        title="Decodificador BCD a 7 segmentos",
        proto=True,
        proto_modo="automatico",
        proto_extremos=EXTREMOS,
    )
    html = report.build_report(tabla(), opciones)
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "bcd-7segmentos.html")
    report.save_report(html, destino)
    print("listo:", destino)


if __name__ == "__main__":
    main()
