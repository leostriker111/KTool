"""Una maquina de estados en VHDL, por los tres metodos de la practica de
Circuitos Secuenciales:

    ecuaciones   las ecuaciones minimizadas de cada flip-flop (D, JK, T o SR)
                 y un process con rising_edge que las aplica
    tabla        la tabla de transicion tal cual: un case sobre (estado, entradas)
    estados      el diagrama de estados: un tipo con los estados por nombre y un
                 case por estado; la sintesis escoge la codificacion

Los tres tienen la misma entidad (mismos puertos), asi que el mismo banco de
prueba sirve para los tres: le da las entradas ciclo por ciclo y revisa que el
estado sea el que da la simulacion en Python (fsm/contadores.simular).

Reset asincrono, activo en alto, al estado inicial. El reloj entra por `clk`:
para verlo en la MAX II hace falta bajarlo de 50 MHz a algo visible (eso lo
agrega el divisor de reloj).
"""

from __future__ import annotations

from .. import __version__
from ..core.simplify import solve_output
from ..fsm import Machine, flipflops
from ..render.codegen import solution_to_ast
from .modelo import ecuacion, validar_nombres

ENTIDAD = "maquina"
PREFIJO = "e_"     # senales internas: e_Q2, e_X (los puertos de salida no se leen en VHDL-93)


def _maquina(maquina):
    return maquina if isinstance(maquina, Machine) else Machine.from_dict(maquina)


def _inicial(m, fuente):
    nombre = fuente.get("inicial") if isinstance(fuente, dict) else None
    return m._by_name.get(nombre) if nombre else m.states[0]


def _puertos(m):
    lineas = ["        clk : in  std_logic", "        rst : in  std_logic"]
    lineas += [f"        {e} : in  std_logic" for e in m.inputs]
    lineas += [f"        {q} : out std_logic" for q in m.state_bits]
    lineas += [f"        {s} : out std_logic" for s in m.outputs]
    return (";\n").join(lineas)


def _encabezado(m, metodo, extra=""):
    return f"""\
-- {m.name}: maquina de estados por el metodo de {metodo}
-- generado por ktool {__version__}. {extra}
-- Reset asincrono (rst = '1') al estado inicial; cambia en el flanco de subida de clk.
-- Entradas: {', '.join(m.inputs) or '(ninguna)'}.  Estado: {', '.join(m.state_bits)}.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity {ENTIDAD} is
    port (
{_puertos(m)}
    );
end entity {ENTIDAD};
"""


def _salidas_moore(m, prefijo):
    """Las salidas de una Moore como ecuaciones sobre el estado."""
    lineas = []
    for nombre, columna in m.output_columns().items():
        sol = solve_output(columna, m.output_variables())["best"]
        lineas.append(f"    {nombre} <= {ecuacion(solution_to_ast(sol), 'vhdl', prefijo)};")
    return lineas


# ------------------------------------------------------------ 1. ecuaciones

def por_ecuaciones(maquina, ff="D"):
    m = _maquina(maquina)
    ff = flipflops.normalize(ff)
    validar_nombres(m.inputs + m.outputs, m.state_bits)
    inicial = _inicial(m, maquina)
    variables = m.io_variables()
    letras = flipflops.inputs(ff)
    excitacion = m.excitation_columns(ff)

    senales = [f"{PREFIJO}{v}" for v in variables] + list(excitacion)
    cuerpo = [f"    {PREFIJO}{e} <= {e};" for e in m.inputs]
    cuerpo.append("")
    cuerpo.append(f"    -- entradas de los flip-flops {ff}, minimizadas (Quine-McCluskey)")
    for nombre, columna in excitacion.items():
        sol = solve_output(columna, variables)["best"]
        cuerpo.append(f"    {nombre} <= {ecuacion(solution_to_ast(sol), 'vhdl', PREFIJO)};"
                      f"   -- {nombre} = {sol.equation}")

    # ecuacion caracteristica de cada flip-flop
    actualizar = []
    for k, q in enumerate(m.state_bits):
        sufijo = m._suffix(k)
        e = f"{PREFIJO}{q}"
        if ff == "D":
            nuevo = f"D{sufijo}"
        elif ff == "T":
            nuevo = f"{e} xor T{sufijo}"
        elif ff == "JK":
            nuevo = f"(J{sufijo} and not {e}) or (not K{sufijo} and {e})"
        else:  # SR
            nuevo = f"S{sufijo} or (not R{sufijo} and {e})"
        actualizar.append(f"            {e} <= {nuevo};")
    reset = [f"            {PREFIJO}{q} <= '{b}';" for q, b in zip(m.state_bits, inicial.code)]

    texto = _encabezado(m, "ecuaciones", f"Flip-flops {ff}: {' '.join(letras)}.")
    texto += f"""
architecture ecuaciones of {ENTIDAD} is
    signal {', '.join(senales)} : std_logic;
begin
{chr(10).join(cuerpo)}

    flipflops : process (clk, rst)
    begin
        if rst = '1' then
{chr(10).join(reset)}
        elsif rising_edge(clk) then
{chr(10).join(actualizar)}
        end if;
    end process;

{chr(10).join(f'    {q} <= {PREFIJO}{q};' for q in m.state_bits)}
{chr(10).join(_salidas_moore(m, PREFIJO))}
end architecture ecuaciones;
"""
    return texto


