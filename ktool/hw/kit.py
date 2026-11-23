"""El kit de hardware: una carpeta con el circuito listo para cada plataforma.

    ktool -e "A'B + C" --hw kit

genera, para el mismo circuito:

    LEEME.md                       resumen: que se genero y que se bloqueo y por que
    pic/<chip>.c                   PIC18F4550, PIC18F45K50, PIC16F877A, 16F628A, 16F84A
    esp32/<variante>/              .ino (Arduino-ESP32) y main.py (MicroPython)
    arduino/<placa>/<placa>.ino    Uno/Nano, o Mega si no cabe en el Uno
    stm32/bluepill/bluepill.ino    Blue Pill con STM32duino
    pico/main.py                   Raspberry Pi Pico en MicroPython
    fpga/                          VHDL, Verilog, dos bancos de prueba y el
                                   proyecto de Quartus para la MAX II EPM240
    gal/CIRCUITO.PLD               GAL22V10 en WinCUPL
    ttl/MATERIALES.md              chips 74LS, cuantos y cada cable
    python/simular.py              tabla de verdad de las ecuaciones, verificada

Solo circuitos combinacionales: las maquinas de estado (reloj y reset) llegan
con el Release 3 (docs/TODO.md).
"""

from __future__ import annotations

import os

from .. import __version__
from . import logica, micros, placas
from .modelo import Bloqueo, Circuito, asignar_pines

# Cada plataforma como (carpeta y archivo, titulo para el resumen). El orden es
# el del resumen.
PIC_CHIPS = ["pic18f4550", "pic18f45k50", "pic16f877a", "pic16f628a", "pic16f84a"]
ESP32_VARIANTES = ["esp32_wroom32", "esp32_s3", "esp32_c3"]


