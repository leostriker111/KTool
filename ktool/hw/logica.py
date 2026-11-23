"""Logica programable y discreta: VHDL, Verilog, bancos de prueba, el .qsf de la
MAX II, la GAL22V10 en WinCUPL, la lista de materiales TTL y la simulacion en
Python.

Igual que micros.py, cada funcion devuelve el texto de un archivo.
"""

from __future__ import annotations

import datetime

from .. import __version__
from ..core.simplify import literal_pairs
from . import placas
from .modelo import Bloqueo, ecuacion, tabla_de_pines


def _ecuaciones_comentadas(circuito, comentario):
    return "\n".join(
        f"{comentario}   {n} = {circuito.elegidas[n].equation}   "
        f"({circuito.elegidas[n].form.upper()})" for n in circuito.salidas)


def _esperado_como_texto(circuito, salida):
    """La columna de la tabla como texto: fila 0 primero, '-' en los don't care."""
    return "".join("-" if v == "x" else str(v) for v in circuito.esperado[salida])


# ==================================================================== VHDL

def vhdl(circuito):
    nombre = circuito.nombre
    puertos = [f"        {e} : in  std_logic" for e in circuito.entradas]
    puertos += [f"        {s} : out std_logic" for s in circuito.salidas]
    asignaciones = "\n".join(
        f"    {s} <= {ecuacion(circuito.arboles[s], 'vhdl')};" for s in circuito.salidas)
    return f"""\
-- {nombre} -- generado por ktool {__version__}
-- VHDL sintetizable (IEEE 1164). Combinacional: asignacion concurrente, sin reloj.
--
-- Ecuaciones:
{_ecuaciones_comentadas(circuito, '--')}

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity {nombre} is
    port (
{(';' + chr(10)).join(puertos)}
    );
end entity {nombre};

architecture combinacional of {nombre} is
begin
{asignaciones}
end architecture combinacional;
"""


def vhdl_testbench(circuito):
    """Barre las 2^n combinaciones y compara cada salida contra la tabla."""
    nombre, n = circuito.nombre, circuito.n_entradas
    filas = 1 << n
    senales_e = ", ".join(circuito.entradas)
    senales_s = ", ".join(circuito.salidas)
    constantes = "\n".join(
        f'    constant ESPERADO_{s} : string(1 to {filas}) := "{_esperado_como_texto(circuito, s)}";'
        for s in circuito.salidas)
    mapa = ", ".join(f"{x} => {x}" for x in circuito.entradas + circuito.salidas)
    reparto = " ".join(f"{e} <= fila({n - 1 - k});" for k, e in enumerate(circuito.entradas))
    revisiones = []
    for s in circuito.salidas:
        revisiones.append(f"""\
            if ESPERADO_{s}(i + 1) /= '-' then
                if (ESPERADO_{s}(i + 1) = '1') /= ({s} = '1') then
                    report "fila " & integer'image(i) & ": {s} vale " & std_logic'image({s})
                         & " y deberia valer " & ESPERADO_{s}(i + 1) severity error;
                    errores := errores + 1;
                end if;
            end if;""")
    return f"""\
-- Banco de prueba de {nombre} -- generado por ktool {__version__}
-- Recorre las {filas} combinaciones de entrada y compara cada salida con la
-- tabla de verdad. En la constante ESPERADO, el caracter i+1 es la fila i y
-- '-' es un don't care (no se revisa).
--
-- Con GHDL:  ghdl -a {nombre}.vhd tb_{nombre}.vhd && ghdl -r tb_{nombre}

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_{nombre} is
end entity tb_{nombre};

architecture prueba of tb_{nombre} is
    signal {senales_e} : std_logic := '0';
    signal {senales_s} : std_logic;
{constantes}
begin
    dut : entity work.{nombre} port map ({mapa});

    process
        variable fila : unsigned({n - 1} downto 0);
        variable errores : natural := 0;
    begin
        for i in 0 to {filas - 1} loop
            fila := to_unsigned(i, {n});
            {reparto}
            wait for 10 ns;
{chr(10).join(revisiones)}
        end loop;
        if errores = 0 then
            report "OK: las {filas} combinaciones coinciden con la tabla" severity note;
        else
            report integer'image(errores) & " diferencia(s) con la tabla" severity failure;
        end if;
        wait;
    end process;
end architecture prueba;
"""


