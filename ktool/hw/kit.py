"""El kit de hardware: el circuito listo para cada plataforma.

    ktool -e "A'B + C" --hw kit

arma, para el mismo circuito:

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

Dos pasos separados: `armar` produce los archivos en memoria (asi el documento
HTML los puede incluir sin tocar el disco) y `escribir` los guarda en una
carpeta. `generar` hace los dos, que es lo que pide `--hw`.

Solo circuitos combinacionales: las maquinas de estado (reloj y reset) llegan
con el Release 3 (docs/TODO.md).
"""

from __future__ import annotations

import os

from .. import __version__
from . import ajustes, asm, logica, micros, placas
from .modelo import Bloqueo, Circuito, asignar_pines, con_pines

PIC_CHIPS = ["pic18f4550", "pic18f45k50", "pic16f877a", "pic16f628a", "pic16f84a"]
ESP32_VARIANTES = ["esp32_wroom32", "esp32_s3", "esp32_c3"]


class Kit:
    """Lo que sale de `armar`.

    circuito  el Circuito resuelto
    archivos  {ruta relativa: texto}, en el orden del resumen
    resumen   [(plataforma, 'listo' | 'bloqueado', archivos o motivo)]
    pines     {plataforma: renglones de asignar_pines} de las que salieron
    """

    def __init__(self, circuito):
        self.circuito = circuito
        self.archivos = {}
        self.resumen = []
        self.pines = {}
        self.editados = set()   # rutas que el usuario corrigio a mano
        self.archivos_de = {}   # {plataforma: [rutas]}: lo que muestra la vista previa

    def listo(self, plataforma, *rutas):
        self.resumen.append((plataforma, "listo", ", ".join(rutas)))
        self.archivos_de[plataforma] = list(rutas)

    def bloqueado(self, plataforma, motivo):
        self.resumen.append((plataforma, "bloqueado", f"Variante bloqueada: {motivo}"))


# Todo lo que el kit sabe generar, en el orden del resumen. Las placas con
# pines son las de placas.PLACAS_CON_PINES; las otras cuatro no tienen pines
# que elegir.
PLATAFORMAS = [(nombre, info["titulo"]) for nombre, info in placas.PLACAS_CON_PINES.items()] + [
    ("hdl", "VHDL y Verilog (con bancos de prueba)"),
    ("gal22v10", placas.GAL22V10["titulo"]),
    ("ttl", "Logica discreta 74LS"),
    ("python", "Simulacion en Python"),
]
TITULO_PLATAFORMA = dict(PLATAFORMAS)


def pines_en_orden(circuito, placa, mapa):
    """{senal: pin} del planificador -> la lista en el orden de con_pines.

    El planificador deja asignar solo algunas senales; las que quedan sin pata
    toman la siguiente libre de la lista de placas.py (entradas de la lista de
    entradas, salidas de la de salidas, nunca una pata solo-entrada). Si no
    alcanza, ValueError con la cuenta.
    """
    senales = circuito.entradas + circuito.salidas
    mapa = {s: p for s, p in mapa.items() if s in senales}   # quita senales viejas
    usados = set(mapa.values())
    solo_entrada = set(placa.get("solo_entrada", []))
    pines = []
    for senal in circuito.entradas + circuito.salidas:
        if senal in mapa:
            pines.append(mapa[senal])
            continue
        es_entrada = senal in circuito.entradas
        candidatos = placa["entradas"] if es_entrada else placa["salidas"]
        libre = next((p for p in candidatos if p not in usados
                      and (es_entrada or p not in solo_entrada)), None)
        if libre is None:
            raise ValueError(f"{placa['titulo']}: no queda pata libre para {senal}")
        usados.add(libre)
        pines.append(libre)
    return pines


def _placa(nombre, pines_usuario, circuito):
    """La placa de placas.PLACAS_CON_PINES, con los pines del usuario si los dio.

    Los pines llegan como lista (la CLI: --pines max2=26,28,33) o como
    {senal: pin} (el planificador de la ventana)."""
    base = placas.PLACAS_CON_PINES[nombre]
    if nombre in pines_usuario:
        elegidos = pines_usuario[nombre]
        if isinstance(elegidos, dict):
            elegidos = pines_en_orden(circuito, base, elegidos)
        return con_pines(circuito, base, elegidos)
    return base


def validar_nombres_de_placa(pines_usuario):
    """Un nombre de placa equivocado en --pines es un error, no algo que se ignora."""
    for nombre in pines_usuario:
        if nombre not in placas.PLACAS_CON_PINES:
            raise ValueError(
                f"no conozco la placa {nombre!r}. Las que aceptan pines propios: "
                + ", ".join(placas.PLACAS_CON_PINES))