# ----------------------------------------------------------------- 2. tabla

def por_tabla(maquina):
    m = _maquina(maquina)
    validar_nombres(m.inputs + m.outputs, m.state_bits)
    inicial = _inicial(m, maquina)
    nq, ne = len(m.state_bits), len(m.inputs)
    ancho = nq + ne
    juntar = " & ".join([f"estado({nq - 1 - k})" for k in range(nq)] + list(m.inputs))
    casos = []
    for st in m.states:
        for combo in m.input_combos():
            t = m.next_state(st.name, combo)
            if t is None:
                continue
            destino = m._by_name[t.dst]
            casos.append(f'            when "{st.code}{combo}" => siguiente <= "{destino.code}";'
                         f"   -- {st.label} -> {destino.label}")
    asignar = "\n".join(f"    {q} <= estado({nq - 1 - k});" for k, q in enumerate(m.state_bits))
    texto = _encabezado(m, "tabla", "La tabla de transicion tal cual, en un case.")
    texto += f"""
architecture tabla of {ENTIDAD} is
    signal estado, siguiente : std_logic_vector({nq - 1} downto 0);
    signal fila : std_logic_vector({ancho - 1} downto 0);    -- estado y entradas juntos
begin
    fila <= {juntar};

    transicion : process (fila)
    begin
        case fila is
{chr(10).join(casos)}
            when others => siguiente <= "{inicial.code}";   -- codigos sin usar: al inicio
        end case;
    end process;

    registro : process (clk, rst)
    begin
        if rst = '1' then
            estado <= "{inicial.code}";
        elsif rising_edge(clk) then
            estado <= siguiente;
        end if;
    end process;

{asignar}
{_salidas_de_tabla(m)}end architecture tabla;
"""
    return texto


def _salidas_de_tabla(m):
    """Las salidas Moore como un case sobre el estado."""
    if not m.outputs:
        return ""
    lineas = ["    salidas : process (estado)", "    begin", "        case estado is"]
    for st in m.states:
        valores = " ".join(f"{s} <= '{b}';" for s, b in zip(m.outputs, st.out or "0" * len(m.outputs)))
        lineas.append(f'            when "{st.code}" => {valores}')
    ceros = " ".join(f"{s} <= '0';" for s in m.outputs)
    lineas += [f"            when others => {ceros}", "        end case;", "    end process;", ""]
    return "\n".join(lineas)


# --------------------------------------------------------- 3. diagrama de estados

def por_estados(maquina):
    m = _maquina(maquina)
    validar_nombres(m.inputs + m.outputs, m.state_bits)
    inicial = _inicial(m, maquina)
    nq = len(m.state_bits)
    nombres = [st.name for st in m.states]
    validar_nombres(nombres, [])
    casos = []
    for st in m.states:
        casos.append(f"            when {st.name} =>   -- {st.label}")
        if not m.inputs:
            t = m.next_state(st.name, "")
            casos.append(f"                siguiente <= {t.dst if t else inicial.name};")
            continue
        casos.append("                case entradas is")
        for combo in m.input_combos():
            t = m.next_state(st.name, combo)
            casos.append(f'                    when "{combo}" => siguiente <= '
                         f"{t.dst if t else inicial.name};")
        casos.append(f"                    when others => siguiente <= {inicial.name};")
        casos.append("                end case;")
    decodificar = []
    for st in m.states:
        valores = [f"{q} <= '{b}';" for q, b in zip(m.state_bits, st.code)]
        valores += [f"{s} <= '{b}';" for s, b in zip(m.outputs, st.out or "0" * len(m.outputs))]
        decodificar.append(f"            when {st.name} => {' '.join(valores)}")
    entradas = ""
    if m.inputs:
        entradas = (f"    signal entradas : std_logic_vector({len(m.inputs) - 1} downto 0);\n")
    juntar = f"    entradas <= {' & '.join(m.inputs)};\n" if m.inputs else ""
    if len(m.inputs) == 1:   # un solo bit: se escribe como vector de 1
        juntar = f"    entradas(0) <= {m.inputs[0]};\n"
    sensibilidad = "actual, entradas" if m.inputs else "actual"
    texto = _encabezado(m, "diagrama de estados",
                        "Los estados por nombre; la sintesis escoge la codificacion.")
    texto += f"""
architecture estados of {ENTIDAD} is
    type t_estado is ({', '.join(nombres)});
    signal actual, siguiente : t_estado;
{entradas}begin
{juntar}
    transicion : process ({sensibilidad})
    begin
        case actual is
{chr(10).join(casos)}
        end case;
    end process;

    registro : process (clk, rst)
    begin
        if rst = '1' then
            actual <= {inicial.name};
        elsif rising_edge(clk) then
            actual <= siguiente;
        end if;
    end process;

    -- lo que muestra cada estado (su codigo y sus salidas)
    salidas : process (actual)
    begin
        case actual is
{chr(10).join(decodificar)}
        end case;
    end process;
end architecture estados;
"""
    return texto