# ================================================================= Verilog

def verilog(circuito):
    nombre = circuito.nombre
    puertos = [f"    input  wire {e}" for e in circuito.entradas]
    puertos += [f"    output wire {s}" for s in circuito.salidas]
    asignaciones = "\n".join(
        f"    assign {s} = {ecuacion(circuito.arboles[s], 'verilog')};" for s in circuito.salidas)
    return f"""\
// {nombre} -- generado por ktool {__version__}
// Verilog sintetizable (IEEE 1364). Combinacional: `assign`, sin reloj.
//
// Ecuaciones:
{_ecuaciones_comentadas(circuito, '//')}

`timescale 1ns/1ps
module {nombre} (
{(',' + chr(10)).join(puertos)}
);
{asignaciones}
endmodule
"""


def verilog_testbench(circuito):
    nombre, n = circuito.nombre, circuito.n_entradas
    filas = 1 << n
    constantes = []
    for s in circuito.salidas:
        valor = "".join("1" if v == 1 else "0" for v in reversed(circuito.esperado[s]))
        importa = "".join("0" if v == "x" else "1" for v in reversed(circuito.esperado[s]))
        constantes.append(f"    localparam [{filas - 1}:0] ESPERADO_{s} = {filas}'b{valor};")
        constantes.append(f"    localparam [{filas - 1}:0] IMPORTA_{s}  = {filas}'b{importa};")
    revisiones = "\n".join(f"""\
            if (IMPORTA_{s}[i] && {s} !== ESPERADO_{s}[i]) begin
                $display("fila %0d: {s} vale %b y deberia valer %b", i, {s}, ESPERADO_{s}[i]);
                errores = errores + 1;
            end""" for s in circuito.salidas)
    formato = " ".join(["%b"] * n) + " | " + " ".join(["%b"] * circuito.n_salidas)
    return f"""\
// Banco de prueba de {nombre} -- generado por ktool {__version__}
// Recorre las {filas} combinaciones y compara cada salida con la tabla de verdad.
// En ESPERADO_x el bit i es la fila i; IMPORTA_x en 0 marca un don't care.
//
// Con Icarus Verilog:  iverilog -o tb tb_{nombre}.v {nombre}.v && vvp tb

`timescale 1ns/1ps
module tb_{nombre};
    reg  {', '.join(circuito.entradas)};
    wire {', '.join(circuito.salidas)};
    integer i;
    integer errores;
{chr(10).join(constantes)}

    {nombre} dut ({', '.join(f'.{x}({x})' for x in circuito.entradas + circuito.salidas)});

    initial begin
        errores = 0;
        $display("{' '.join(circuito.entradas)} | {' '.join(circuito.salidas)}");
        for (i = 0; i < {filas}; i = i + 1) begin
            {{{', '.join(circuito.entradas)}}} = i;
            #10;
            $display("{formato}", {', '.join(circuito.entradas + circuito.salidas)});
{revisiones}
        end
        if (errores == 0)
            $display("OK: las {filas} combinaciones coinciden con la tabla");
        else
            $display("FALLO: %0d diferencia(s) con la tabla", errores);
        $finish;
    end
endmodule
"""


# ================================================================ MAX II

