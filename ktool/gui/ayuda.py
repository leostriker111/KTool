"""Los textos del menu Ayuda: guia rapida, guias por tema y Acerca de.

Solo texto: la ventana los muestra con su `_text_window`. Viven aparte para que
app.py sea la ventana y no un libro.
"""

from __future__ import annotations

from .. import __version__
from ..core.table import MAX_OUTPUTS, MAX_VARS, MIN_VARS

REPO_URL = "https://github.com/leostriker111/KTool"

GUIA_RAPIDA = (
    "ktool simplifica logica digital y la lleva al hardware.\n\n"
    f"1. Arriba eliges cuantas entradas ({MIN_VARS}-{MAX_VARS}) y salidas (1-{MAX_OUTPUTS}),\n"
    "   y le das Aplicar.\n"
    "2. Llenas la tabla: doble clic cicla 0 -> 1 -> x, o seleccionas varias\n"
    "   celdas y presionas 1, 0 o x. Tambien puedes escribir una expresion\n"
    "   y darle 'Evaluar y llenar'.\n"
    "3. Clic en el encabezado de una entrada o salida para cambiarle el\n"
    "   nombre (SEL, D0, EN...). El cambio llega a todo: ecuaciones,\n"
    "   documento, armado y codigo.\n"
    "4. 'Forma' decide la realizacion para todo lo de abajo.\n"
    "5. Abajo, en Resultados: Ecuaciones, Portada (los datos del reporte),\n"
    "   Generar (palomeas lo que quieres y sale todo de un clic), Protoboard\n"
    "   y Kit de hardware.\n"
    "6. Archivo guarda y abre proyectos (.ktool.json) y trae ejemplos listos.\n\n"
    "Las guias de Ayuda > Guias explican cada parte con calma."
)

GUIAS = {
    "Llenar la tabla": (
        "LLENAR LA TABLA\n\n"
        "Cada fila es una combinacion de las entradas; la primera entrada es el\n"
        "bit mas alto, asi que la fila 5 con A B C es A=1 B=0 C=1.\n\n"
        "- Doble clic en una celda: 0 -> 1 -> x (x = no importa).\n"
        "- Arrastra para escoger un rango, Shift + clic para agregar; luego\n"
        "  1, 0 o x cambia todas las escogidas.\n"
        "- Ctrl+C / Ctrl+V copian y pegan en formato de Excel.\n"
        "- La barra Expresion llena una columna completa:\n"
        "    A'B + C        con letras sueltas, pegar dos letras es AND\n"
        "    SEL' D0 + SEL D1   con nombres largos, separados por espacio\n"
        "    b1011, h4D, d77    un numero: sus bits van de la fila 0 hacia abajo\n"
        "- 'x' (no importa) deja que el minimizador escoja 0 o 1 para ahorrar."
    ),
    "Formas y costos": (
        "FORMAS Y COSTOS\n\n"
        "- SOP: suma de productos (AND y luego OR).\n"
        "- POS: producto de sumas (OR y luego AND).\n"
        "- Solo NAND / solo NOR: la misma funcion con un solo tipo de compuerta.\n"
        "  En el papel casi nunca gana; en la protoboard puede ahorrar chips.\n"
        "- XOR/XNOR: cuando la funcion es una paridad, sale mucho mas barata.\n"
        "- auto: la mas barata en compuertas y luego en literales.\n"
        "- both: el documento pone SOP y POS lado a lado.\n\n"
        "La pestana Ecuaciones muestra todas con su costo (compuertas, literales)."
    ),
    "Portada y Generar": (
        "PORTADA Y GENERAR\n\n"
        "Portada: titulo, autor, organizacion, materia, profesor, secuencia,\n"
        "fecha, reviso y autorizo. Lo que llenes sale al inicio del documento,\n"
        "con lineas de firma para quien revisa y quien autoriza. Lo vacio no\n"
        "aparece.\n\n"
        "Generar: palomeas que contiene el documento (portada, tabla, mapas,\n"
        "circuitos, lenguajes, armado, kit) y que mas se guarda en la carpeta\n"
        "(el armado aparte, la carpeta del kit, el proyecto para reabrirlo).\n"
        "Un clic en 'Generar todo' y sale todo en la carpeta que digas."
    ),
    "Protoboard": (
        "ARMADO EN PROTOBOARD (beta)\n\n"
        "De las ecuaciones a chips 74xx en una protoboard, con cada cable.\n\n"
        "- Chips: fiel al diagrama, solo los que tengo (escribes cuales), o\n"
        "  automatico (el ancho mayor que use el circuito).\n"
        "- En las salidas: puntos, LEDs o displays de 7 y 16 segmentos.\n"
        "- Una protoboard por salida, si prefieres probarlas por separado.\n\n"
        "La lista de cables se comprueba contra la tabla de verdad; el armado\n"
        "fisico todavia no se prueba en una mesa real."
    ),
    "Kit de hardware y pines": (
        "KIT DE HARDWARE\n\n"
        "El circuito como codigo para PIC (18F4550, 18F45K50, 16F877A, 16F628A,\n"
        "16F84A), ESP32, Arduino, Blue Pill, Pico, VHDL/Verilog, la MAX II, la\n"
        "GAL22V10 y chips 74LS, con la tabla de pines al inicio de cada archivo.\n\n"
        "Si una placa no alcanza (pines, memoria, macroceldas) lo dice con la\n"
        "cuenta en vez de escribir codigo roto.\n\n"
        "Pines fijos: si tu placa trae LEDs o botones en pines fijos, escoge la\n"
        "placa y escribe sus pines: primero las entradas y luego las salidas,\n"
        "en el orden que te indica la pestana. Cada placa recuerda los suyos.\n"
        "Un pin de alimentacion, tierra, JTAG o de la flash se rechaza con el\n"
        "motivo."
    ),
    "Proyectos y ejemplos": (
        "PROYECTOS Y EJEMPLOS\n\n"
        "Archivo > Guardar guarda TODO en un .ktool.json: la tabla, los nombres,\n"
        "la portada y las opciones de cada pestana. Archivo > Abrir lo recupera\n"
        "tal cual.\n\n"
        "Mientras trabajas, ktool guarda una copia cada pocos segundos. Si cierras\n"
        "sin guardar o empiezas otro, lo anterior va a la papelera de ktool:\n"
        "Archivo > Recuperar trabajo anterior lo abre.\n\n"
        "Archivo > Ejemplos trae circuitos listos (multiplexor, decodificadores,\n"
        "sumadores, restadores, comparador, convertidores Gray / BCD / exceso-3,\n"
        "complemento a 2 y los de las practicas) para estudiarlos o modificarlos."
    ),
}


def acerca_de():
    return (
        f"ktool {__version__}\n\n"
        "Simplificador de logica digital: tabla de verdad, mapas de Karnaugh,\n"
        "SOP/POS/XOR/NAND/NOR exactos por Quine-McCluskey, circuito, armado en\n"
        "protoboard y codigo para cada placa.\n\n"
        "Python puro, sin dependencias.\n"
        "Licencia MIT.\n"
        f"Codigo: {REPO_URL}"
    )