def generar(tabla, carpeta, forma="auto"):
    """Escribe el kit en `carpeta` y devuelve el resumen como lista de
    (plataforma, estado, detalle). `estado` es 'listo' o 'bloqueado'."""
    circuito = Circuito(tabla, forma)
    archivos = {}   # ruta relativa -> texto
    resumen = []

    def listo(plataforma, *rutas):
        resumen.append((plataforma, "listo", ", ".join(rutas)))

    def bloqueado(plataforma, motivo):
        resumen.append((plataforma, "bloqueado", f"Variante bloqueada: {motivo}"))

    # --- PIC
    for chip in PIC_CHIPS:
        info = placas.PIC[chip]
        try:
            renglones = asignar_pines(circuito, info)
        except Bloqueo as b:
            bloqueado(info["titulo"], str(b))
            continue
        palabras, terminos = micros.palabras_estimadas(circuito)
        if palabras > info["palabras"]:
            bloqueado(info["titulo"],
                      f"el programa necesitaria unas {palabras} palabras ({terminos} "
                      f"terminos) y el {info['titulo']} tiene {info['palabras']}; "
                      "usa uno con mas memoria")
            continue
        ruta = f"pic/{chip}.c"
        archivos[ruta] = micros.pic(circuito, chip, renglones)
        listo(info["titulo"], ruta)

    # --- ESP32: el mismo reparto para Arduino y MicroPython
    for variante in ESP32_VARIANTES:
        info = placas.ESP32[variante]
        try:
            renglones = asignar_pines(circuito, info)
        except Bloqueo as b:
            bloqueado(info["titulo"], str(b))
            continue
        ino = f"esp32/{variante}/{variante}.ino"
        py = f"esp32/{variante}/main.py"
        archivos[ino] = micros.esp32_arduino(circuito, variante, renglones)
        archivos[py] = micros.esp32_micropython(circuito, variante, renglones)
        listo(info["titulo"], ino, py)

    # --- Arduino: el Uno si cabe; si no, el Mega
    try:
        renglones = asignar_pines(circuito, placas.ARDUINO["uno_nano"])
        ruta = "arduino/uno_nano/uno_nano.ino"
        archivos[ruta] = micros.avr(circuito, "uno_nano", renglones)
        listo(placas.ARDUINO["uno_nano"]["titulo"], ruta)
    except Bloqueo as b:
        bloqueado(placas.ARDUINO["uno_nano"]["titulo"], f"{b}; se genera para el Mega")
        try:
            renglones = asignar_pines(circuito, placas.ARDUINO["mega2560"])
            ruta = "arduino/mega2560/mega2560.ino"
            archivos[ruta] = micros.avr(circuito, "mega2560", renglones)
            listo(placas.ARDUINO["mega2560"]["titulo"], ruta)
        except Bloqueo as b2:
            bloqueado(placas.ARDUINO["mega2560"]["titulo"], str(b2))

    # --- Blue Pill
    try:
        renglones = asignar_pines(circuito, placas.BLUEPILL)
        ruta = "stm32/bluepill/bluepill.ino"
        archivos[ruta] = micros.bluepill(circuito, renglones)
        listo(placas.BLUEPILL["titulo"], ruta)
    except Bloqueo as b:
        bloqueado(placas.BLUEPILL["titulo"], str(b))

    # --- Pico
    try:
        renglones = asignar_pines(circuito, placas.PICO)
        archivos["pico/main.py"] = micros.pico(circuito, renglones)
        listo(placas.PICO["titulo"], "pico/main.py")
    except Bloqueo as b:
        bloqueado(placas.PICO["titulo"], str(b))

    # --- HDL: no depende de pines, siempre sale
    n = circuito.nombre
    archivos[f"fpga/{n}.vhd"] = logica.vhdl(circuito)
    archivos[f"fpga/{n}.v"] = logica.verilog(circuito)
    archivos[f"fpga/tb_{n}.vhd"] = logica.vhdl_testbench(circuito)
    archivos[f"fpga/tb_{n}.v"] = logica.verilog_testbench(circuito)
    listo("VHDL y Verilog (con bancos de prueba)", f"fpga/{n}.vhd", f"fpga/{n}.v",
          f"fpga/tb_{n}.vhd", f"fpga/tb_{n}.v")
    try:
        renglones = asignar_pines(circuito, placas.EPM240)
        # Con los topes de ktool (6 entradas, 32 salidas) son a lo mas 160 de
        # 240 celdas: hoy nunca se bloquea por tamano. Se revisa igual, por si
        # algun dia suben los topes.
        if logica.celdas_max_ii(circuito) > 240:
            raise Bloqueo(f"pide hasta {logica.celdas_max_ii(circuito)} celdas logicas y "
                          "la EPM240 tiene 240")
        archivos[f"fpga/{n}.qsf"] = logica.qsf(circuito, renglones)
        archivos[f"fpga/{n}.qpf"] = logica.qpf(circuito)
        listo(placas.EPM240["titulo"], f"fpga/{n}.qpf", f"fpga/{n}.qsf")
    except Bloqueo as b:
        bloqueado(placas.EPM240["titulo"], str(b))

    # --- GAL22V10
    try:
        archivos["gal/CIRCUITO.PLD"] = logica.gal22v10(circuito)
        listo(placas.GAL22V10["titulo"], "gal/CIRCUITO.PLD")
    except Bloqueo as b:
        bloqueado(placas.GAL22V10["titulo"], str(b))

    # --- TTL
    try:
        archivos["ttl/MATERIALES.md"] = logica.ttl(circuito)
        listo("Logica discreta 74LS", "ttl/MATERIALES.md")
    except Bloqueo as b:
        bloqueado("Logica discreta 74LS", str(b))

    # --- Python
    archivos["python/simular.py"] = logica.simulacion_python(circuito)
    listo("Simulacion en Python", "python/simular.py")

    archivos["LEEME.md"] = _leeme(circuito, resumen)

    for ruta, texto in archivos.items():
        destino = os.path.join(carpeta, *ruta.split("/"))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        # newline="\n": los mismos bytes en Windows y en Linux
        with open(destino, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    return resumen


def _leeme(circuito, resumen):
    ne, ns = circuito.n_entradas, circuito.n_salidas
    lineas = [f"""\
# Kit de hardware: {circuito.nombre}

Generado por ktool {__version__}. Circuito **combinacional** con {ne} entradas
({', '.join(circuito.entradas)}) y {ns} salida(s) ({', '.join(circuito.salidas)}):
{ne + ns} pines en total. Cada microcontrolador lo evalua en un ciclo sin fin;
el HDL lo describe con asignaciones concurrentes.

## Ecuaciones
"""]
    for s in circuito.salidas:
        sol = circuito.elegidas[s]
        lineas.append(f"- `{s} = {sol.equation}` ({sol.form.upper()})")
    lineas.append("\n## Que se genero\n")
    lineas.append("| Plataforma | Estado | Archivos o motivo |")
    lineas.append("|---|---|---|")
    for plataforma, estado, detalle in resumen:
        lineas.append(f"| {plataforma} | {estado} | {detalle} |")
    lineas.append("""
Cada archivo trae arriba su tabla de pines (senal -> pin fisico). Si un pin
lleva nota, es porque se uso uno de reserva: leela antes de conectar.

## Antes de grabar

1. Corre `python python/simular.py`: imprime la tabla de verdad de las
   ecuaciones y la compara con la original.
2. Para el HDL, los bancos de prueba recorren todas las combinaciones:
   `ghdl -a circuito.vhd tb_circuito.vhd && ghdl -r tb_circuito`, o
   `iverilog -o tb tb_circuito.v circuito.v && vvp tb`.
3. Las entradas necesitan pull-down (interna donde la placa la tiene, si no
   una resistencia de 10 kOhm a GND), o leen basura con el interruptor abierto.

Las maquinas de estado (reloj y reset) todavia no: llegan con el Release 3.
""")
    return "\n".join(lineas)