def armar(tabla, forma="auto", pines=None, elegidas=None, ajustes_por_placa=None,
          editados=None):
    """Arma el kit en memoria y lo devuelve como Kit.

    `pines`: {nombre de placa: [pines] o {senal: pin}} opcional, con los nombres
    de placas.PLACAS_CON_PINES (ej. {'max2': [26, 28, 33]}). Los pines se revisan
    aqui, antes de generar nada: uno que no sirve es un ValueError con el motivo.
    `elegidas`: las claves de PLATAFORMAS que se generan; None = todas (la CLI).
    `ajustes_por_placa`: {placa: {ajuste: valor}} de la ventana (hw/ajustes.py).
    `editados`: {ruta: texto} archivos que el usuario corrigio a mano en la vista
    previa; sustituyen al generado si la ruta sigue existiendo.
    """
    pines = pines or {}
    validar_nombres_de_placa(pines)
    ajustes_por_placa = ajustes_por_placa or {}
    circuito = Circuito(tabla, forma)
    usadas = {nombre: _placa(nombre, pines, circuito) for nombre in placas.PLACAS_CON_PINES}
    kit = Kit(circuito)

    def quiere(nombre):
        return elegidas is None or nombre in elegidas

    def valores(nombre):
        return ajustes.con_omision(nombre, ajustes_por_placa.get(nombre))

    # --- PIC
    for chip in PIC_CHIPS:
        if not quiere(chip):
            continue
        info = usadas[chip]
        try:
            renglones = asignar_pines(circuito, info)
        except Bloqueo as b:
            kit.bloqueado(info["titulo"], str(b))
            continue
        palabras, terminos = micros.palabras_estimadas(circuito)
        if palabras > info["palabras"]:
            kit.bloqueado(info["titulo"],
                          f"el programa necesitaria unas {palabras} palabras ({terminos} "
                          f"terminos) y el {info['titulo']} tiene {info['palabras']}; "
                          "usa uno con mas memoria")
            continue
        rutas = []
        lenguajes = ajustes.lenguajes_pic(valores(chip)) if chip in ajustes.AJUSTES else ("c",)
        if "c" in lenguajes:
            rutas.append(f"pic/{chip}.c")
            kit.archivos[rutas[-1]] = micros.pic(circuito, chip, renglones, valores(chip))
        if "asm" in lenguajes:
            rutas.append(f"pic/{chip}.S")
            kit.archivos[rutas[-1]] = asm.pic18_combinacional(circuito, chip, renglones,
                                                              valores(chip))
        kit.pines[info["titulo"]] = renglones
        kit.listo(info["titulo"], *rutas)

    # --- ESP32: el mismo reparto para Arduino y MicroPython
    for variante in ESP32_VARIANTES:
        if not quiere(variante):
            continue
        info = usadas[variante]
        try:
            renglones = asignar_pines(circuito, info)
        except Bloqueo as b:
            kit.bloqueado(info["titulo"], str(b))
            continue
        ino = f"esp32/{variante}/{variante}.ino"
        py = f"esp32/{variante}/main.py"
        kit.archivos[ino] = micros.esp32_arduino(circuito, variante, renglones)
        kit.archivos[py] = micros.esp32_micropython(circuito, variante, renglones)
        kit.pines[info["titulo"]] = renglones
        kit.listo(info["titulo"], ino, py)

    # --- Arduino. Con todas las placas (la CLI): el Uno si cabe; si no, el
    # Mega. Elegidas en la ventana: cada una por su lado.
    for variante in ("uno_nano", "mega2560"):
        if elegidas is None and variante == "mega2560":
            continue
        if not quiere(variante):
            continue
        info = usadas[variante]
        try:
            renglones = asignar_pines(circuito, info)
        except Bloqueo as b:
            if elegidas is None:   # el Mega de respaldo
                kit.bloqueado(info["titulo"], f"{b}; se genera para el Mega")
                _arduino(kit, circuito, "mega2560", usadas["mega2560"], valores("mega2560"))
            else:
                kit.bloqueado(info["titulo"], str(b))
            continue
        ruta = f"arduino/{variante}/{variante}.ino"
        kit.archivos[ruta] = micros.avr(circuito, variante, renglones, valores(variante))
        kit.pines[info["titulo"]] = renglones
        kit.listo(info["titulo"], ruta)

    # --- Blue Pill
    if quiere("bluepill"):
        info = usadas["bluepill"]
        try:
            renglones = asignar_pines(circuito, info)
            ruta = "stm32/bluepill/bluepill.ino"
            kit.archivos[ruta] = micros.bluepill(circuito, renglones)
            kit.pines[info["titulo"]] = renglones
            kit.listo(info["titulo"], ruta)
        except Bloqueo as b:
            kit.bloqueado(info["titulo"], str(b))

    # --- Pico
    if quiere("pico"):
        info = usadas["pico"]
        try:
            renglones = asignar_pines(circuito, info)
            kit.archivos["pico/main.py"] = micros.pico(circuito, renglones)
            kit.pines[info["titulo"]] = renglones
            kit.listo(info["titulo"], "pico/main.py")
        except Bloqueo as b:
            kit.bloqueado(info["titulo"], str(b))

    # --- HDL: no depende de pines. La MAX II lo necesita, asi que sale con ella.
    n = circuito.nombre
    if quiere("hdl") or quiere("max2"):
        kit.archivos[f"fpga/{n}.vhd"] = logica.vhdl(circuito)
        kit.archivos[f"fpga/tb_{n}.vhd"] = logica.vhdl_testbench(circuito)
        rutas = [f"fpga/{n}.vhd", f"fpga/tb_{n}.vhd"]
        if quiere("hdl"):
            kit.archivos[f"fpga/{n}.v"] = logica.verilog(circuito)
            kit.archivos[f"fpga/tb_{n}.v"] = logica.verilog_testbench(circuito)
            rutas += [f"fpga/{n}.v", f"fpga/tb_{n}.v"]
            kit.listo(TITULO_PLATAFORMA["hdl"], *rutas)
    if quiere("max2"):
        info = usadas["max2"]
        try:
            renglones = asignar_pines(circuito, info)
            # Con los topes de ktool (6 entradas, 32 salidas) son a lo mas 160 de
            # 240 celdas: hoy nunca se bloquea por tamano. Se revisa igual, por si
            # algun dia suben los topes.
            if logica.celdas_max_ii(circuito) > 240:
                raise Bloqueo(f"pide hasta {logica.celdas_max_ii(circuito)} celdas logicas y "
                              "la EPM240 tiene 240")
            rutas = [f"fpga/{n}.qpf", f"fpga/{n}.qsf"]
            envoltura = logica.vhdl_max2(circuito, valores("max2"))
            if envoltura is not None:
                rutas.append(f"fpga/{logica.nombre_max2(circuito)}.vhd")
                kit.archivos[rutas[-1]] = envoltura
            kit.archivos[f"fpga/{n}.qsf"] = logica.qsf(circuito, renglones, valores("max2"))
            kit.archivos[f"fpga/{n}.qpf"] = logica.qpf(circuito)
            kit.pines[info["titulo"]] = renglones
            if not quiere("hdl"):
                rutas = [f"fpga/{n}.vhd", f"fpga/tb_{n}.vhd"] + rutas
            kit.listo(info["titulo"], *rutas)
        except Bloqueo as b:
            kit.bloqueado(info["titulo"], str(b))

    # --- GAL22V10
    if quiere("gal22v10"):
        try:
            kit.archivos["gal/CIRCUITO.PLD"] = logica.gal22v10(circuito)
            kit.listo(placas.GAL22V10["titulo"], "gal/CIRCUITO.PLD")
        except Bloqueo as b:
            kit.bloqueado(placas.GAL22V10["titulo"], str(b))

    # --- TTL
    if quiere("ttl"):
        try:
            kit.archivos["ttl/MATERIALES.md"] = logica.ttl(circuito)
            kit.listo("Logica discreta 74LS", "ttl/MATERIALES.md")
        except Bloqueo as b:
            kit.bloqueado("Logica discreta 74LS", str(b))

    # --- Python
    if quiere("python"):
        kit.archivos["python/simular.py"] = logica.simulacion_python(circuito)
        kit.listo("Simulacion en Python", "python/simular.py")

    _aplicar_editados(kit, editados)
    kit.archivos["LEEME.md"] = _leeme(circuito, kit.resumen)
    return kit