def celdas_max_ii(circuito):
    """Cota de celdas logicas (LE) que pide el circuito en la MAX II.

    Cada LE de la MAX II es una tabla de 4 entradas. Una funcion de hasta 4
    entradas cabe en 1; de 5, en 3 (dos tablas y la que escoge); de 6, en 5
    (cuatro tablas de 4 y dos niveles para escoger, que caben en una). Es una
    cota por arriba: Quartus suele usar menos.
    """
    por_salida = {2: 1, 3: 1, 4: 1, 5: 3, 6: 5}[circuito.n_entradas]
    constantes = sum(1 for s in circuito.salidas if circuito.elegidas[s].const is not None)
    return por_salida * (circuito.n_salidas - constantes)


def qsf(circuito, renglones):
    """Restricciones de Quartus Prime para la MAX II EPM240T100C5."""
    lineas = [f"""\
# {circuito.nombre} en {placas.EPM240['titulo']} -- generado por ktool {__version__}
# Quartus Prime: abre {circuito.nombre}.qpf y compila. Las patas salen de la tabla
# oficial de Intel (PT-EPM240-1.4): solo patas de I/O de usuario, sin GCLK,
# DEV_OE ni DEV_CLRn, que quedan para disenos con reloj.
#
# Mapeo de pines:
{tabla_de_pines(renglones, '#', lambda p: f'PIN_{p}')}
#
# Las patas son de 3.3 V y NO aguantan 5 V directo: los interruptores de las
# entradas van a 3.3 V. Si la senal viene de un chip TTL de 5 V, baja el nivel
# antes (un divisor de 1 kOhm y 2 kOhm, o un 74LVC245).
#
# Tamano: a lo mas {celdas_max_ii(circuito)} de las 240 celdas logicas.

set_global_assignment -name FAMILY "MAX II"
set_global_assignment -name DEVICE EPM240T100C5
set_global_assignment -name TOP_LEVEL_ENTITY {circuito.nombre}
set_global_assignment -name VHDL_FILE {circuito.nombre}.vhd
# Para usar la version en Verilog, cambia la linea de arriba por:
# set_global_assignment -name VERILOG_FILE {circuito.nombre}.v

# El VHDL generado se valido en VHDL-1993 estricto (y en 2008).
set_global_assignment -name VHDL_INPUT_VERSION VHDL_1993
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files

# Las patas que el diseno no usa quedan como entradas en alta impedancia. Por
# omision Quartus las deja como salidas a tierra ("As output driving ground"),
# y en las placas de practica de la EPM240 hay LEDs y botones en patas sueltas:
# un boton a VCC contra una pata en tierra es un corto.
set_global_assignment -name RESERVE_ALL_UNUSED_PINS "AS INPUT TRI-STATED"
"""]
    for r in renglones:
        lineas.append(f"set_location_assignment PIN_{r['pin']} -to {r['senal']}")
    lineas.append("")
    for r in renglones:
        lineas.append(f'set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to {r["senal"]}')
    return "\n".join(lineas) + "\n"


def qpf(circuito):
    return (f"# Proyecto de Quartus Prime para {circuito.nombre} -- generado por ktool\n"
            f'PROJECT_REVISION = "{circuito.nombre}"\n')


# ============================================================ GAL22V10

def _producto_cupl(patron, variables):
    """Un termino producto con la polaridad del patron: A & !B ..."""
    lits = [("!" if comp else "") + v for v, comp in literal_pairs(patron, variables)]
    return " & ".join(lits) if lits else "'b'1"