# ------------------------------------------------------------ banco de prueba

def banco_de_prueba(maquina, entradas_por_ciclo):
    """Testbench que aplica `entradas_por_ciclo` (una combinacion por flanco) y
    compara el estado con la simulacion en Python, ciclo por ciclo."""
    from ..fsm.contadores import simular
    m = _maquina(maquina)
    fuente = maquina if isinstance(maquina, dict) else None
    inicial = _inicial(m, fuente or {})
    visitados = simular(fuente, entradas_por_ciclo, inicial.name) if fuente else None
    codigos = [m._by_name[n].code for n in visitados]
    nq = len(m.state_bits)
    senales = ["clk", "rst"] + m.inputs + m.state_bits + m.outputs
    mapa = ", ".join(f"{s} => {s}" for s in senales)
    leer = " & ".join(m.state_bits)
    if nq == 1:
        leer = f"(0 => {m.state_bits[0]})"
    pasos = [f'        revisar("{codigos[0]}", 0);']
    for i, combo in enumerate(entradas_por_ciclo, start=1):
        poner = " ".join(f"{e} <= '{b}';" for e, b in zip(m.inputs, combo))
        if poner:
            pasos.append(f"        {poner}")
        pasos.append("        wait until rising_edge(clk); wait for 1 ns;")
        pasos.append(f'        revisar("{codigos[i]}", {i});')
    return f"""\
-- Banco de prueba de {m.name} -- generado por ktool {__version__}
-- Sirve para los tres metodos (misma entidad). Aplica {len(entradas_por_ciclo)} ciclos y
-- compara el estado con lo esperado. Con GHDL:
--   ghdl -a maquina_tabla.vhd tb_maquina.vhd && ghdl -r tb_maquina

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity tb_{ENTIDAD} is
end entity tb_{ENTIDAD};

architecture prueba of tb_{ENTIDAD} is
    signal {', '.join(senales)} : std_logic := '0';
    signal terminado : boolean := false;
begin
    dut : entity work.{ENTIDAD} port map ({mapa});

    reloj : process
    begin
        while not terminado loop
            clk <= '0'; wait for 5 ns;
            clk <= '1'; wait for 5 ns;
        end loop;
        wait;
    end process;

    estimulo : process
        variable fallas : natural := 0;
        procedure revisar(esperado : std_logic_vector; ciclo : natural) is
            variable obtenido : std_logic_vector({nq - 1} downto 0);
        begin
            obtenido := {leer};
            if obtenido /= esperado then
                report "ciclo " & integer'image(ciclo) & ": el estado no es el esperado"
                    severity error;
                fallas := fallas + 1;
            end if;
        end procedure;
    begin
        rst <= '1'; wait for 2 ns; rst <= '0';
{chr(10).join(pasos)}
        if fallas = 0 then
            report "OK: los {len(entradas_por_ciclo)} ciclos siguen la secuencia esperada" severity note;
        else
            report integer'image(fallas) & " ciclo(s) fuera de secuencia" severity failure;
        end if;
        terminado <= true;
        wait;
    end process;
end architecture prueba;
"""


def estimulo_completo(maquina, vueltas=2):
    """Entradas de prueba: cada combinacion de entradas durante suficientes
    ciclos para recorrer su secuencia `vueltas` veces."""
    import random
    m = _maquina(maquina)
    ciclos = len(m.states) * vueltas
    combos = m.input_combos()
    estimulo = []
    for combo in combos:
        estimulo += [combo] * ciclos
    # y luego cambios de modo al azar (semilla fija: siempre los mismos), que es
    # donde se esconden los errores de los saltos entre secuencias
    if len(combos) > 1:
        azar = random.Random(len(m.states))
        estimulo += [azar.choice(combos) for _ in range(ciclos * 2)]
    return estimulo


def escribir(fuente, carpeta, ff="D"):
    """Los tres metodos y el banco de prueba en `carpeta`. Devuelve los nombres."""
    import os
    os.makedirs(carpeta, exist_ok=True)
    archivos = {
        f"maquina_ecuaciones_{flipflops.normalize(ff)}.vhd": por_ecuaciones(fuente, ff),
        "maquina_tabla.vhd": por_tabla(fuente),
        "maquina_estados.vhd": por_estados(fuente),
        "tb_maquina.vhd": banco_de_prueba(fuente, estimulo_completo(fuente)),
    }
    for nombre, texto in archivos.items():
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    return list(archivos)