def _arduino(kit, circuito, variante, info, valores):
    """El sketch de una placa Arduino, o su motivo de bloqueo."""
    try:
        renglones = asignar_pines(circuito, info)
    except Bloqueo as b:
        kit.bloqueado(info["titulo"], str(b))
        return
    ruta = f"arduino/{variante}/{variante}.ino"
    kit.archivos[ruta] = micros.avr(circuito, variante, renglones, valores)
    kit.pines[info["titulo"]] = renglones
    kit.listo(info["titulo"], ruta)


def _aplicar_editados(kit, editados):
    """Los archivos corregidos a mano en la vista previa sustituyen al generado.

    Solo si la ruta sigue existiendo: si el circuito cambio tanto que ese
    archivo ya no sale (otra placa, otro nombre), la edicion vieja no se cuela.
    """
    for ruta, texto in (editados or {}).items():
        if ruta in kit.archivos:
            kit.archivos[ruta] = texto
            kit.editados.add(ruta)


def escribir(kit, carpeta):
    """Guarda los archivos del kit en `carpeta` (se crea si no existe)."""
    for ruta, texto in kit.archivos.items():
        destino = os.path.join(carpeta, *ruta.split("/"))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        # newline="\n": los mismos bytes en Windows y en Linux
        with open(destino, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)


def generar(tabla, carpeta, forma="auto", pines=None):
    """Arma y escribe el kit; devuelve el resumen. Es lo que corre `--hw`."""
    kit = armar(tabla, forma, pines)
    escribir(kit, carpeta)
    return kit.resumen


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