def gal22v10(circuito):
    """Archivo .pld de WinCUPL, o Bloqueo si no cabe en la GAL22V10.

    Cada macrocelda suma un numero fijo de terminos producto (8 a 16). Se
    escribe la suma de productos minima; si no cabe, se prueba el complemento
    (`!Y = ...`), que la GAL implementa con su fusible de polaridad. Las salidas
    que piden mas terminos van a las macroceldas mas grandes.
    """
    gal = placas.GAL22V10
    if circuito.n_salidas > len(gal["terminos_por_pata"]):
        raise Bloqueo(
            f"requiere {circuito.n_salidas} salidas y la GAL22V10 tiene 10 macroceldas: "
            "migra a la MAX II (carpeta fpga)")
    if circuito.n_entradas > len(gal["entradas"]):
        raise Bloqueo(f"requiere {circuito.n_entradas} entradas y la GAL22V10 tiene 12")

    variables = circuito.entradas
    necesidad = {}
    for s in circuito.salidas:
        sop, pos = circuito.soluciones[s]["sop"], circuito.soluciones[s]["pos"]
        if sop.const is not None:
            necesidad[s] = (0, 0)
        else:
            necesidad[s] = (len(sop.patterns), len(pos.patterns))

    patas = sorted(gal["terminos_por_pata"], key=lambda p: (-gal["terminos_por_pata"][p], p))
    orden = sorted(circuito.salidas, key=lambda s: -min(necesidad[s]))

    asignacion = {}
    for s, pata in zip(orden, patas):
        cap = gal["terminos_por_pata"][pata]
        directo, complemento = necesidad[s]
        if directo <= cap:
            asignacion[s] = (pata, "directa")
        elif complemento <= cap:
            asignacion[s] = (pata, "complemento")
        else:
            raise Bloqueo(
                f"la salida {s} necesita {min(directo, complemento)} terminos producto y "
                f"la macrocelda que le toca (pata {pata}) admite {cap}; la mas grande de "
                "la GAL22V10 admite 16. Migra a la MAX II (carpeta fpga)")

    lineas = [f"""\
Name     CIRCUITO ;
PartNo   00 ;
Date     {datetime.date.today():%m/%d/%Y} ;
Revision 01 ;
Designer ktool ;
Company  ktool ;
Assembly None ;
Location None ;
Device   G22V10 ;

/* {circuito.nombre} -- generado por ktool {__version__}                    */
/* Compilar con WinCUPL; grabar el .jed con un programador de GAL         */
/* (TL866/T48 o similar).                                                 */
/*                                                                        */
/* Ecuaciones:                                                            */"""]
    for s in circuito.salidas:
        lineas.append(f"/*   {s} = {circuito.elegidas[s].equation}".ljust(74) + " */")
    lineas.append("\n/* ---- Entradas ---- */")
    for e, pata in zip(circuito.entradas, gal["entradas"]):
        lineas.append(f"PIN {pata} = {e} ;")
    lineas.append("\n/* ---- Salidas (pata = terminos que admite su macrocelda) ---- */")
    for s in circuito.salidas:
        pata, _ = asignacion[s]
        lineas.append(f"PIN {pata} = {s} ;  /* {gal['terminos_por_pata'][pata]} terminos */")
    lineas.append("\n/* ---- Ecuaciones (suma de productos) ---- */")
    for s in circuito.salidas:
        sol = circuito.soluciones[s]
        _, polaridad = asignacion[s]
        if sol["sop"].const is not None:
            lineas.append(f"{s} = 'b'{sol['sop'].const} ;")
        elif polaridad == "directa":
            productos = [_producto_cupl(p, variables) for p in sol["sop"].patterns]
            lineas.append(f"{s} = " + "\n    # ".join(productos) + " ;")
        else:
            productos = [_producto_cupl(p, variables) for p in sol["pos"].patterns]
            lineas.append(f"/* {s} pide mas terminos de los que caben: se escribe su complemento */")
            lineas.append(f"!{s} = " + "\n     # ".join(productos) + " ;")
    return "\n".join(lineas) + "\n"


# ======================================================== TTL / CMOS

def _nombre_comercial(chip):
    """'7408' -> '74LS08'; los CMOS de la serie 4000 se quedan como CD40xx."""
    if chip.startswith("74"):
        return "74LS" + chip[2:]
    return "CD" + chip


def ttl(circuito):
    """Lista de materiales y conexiones pin a pin en chips 74LS.

    Reusa el armado del protoboard (proto/netlist.py), que ya trae los pinouts
    verificados contra hoja de datos. Prueba SOP, POS, solo NAND y solo NOR y se
    queda con la que usa menos encapsulados; el netlist elegido se revisa contra
    la tabla de verdad antes de escribirlo.
    """
    from ..proto import chips, netlist

    nombradas = {}
    candidatos = {}
    for forma in ("sop", "pos", "nand", "nor"):
        nombradas[forma] = [(s, circuito.soluciones[s][forma]) for s in circuito.salidas]
        try:
            # con extremos 'led' cada salida lleva su LED y su resistencia, y
            # quedan en la lista de cables como cualquier otra conexion
            net = netlist.construir(nombradas[forma], forma, extremos="led")
        except Exception:  # una forma que no se puede armar no compite
            continue
        if net["completo"]:
            candidatos[forma] = net
    if not candidatos:
        raise Bloqueo("ninguna realizacion cabe en los chips del catalogo")

    orden = {"sop": 0, "pos": 1, "nand": 2, "nor": 3}
    forma = min(candidatos, key=lambda f: (len(candidatos[f]["pastillas"]), orden[f]))
    net = candidatos[forma]
    problemas = netlist.comprobar(net, circuito.tabla)
    if problemas:
        raise Bloqueo("el armado no coincide con la tabla: " + problemas[0])

    por_modelo = {}
    for p in net["pastillas"]:
        info = chips.CHIPS[p["chip"]]
        huecos = len(chips.compuertas(p["chip"]))
        usadas = sum(1 for g in p["compuertas"] if g is not None)
        d = por_modelo.setdefault(p["chip"], {"cuantos": 0, "usadas": 0, "huecos": 0,
                                              "descripcion": info["descripcion"],
                                              "refs": []})
        d["cuantos"] += 1
        d["usadas"] += usadas
        d["huecos"] += huecos
        d["refs"].append(p["ref"])

    otras = {f: len(n["pastillas"]) for f, n in candidatos.items() if f != forma}
    lineas = [f"""\
# {circuito.nombre} en logica discreta 74LS

Generado por ktool {__version__}. Sirve igual para protoboard, Proteus o
Logisim (los tres tienen los mismos 74LSxx).

Realizacion elegida: **{forma.upper()}**, la que usa menos encapsulados
({len(net['pastillas'])}). Las otras: """ + (", ".join(f"{f.upper()} {n}" for f, n in sorted(otras.items())) or "ninguna mas se pudo armar") + ".", ""]
    lineas.append("Ecuaciones de esa realizacion:\n")
    for s in circuito.salidas:
        lineas.append(f"- `{s} = {circuito.soluciones[s][forma].equation}`")

    lineas.append("\n## Lista de materiales\n")
    lineas.append("| Cantidad | Pieza | Para que | Referencias |")
    lineas.append("|---|---|---|---|")
    for modelo in sorted(por_modelo):
        d = por_modelo[modelo]
        lineas.append(
            f"| {d['cuantos']} | {_nombre_comercial(modelo)} | {d['descripcion']} "
            f"({d['usadas']} compuertas usadas de {d['huecos']} disponibles) | "
            f"{', '.join(d['refs'])} |")
    lineas.append(f"| {circuito.n_entradas} | interruptor (DIP switch) | una entrada cada uno | "
                  + ", ".join(f"SW{i + 1}" for i in range(circuito.n_entradas)) + " |")
    # Ojo con el valor: una entrada 74LS en bajo EMPUJA hasta 0.4 mA hacia
    # afuera. Sobre 10 kOhm eso son 4 V, y la entrada "en 0" lee 1. Para que
    # quede debajo de VIL = 0.8 V la resistencia no puede pasar de 2 kOhm.
    lineas.append(f"| {circuito.n_entradas} | resistencia de 1 kOhm | pull-down de cada "
                  "interruptor, que va a 5 V. Sin ella la entrada al aire lee 1; y con "
                  "10 kOhm tambien: la entrada 74LS empuja 0.4 mA y se levanta a 4 V | |")
    leds = [c for c in net["componentes"] if c["tipo"] not in ("ci", "entrada")]
    if leds:
        lineas.append(f"| {circuito.n_salidas} | LED + resistencia de 330 Ohm | uno por "
                      "salida, ya incluidos en la lista de cables | "
                      + ", ".join(c["ref"] for c in leds) + " |")
    lineas.append("| 1 | fuente de 5 V | alimentacion (los 74LS no aguantan mas de 5.25 V) | |")

    lineas.append("\n## Conexiones pin a pin\n")
    lineas.append("Cada renglon es un cable. `U1-3` es la pata 3 de U1. Las compuertas "
                  "sobrantes llevan sus entradas a VCC o a GND para que no floten.\n")
    lineas.append("| Senal | De | A |")
    lineas.append("|---|---|---|")
    for c in netlist.lista_de_cables(net):
        lineas.append(f"| `{c['nodo']}` | {c['de']} | {c['a']} |")
    if net["avisos"]:
        lineas.append("\n## Avisos\n")
        for a in net["avisos"]:
            lineas.append(f"- {a}")
    lineas.append("\nEl armado se comprobo contra la tabla de verdad, fila por fila, antes "
                  "de escribir este archivo.\n")
    return "\n".join(lineas)


# =========================================================== Python

def simulacion_python(circuito):
    """Script autonomo (solo libreria estandar) que imprime la tabla de verdad
    de las ecuaciones y la compara con la tabla original."""
    esperados = "\n".join(f'    "{s}": "{_esperado_como_texto(circuito, s)}",'
                          for s in circuito.salidas)
    ecuaciones = "\n".join(f"    {s} = {ecuacion(circuito.arboles[s], 'python')}"
                           for s in circuito.salidas)
    return f'''\
#!/usr/bin/env python3
"""Simulacion de {circuito.nombre} -- generado por ktool {__version__}

Evalua las ecuaciones en las {1 << circuito.n_entradas} combinaciones de entrada,
imprime la tabla de verdad alineada y la compara con la tabla original. Solo
usa la libreria estandar. Sale con codigo 1 si alguna fila no coincide.

    python simular.py
"""

import itertools
import sys

ENTRADAS = {circuito.entradas!r}
SALIDAS = {circuito.salidas!r}

# La tabla original, fila 0 primero: '1', '0' o '-' (don't care: no se revisa).
ESPERADO = {{
{esperados}
}}


def evaluar({", ".join(circuito.entradas)}):
    """Las ecuaciones minimizadas. Los valores son 0 o 1; `x ^ 1` es NOT."""
{ecuaciones}
    return {{{", ".join(f'"{s}": {s}' for s in circuito.salidas)}}}


def main():
    ancho = {{n: max(len(n), 1) for n in ENTRADAS + SALIDAS}}
    titulo = " ".join(n.rjust(ancho[n]) for n in ENTRADAS)
    titulo += " | " + " ".join(n.rjust(ancho[n]) for n in SALIDAS) + " | revision"
    print(titulo)
    print("-" * len(titulo))

    errores = 0
    for fila, valores in enumerate(itertools.product((0, 1), repeat=len(ENTRADAS))):
        salidas = evaluar(*valores)
        marcas = []
        for s in SALIDAS:
            esperado = ESPERADO[s][fila]
            if esperado == "-":
                marcas.append("x")
            elif int(esperado) == salidas[s]:
                marcas.append("ok")
            else:
                marcas.append("MAL")
                errores += 1
        texto = " ".join(str(v).rjust(ancho[n]) for n, v in zip(ENTRADAS, valores))
        texto += " | " + " ".join(str(salidas[s]).rjust(ancho[s]) for s in SALIDAS)
        print(texto + " | " + " ".join(marcas))

    print()
    if errores:
        print(f"{{errores}} diferencia(s) con la tabla original")
        return 1
    print("OK: todas las filas coinciden con la tabla original ('x' = don't care)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
