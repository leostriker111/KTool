"""El kit de hardware para MAQUINAS DE ESTADO: la maquina lista para cada placa.

Es el hermano de kit.py (que arma circuitos combinacionales) para lo que piden
las practicas de circuitos secuenciales: contadores y maquinas con reloj y
reset. Para la misma maquina arma:

    LEEME.md                        resumen: que se genero, que se bloqueo y por que
    pic/<chip>.c                    PIC18F45K50 y PIC18F4550 con XC8
    pic/<chip>.S                    los mismos en ensamblador (pic-as)
    arduino/<placa>/<placa>.ino     Uno/Nano y Mega 2560
    fpga/maquina.vhd                la maquina por el metodo elegido (hw/vhdl_fsm.py)
    fpga/divisor.vhd                baja el reloj de la tarjeta a la frecuencia pedida
    fpga/maquina_max2.vhd           nivel superior: divisor + maquina + reset + inversiones
    fpga/tb_maquina.vhd             banco de prueba de la maquina (GHDL)
    fpga/maquina_max2.qsf / .qpf    proyecto de Quartus para la EPM240
    python/simular.py               imprime la secuencia de estados

Las demas plataformas del kit (ESP32, Pico, GAL, 74LS...) salen en el resumen
como bloqueadas, con el motivo.

Todas las placas leen la misma TablaMaquina: el siguiente estado de cada
(estado, entradas) como numero. Asi la tabla que se graba en el PIC, en el
Arduino y en la simulacion es, numero por numero, la de la maquina.

Como se integra:
    ventana del kit   su fuente de maquina responde senales(placa) con
                      `senales(fuente, placa)` y armar(config) con
                      `armar(fuente, config)`
    documento         report.seccion_kit(armado, config, seccion_reloj(fuente, config))
"""

from __future__ import annotations

import html

from .. import __version__
from ..fsm import Machine
from . import ajustes, asm, kit, micros, placas, reloj, vhdl_fsm
from .micros import _puerto
from .modelo import Bloqueo, asignar_pines, con_pines, tabla_de_pines, validar_nombres

# Las plataformas que sabe armar este modulo. Las demas de kit.PLATAFORMAS se
# reportan como bloqueadas con MOTIVO_NO_FSM.
PIC18 = ["pic18f45k50", "pic18f4550"]
ARDUINOS = ["uno_nano", "mega2560"]
MOTIVO_NO_FSM = "las maquinas de estado se generan para PIC 18F, MAX II y Arduino"

# MAX II EPM240: el reloj solo entra por una red global (GCLK0-3). La tarjeta de
# la practica trae el oscilador de 50 MHz en la 12 (GCLK0).
RELOJES_MAX2 = [12, 14, 62, 64]
RELOJ_MAX2_OMISION = 12
# El reset va por omision a la 44 (DEV_CLRn): es una I/O de usuario que la
# tabla de Intel aparta para un borrado global, y como ese borrado queda apagado
# (lo normal en Quartus), funciona como entrada comun. Es la misma pata que
# elige el planificador de pines ("preferidos" de encapsulados.py), y deja
# libres las 74 I/O comunes para la maquina. La 43 (DEV_OE) o cualquier I/O de
# usuario tambien sirven.
RESET_MAX2_OMISION = 44
RESETS_ESPECIALES_MAX2 = [43, 44]

# Topes de la tabla: el estado es un byte y el indice de la tabla de 12 bits
# (4096 renglones, 4 KB de memoria de programa).
BITS_ESTADO_MAXIMOS = 8
BITS_FILA_MAXIMOS = 12
SALIDAS_MAXIMAS = 16

ARCHIVOS_FPGA = ["fpga/maquina.vhd", "fpga/divisor.vhd", "fpga/maquina_max2.vhd",
                 "fpga/tb_maquina.vhd", "fpga/maquina_max2.qsf", "fpga/maquina_max2.qpf"]


# ===================================================================== la maquina

def _maquina(fuente):
    """La Machine de la fuente: acepta el dict de Machine.from_dict o una Machine."""
    return fuente if isinstance(fuente, Machine) else Machine.from_dict(fuente)


def como_dict(fuente):
    """El dict de la maquina (con "inicial" si lo trae).

    Existe porque contadores.simular y vhdl_fsm.banco_de_prueba piden el dict,
    y la ventana puede pasar una Machine ya construida.
    """
    if isinstance(fuente, dict):
        return fuente
    m = fuente
    estados = []
    for st in m.states:
        estado = {"name": st.name, "code": st.code, "label": st.label}
        if st.out is not None:
            estado["out"] = st.out
        estados.append(estado)
    transiciones = []
    for t in m.transitions:
        transicion = {"from": t.src, "in": t.inp, "to": t.dst}
        if t.out is not None:
            transicion["out"] = t.out
        transiciones.append(transicion)
    return {"name": m.name, "kind": m.kind, "inputs": list(m.inputs),
            "state_bits": list(m.state_bits), "outputs": list(m.outputs),
            "states": estados, "transitions": transiciones}


class TablaMaquina:
    """La maquina como tablas de numeros, lista para grabarse en memoria.

    nombre, tipo           titulo de la maquina y "moore" o "mealy"
    entradas, bits, salidas  nombres; el primero de cada lista es el bit mas alto
    inicial                codigo (numero) del estado inicial
    siguiente              lista de 2^(bits + entradas) codigos: el renglon
                           (codigo << n_entradas) | entradas dice a donde va.
                           Un codigo que no es de ningun estado, o una
                           transicion que falta, va al inicial (como el
                           `when others` de vhdl_fsm.por_tabla).
    tabla_salidas          Moore: un numero por codigo; Mealy: uno por renglon
                           de `siguiente`. Vacia si la maquina no tiene salidas.
    nombres, etiquetas     {codigo: nombre del estado} y {codigo: etiqueta}
    """

    def __init__(self, fuente):
        m = _maquina(fuente)
        self.nombre = m.name
        self.tipo = m.kind
        self.entradas = list(m.inputs)
        self.bits = list(m.state_bits)
        self.salidas = list(m.outputs)
        por_codigo = {st.code: st for st in m.states}
        por_nombre = {st.name: st for st in m.states}
        inicial = m.states[0]
        nombre_inicial = fuente.get("inicial") if isinstance(fuente, dict) else None
        if nombre_inicial in por_nombre:
            inicial = por_nombre[nombre_inicial]
        self.inicial = int(inicial.code, 2)
        self.nombres = {int(st.code, 2): st.name for st in m.states}
        self.etiquetas = {int(st.code, 2): st.label for st in m.states}

        self.siguiente = []
        self.tabla_salidas = []
        for codigo in range(1 << self.n_bits):
            estado = por_codigo.get(format(codigo, f"0{self.n_bits}b"))
            if self.salidas and self.tipo != "mealy":
                salida = estado.out if estado is not None and estado.out else None
                self.tabla_salidas.append(int(salida, 2) if salida else 0)
            for combo in range(1 << self.n_entradas):
                texto = format(combo, f"0{self.n_entradas}b") if self.n_entradas else ""
                t = m.next_state(estado.name, texto) if estado is not None else None
                destino = por_nombre.get(t.dst) if t is not None else None
                self.siguiente.append(int(destino.code, 2) if destino is not None
                                      else self.inicial)
                if self.salidas and self.tipo == "mealy":
                    self.tabla_salidas.append(int(t.out, 2) if t is not None and t.out else 0)

    @property
    def n_entradas(self):
        return len(self.entradas)

    @property
    def n_bits(self):
        return len(self.bits)

    @property
    def n_salidas(self):
        return len(self.salidas)

    def fila(self, codigo, entradas):
        """El renglon de `siguiente`: el estado en los bits altos, las entradas en los bajos."""
        return (codigo << self.n_entradas) | entradas

    def bits_de_fila(self):
        return self.n_bits + self.n_entradas

    # Las tres que siguen existen para que asm.py escriba los mismos comentarios
    # y renglones que el C sin importar este modulo (kit_fsm ya importa asm).
    def comentario(self, prefijo):
        """La tabla de estados como comentario del lenguaje (`//`, `;`, `#`)."""
        return _tabla_comentada(self, prefijo)

    def descripcion(self):
        """Una linea: tipo, cuantos estados, entradas, bits de estado y salidas."""
        return _descripcion(self)

    def renglones_numericos(self, valores, por_estado, ancho_hex, sangria, separador,
                            comentario, al_final=""):
        """Los numeros de una tabla, un renglon de texto por estado (ver
        _renglones_de_tabla)."""
        return _renglones_de_tabla(valores, self, por_estado, ancho_hex, sangria, separador,
                                   comentario, al_final)


def tabla_de_maquina(fuente):
    """La TablaMaquina de la fuente (dict o Machine)."""
    return TablaMaquina(fuente)


def _revisar_tamano(tabla):
    """Bloqueo si la maquina no cabe en las tablas de los microcontroladores."""
    if tabla.n_bits > BITS_ESTADO_MAXIMOS:
        raise Bloqueo(f"la maquina tiene {tabla.n_bits} bits de estado y el programa guarda "
                      f"el estado en un byte ({BITS_ESTADO_MAXIMOS} bits)")
    if tabla.bits_de_fila() > BITS_FILA_MAXIMOS:
        raise Bloqueo(f"la tabla de siguiente estado tendria {1 << tabla.bits_de_fila()} "
                      f"renglones ({tabla.n_bits} bits de estado + {tabla.n_entradas} "
                      f"entradas); el tope es {1 << BITS_FILA_MAXIMOS}")
    if tabla.n_salidas > SALIDAS_MAXIMAS:
        raise Bloqueo(f"la maquina tiene {tabla.n_salidas} salidas y el programa las guarda "
                      f"en 16 bits")


# ===================================================================== senales y pines

def senales(fuente, placa=None):
    """[(nombre, direccion)] de la maquina, para el planificador de pines.

    Entradas ("entrada"), luego los bits de estado y las salidas ("salida"):
    los bits de estado van a LEDs, asi se ve el numero del contador. Con
    placa="max2" van primero ("clk", "reloj") y ("rst", "reset"), porque en la
    MAX II el reloj y el reset son patas de la tarjeta; en el PIC el reloj es el
    oscilador interno y el reset es MCLR, y en Arduino el reset es su boton,
    asi que esas placas no los piden. Sin placa, sin reloj ni reset.
    """
    m = _maquina(fuente)
    lista = [(e, "entrada") for e in m.inputs]
    lista += [(q, "salida") for q in m.state_bits]
    lista += [(s, "salida") for s in m.outputs]
    if placa == "max2":
        lista = [("clk", "reloj"), ("rst", "reset")] + lista
    return lista


class _Senales:
    """Lo que piden asignar_pines, con_pines y kit.pines_en_orden de un circuito:
    los nombres de las entradas y de las salidas. Aqui las salidas son los bits
    de estado seguidos de las salidas de la maquina."""

    def __init__(self, entradas, salidas):
        self.entradas = list(entradas)
        self.salidas = list(salidas)

    @property
    def n_entradas(self):
        return len(self.entradas)

    @property
    def n_salidas(self):
        return len(self.salidas)


def _mapa_del_planificador(fuente, clave, pines):
    """{senal: pin} de la configuracion. Una lista (de --pines o de un proyecto
    viejo) se lee en el orden de `senales`, como lo hace la ventana."""
    if not pines:
        return {}
    if isinstance(pines, dict):
        return dict(pines)
    nombres = [n for n, _d in senales(fuente, clave)]
    return dict(zip(nombres, pines))


def _renglones(tabla, clave, mapa, apartados=()):
    """Reparte entradas, bits de estado y salidas en los pines de la placa.

    Respeta los pines del planificador y completa los que falten con los
    siguientes libres de placas.py. `apartados` son pines que ya tomaron el
    reloj o el reset y que ninguna otra senal puede usar. ValueError si un pin
    del usuario no sirve; Bloqueo si la placa no alcanza.
    """
    senales_io = _Senales(tabla.entradas, tabla.bits + tabla.salidas)
    nombres = senales_io.entradas + senales_io.salidas
    info = dict(placas.PLACAS_CON_PINES[clave])
    info["entradas"] = [p for p in info["entradas"] if p not in apartados]
    info["salidas"] = [p for p in info["salidas"] if p not in apartados]
    propios = {s: p for s, p in mapa.items() if s in nombres}
    for senal, pin in propios.items():
        if pin in apartados:
            raise ValueError(f"{info['titulo']}: el pin {pin} ya es del reloj o del reset; "
                             f"{senal} necesita otro")
    if propios:
        elegidos = kit.pines_en_orden(senales_io, info, propios)
        info = con_pines(senales_io, info, elegidos)
    return asignar_pines(senales_io, info)


def _control_max2(mapa, valores):
    """(pin del reloj, pin del reset o None) de la MAX II, revisados.

    El reloj solo acepta una GCLK (12, 14, 62, 64). El reset acepta la 44
    (DEV_CLRn, la de omision), la 43 (DEV_OE) o una I/O de usuario; con el
    ajuste "sin reset" no lleva pata. ValueError con el motivo.
    """
    titulo = placas.EPM240["titulo"]
    clk = mapa.get("clk", RELOJ_MAX2_OMISION)
    if clk not in RELOJES_MAX2:
        raise ValueError(f"{titulo}: el reloj (clk) va en una pata de reloj global (GCLK): "
                         f"12, 14, 62 o 64; se pidio la {clk}")
    if valores["reset"] == "sin reset":
        return clk, None
    rst = mapa.get("rst", RESET_MAX2_OMISION)
    validos = set(placas.EPM240["entradas"]) | set(placas.EPM240["salidas"])
    validos |= set(RESETS_ESPECIALES_MAX2)
    if rst not in validos:
        raise ValueError(f"{titulo}: el reset (rst) va en la 44 (DEV_CLRn), la 43 (DEV_OE) "
                         f"o una I/O de usuario; la {rst} no sirve")
    return clk, rst


# ===================================================================== comentarios

def _seguro(texto):
    """Una etiqueta de estado dentro de un comentario o una cadena: solo ASCII
    imprimible, sin cerrar el comentario de C ni la cadena."""
    limpio = "".join(c if 32 <= ord(c) < 127 else "?" for c in str(texto))
    return limpio.replace("*/", "* /").replace("\\", "/").replace('"', "'")


def _binario(valor, ancho):
    return format(valor, f"0{ancho}b") if ancho else ""


def _tabla_comentada(tabla, comentario):
    """La tabla de estados como comentario: un renglon por estado con su codigo,
    a donde va con cada combinacion de entradas y sus salidas."""
    ne, nb = tabla.n_entradas, tabla.n_bits
    combos = [_binario(c, ne) for c in range(1 << ne)]
    ancho_nombre = max([len("estado")] + [len(n) for n in tabla.nombres.values()])
    ancho_celda = max([len(c) for c in combos] + [len(n) for n in tabla.nombres.values()])
    if tabla.tipo == "mealy" and tabla.salidas:
        ancho_celda += 1 + tabla.n_salidas
    if ne:
        titulo_combos = "  ".join(c.ljust(ancho_celda) for c in combos)
        encabezado = (f"{comentario}   (codigo = {' '.join(tabla.bits)}; columnas = "
                      f"{' '.join(tabla.entradas)}"
                      + ("; celda = siguiente/salidas" if tabla.tipo == "mealy" and tabla.salidas
                         else "") + ")")
    else:
        titulo_combos = "siguiente"
        encabezado = f"{comentario}   (codigo = {' '.join(tabla.bits)}; sin entradas)"
    lineas = [encabezado]
    fila_titulo = f"{'estado'.ljust(ancho_nombre)}  {'codigo'.ljust(max(nb, 6))}  {titulo_combos}"
    if tabla.salidas and tabla.tipo != "mealy":
        fila_titulo += f"  salidas ({' '.join(tabla.salidas)})"
    lineas.append(f"{comentario}   {fila_titulo}".rstrip())
    for codigo in sorted(tabla.nombres):
        celdas = []
        for combo in range(1 << ne):
            fila = tabla.fila(codigo, combo)
            celda = tabla.nombres.get(tabla.siguiente[fila], "?")
            if tabla.tipo == "mealy" and tabla.salidas:
                celda += "/" + _binario(tabla.tabla_salidas[fila], tabla.n_salidas)
            celdas.append(celda.ljust(ancho_celda))
        texto = (f"{tabla.nombres[codigo].ljust(ancho_nombre)}  "
                 f"{_binario(codigo, nb).ljust(max(nb, 6))}  " + "  ".join(celdas))
        if tabla.salidas and tabla.tipo != "mealy":
            texto += "  " + _binario(tabla.tabla_salidas[codigo], tabla.n_salidas)
        etiqueta = tabla.etiquetas[codigo]
        if etiqueta != tabla.nombres[codigo]:
            texto += f"   ({_seguro(etiqueta)})"
        lineas.append(f"{comentario}   {texto}".rstrip())
    lineas.append(f"{comentario}   Estado inicial: {tabla.nombres[tabla.inicial]} "
                  f"({_binario(tabla.inicial, nb)}).")
    return "\n".join(lineas)


def _renglones_de_tabla(valores_por_fila, tabla, por_estado, ancho_hex, sangria, separador,
                        comentario, al_final=""):
    """Los numeros de una tabla, un renglon de texto por codigo de estado.

    por_estado   True: un numero por estado (salidas Moore); False: uno por
                 cada combinacion de entradas (siguiente estado y salidas Mealy).
    Cada renglon termina con un comentario que dice de que estado es.
    """
    lineas = []
    por_renglon = 1 if por_estado else 1 << tabla.n_entradas
    total = len(valores_por_fila)
    for codigo in range(1 << tabla.n_bits):
        inicio = codigo * por_renglon
        numeros = [f"0x{v:0{ancho_hex}X}" for v in valores_por_fila[inicio:inicio + por_renglon]]
        ultimo = inicio + por_renglon == total
        coma = al_final if ultimo else separador
        nombre = tabla.nombres.get(codigo)
        nota = (f"{_binario(codigo, tabla.n_bits)} {nombre} ({_seguro(tabla.etiquetas[codigo])})"
                if nombre else f"{_binario(codigo, tabla.n_bits)} sin usar")
        lineas.append(f"{sangria}{', '.join(numeros)}{coma}   {comentario} {nota}")
    return lineas


def _descripcion(tabla):
    tipo = "Moore" if tabla.tipo != "mealy" else "Mealy"
    entradas = ", ".join(tabla.entradas) or "ninguna"
    salidas = ", ".join(tabla.salidas) or "ninguna (el estado es lo que se ve)"
    return (f"Maquina {tipo} de {len(tabla.nombres)} estados. Entradas: {entradas}. "
            f"Estado: {' '.join(tabla.bits)}. Salidas: {salidas}.")


def _texto_frecuencia(f):
    return reloj.formato(f, "Hz")


# ===================================================================== PIC 18F en C

def _metodo_c(valores):
    return "timer0" if valores.get("retardo") == "Timer0" else "delay"


def _metodo_asm(valores):
    return "timer0" if valores.get("retardo") == "Timer0" else "subrutina"


def _por_puerto(tabla, renglones):
    """{puerto: [(bit del puerto, senal, 'estado' o 'salidas', bit de origen)]}
    de cada senal que se escribe: los bits de estado y las salidas."""
    puertos = {}
    for r in renglones:
        if r["direccion"] != "salida":
            continue
        p, bit = _puerto(r["pin"])
        if r["senal"] in tabla.bits:
            origen, desde = "estado", tabla.n_bits - 1 - tabla.bits.index(r["senal"])
        else:
            origen, desde = "salidas", tabla.n_salidas - 1 - tabla.salidas.index(r["senal"])
        puertos.setdefault(p, []).append((bit, r["senal"], origen, desde))
    return puertos


def c_pic18(tabla, chip, renglones, valores):
    """Archivo .c completo para XC8: la maquina en un PIC 18F.

    El estado vive en una variable; el siguiente estado sale de un arreglo
    const (memoria de programa) indexado por estado y entradas; el reloj de la
    maquina son dos esperas de medio periodo (reloj.c_pic18_retardo, por
    instrucciones o con el Timer0). ValueError si el retardo no se puede.
    """
    info = placas.PIC[chip]
    fosc, texto_reloj, linea_oscilador = micros.reloj_pic(chip, valores)
    f = valores["frecuencia_hz"]
    metodo = _metodo_c(valores)
    retardo = reloj.c_pic18_retardo(fosc, f, metodo)
    entradas_en_bajo = ajustes.entradas_invertidas(valores)
    salidas_en_bajo = ajustes.salidas_invertidas(valores)
    entradas = [r for r in renglones if r["direccion"] == "entrada"]
    puertos = ["A", "B", "C", "D", "E"]
    ne, nb, ns = tabla.n_entradas, tabla.n_bits, tabla.n_salidas
    tipo_fila = "uint8_t" if tabla.bits_de_fila() <= 8 else "uint16_t"
    tipo_salidas = "uint8_t" if ns <= 8 else "uint16_t"
    mealy = tabla.tipo == "mealy"

    def pata(pin):
        return f"{pin} (pata {info['patas'][pin]})"

    if valores.get("mclr") == "entrada RE3":
        texto_reset = ("sin reset externo (pata 1 = RE3): la maquina arranca en el estado "
                       "inicial al encender")
    else:
        texto_reset = ("MCLR (pata 1, 10 kOhm a VDD): un pulso a GND reinicia el PIC y la "
                       "maquina vuelve al estado inicial")
    if entradas_en_bajo:
        nota = (" * Entradas activas en bajo: cada boton va de la pata a GND y presionado vale 1.\n"
                " * En PORTB se usa la pull-up interna; en otro puerto, 10 kOhm a VDD.")
    else:
        nota = (" * Cada entrada necesita su resistencia de 10 kOhm a GND (pull-down) para no\n"
                " * quedar flotando cuando el interruptor esta abierto.")
    if salidas_en_bajo:
        nota += ("\n * Salidas activas en bajo: el LED va de VDD a la pata (con su resistencia)\n"
                 " * y enciende cuando el bit vale 1.")
    if not ne:
        nota = " * La maquina no tiene entradas: solo avanza con el reloj."
        if salidas_en_bajo:
            nota += ("\n * Salidas activas en bajo: el LED va de VDD a la pata (con su "
                     "resistencia)\n * y enciende cuando el bit vale 1.")

    t = [f"""\
/*
 * {_seguro(tabla.nombre)} en {info['titulo']} -- generado por ktool {__version__}
 * {_descripcion(tabla)}
 * Compilador: MPLAB XC8 (proyecto de MPLAB X para {info['titulo']}).
 * Reloj del PIC: {texto_reloj}.
 * Reloj de la maquina: {_texto_frecuencia(f)}, un estado por periodo. Cada periodo son dos
 * esperas de medio periodo ({'Timer0' if metodo == 'timer0' else '__delay_ms / __delay_us'}).
 * Reset: {texto_reset}.
 *
 * Tabla de estados:
{_tabla_comentada(tabla, ' *')}
 *
 * Mapeo de pines (los bits de estado van a LEDs: se ve el numero del estado):
{tabla_de_pines(renglones, ' *', pata)}
 *
{nota}
 */

#include <xc.h>
#include <stdint.h>

{micros.config_pic(chip, valores)}

{retardo['definiciones']}
"""]
    if ne:
        t.append(f"#define NUM_ENTRADAS {ne}u      // bits de entrada: "
                 f"{', '.join(tabla.entradas)}")
    t.append(f"#define ESTADO_INICIAL 0x{tabla.inicial:02X}u   // "
             f"{tabla.nombres[tabla.inicial]} ({_binario(tabla.inicial, nb)})")
    t.append("")
    if ne:
        t.append(f"// Siguiente estado: SIGUIENTE[(estado << {ne}) | entradas]. Un renglon por "
                 "codigo de estado,")
        t.append(f"// una columna por combinacion de {' '.join(tabla.entradas)} "
                 f"({', '.join(_binario(c, ne) for c in range(1 << ne))}). Los codigos sin "
                 "usar van al inicial.")
    else:
        t.append("// Siguiente estado: SIGUIENTE[estado]. Los codigos sin usar van al inicial.")
    t.append("// const: XC8 guarda el arreglo en la memoria de programa, no en la RAM.")
    t.append(f"static const uint8_t SIGUIENTE[{len(tabla.siguiente)}] = {{")
    t += _renglones_de_tabla(tabla.siguiente, tabla, False, 2, "    ", ",", "//")
    t.append("};")
    if ns:
        ancho = 2 if ns <= 8 else 4
        t.append("")
        if mealy:
            t.append(f"// Salidas Mealy: SALIDAS[(estado << {ne}) | entradas], "
                     f"{tabla.salidas[0]} es el bit {ns - 1}." if ne else
                     f"// Salidas Mealy: SALIDAS[estado], {tabla.salidas[0]} es el bit {ns - 1}.")
        else:
            t.append(f"// Salidas Moore: SALIDAS[estado], {tabla.salidas[0]} es el bit {ns - 1} "
                     f"y {tabla.salidas[-1]} el bit 0.")
        t.append(f"static const {tipo_salidas} SALIDAS[{len(tabla.tabla_salidas)}] = {{")
        t += _renglones_de_tabla(tabla.tabla_salidas, tabla, not mealy, ancho, "    ", ",", "//")
        t.append("};")

    # --- configurar
    tris = {p: 0 for p in puertos}
    for r in entradas:
        p, bit = _puerto(r["pin"])
        tris[p] |= 1 << bit
    t.append(f"""
// Explicito antes de arrancar: reloj del PIC, lo analogico apagado, la
// direccion de cada pata y el temporizador del retardo.
static void configurar(void)
{{
{linea_oscilador}
{micros.ANALOGICO_PIC[chip]}""")
    for k, p in enumerate(puertos):
        t.append(f"    LAT{p} = 0x00;" + ("        // salidas en bajo antes de habilitarlas"
                                           if k == 0 else ""))
    for k, p in enumerate(puertos):
        t.append(f"    TRIS{p} = 0x{tris[p]:02X};" + ("  // 1 = entrada, 0 = salida" if k == 0 else ""))
    if entradas_en_bajo:
        t += micros.pullups_pic(chip, entradas)
    t.append(retardo["configurar"])
    t.append("}")

    # --- esperar medio periodo
    t.append(f"""
// Medio periodo del reloj de la maquina: T/2 = 1 / (2 x {_texto_frecuencia(f)}).
static void esperar_medio_periodo(void)
{{
{retardo['esperar_medio_periodo']}
}}""")

    # --- leer entradas y fila
    if ne:
        t.append(f"""
// Las entradas como un numero, en el orden de la tabla: {tabla.entradas[0]} es el bit {ne - 1}.
static uint8_t leer_entradas(void)
{{
    uint8_t entradas = 0;""")
        if entradas_en_bajo:
            t.append("    // activas en bajo: la pata en 0 (boton presionado) cuenta como 1")
        negar = "!" if entradas_en_bajo else ""
        for k, r in enumerate(entradas):
            p, bit = _puerto(r["pin"])
            t.append(f"    if ({negar}PORT{p}bits.R{p}{bit}) entradas |= 0x{1 << (ne - 1 - k):02X}u;"
                     f"   // {r['senal']}")
        t.append("    return entradas;\n}")
        if tipo_fila == "uint8_t":
            cuerpo = "    return (uint8_t)((uint8_t)(estado << NUM_ENTRADAS) | entradas);"
        else:
            cuerpo = "    return (uint16_t)(((uint16_t)estado << NUM_ENTRADAS) | entradas);"
        t.append(f"""
// El renglon de la tabla: el estado en los bits altos y las entradas en los bajos.
static {tipo_fila} fila(uint8_t estado, uint8_t entradas)
{{
{cuerpo}
}}""")

    # --- escribir
    por_puerto = _por_puerto(tabla, renglones)
    parametros = "uint8_t estado" + (f", {tipo_salidas} salidas" if ns else "")
    t.append(f"""
// Escribe los bits de estado (LEDs) y las salidas, cada puerto de un golpe.
static void escribir({parametros})
{{""")
    for p in puertos:
        for _bit, senal, origen, desde in por_puerto.get(p, []):
            if desde == 0:
                valor = f"{origen} & 1u"
            else:
                valor = f"({origen} >> {desde}) & 1u"
            t.append(f"    uint8_t out_{senal} = (uint8_t)({valor});")
    if salidas_en_bajo:
        t.append("    // activas en bajo: se escribe el complemento de cada bit")
    for p in puertos:
        if p not in por_puerto:
            continue
        if salidas_en_bajo:
            partes = " | ".join(f"((out_{s} ^ 1u) << {b})" for b, s, _o, _d in por_puerto[p])
        else:
            partes = " | ".join(f"(out_{s} << {b})" for b, s, _o, _d in por_puerto[p])
        t.append(f"    LAT{p} = (uint8_t)({partes});")
    t.append("}")

    # --- main
    if ns:
        indice = "fila(estado, entradas)" if (mealy and ne) else "estado"
        llamada_escribir = f"escribir(estado, SALIDAS[{indice}]);"
    else:
        llamada_escribir = "escribir(estado);"
    siguiente = "SIGUIENTE[fila(estado, entradas)]" if ne else "SIGUIENTE[estado]"
    t.append("""
void main(void)
{
    configurar();
    uint8_t estado = ESTADO_INICIAL;      // al encender y despues de cada reset""")
    # Mealy: la salida del estado inicial ya depende de las entradas
    entradas_antes = bool(ne and ns and mealy)
    if entradas_antes:
        t.append("    uint8_t entradas = leer_entradas();")
    t.append(f"    {llamada_escribir}")
    t.append("""
    while (1) {
        esperar_medio_periodo();          // medio periodo con el reloj en bajo

        // flanco de subida: se leen las entradas (como lo hace un flip-flop)
        // y la tabla da el siguiente estado""")
    if entradas_antes:
        t.append("        entradas = leer_entradas();")
    elif ne:
        t.append("        uint8_t entradas = leer_entradas();")
    t.append(f"        estado = {siguiente};")
    t.append(f"        {llamada_escribir}")
    t.append("""
        esperar_medio_periodo();          // medio periodo con el reloj en alto
    }
}
""")
    return "\n".join(t)


# ===================================================================== Arduino

def arduino(tabla, variante, renglones, valores):
    """Sketch .ino: la maquina en un Arduino Uno/Nano o Mega.

    Las tablas van en la flash (PROGMEM) y se leen con pgm_read_byte. El reloj
    de la maquina es una variable que cambia cada medio periodo (delay() o
    millis(), reloj.arduino_retardo); en cada flanco de subida avanza un estado.
    ValueError si la frecuencia es demasiado alta para loop().
    """
    info = placas.ARDUINO[variante]
    f = valores["frecuencia_hz"]
    metodo = "millis" if valores.get("tiempo") == "millis()" else "delay"
    con_serial = valores.get("serial", "no").startswith("si")
    accion = "reloj = !reloj;\nif (reloj) {\n  avanzar();   // flanco de subida: un estado mas\n}"
    retardo = reloj.arduino_retardo(f, metodo, accion)
    entradas_en_bajo = ajustes.entradas_invertidas(valores)
    salidas_en_bajo = ajustes.salidas_invertidas(valores)
    entradas = [r for r in renglones if r["direccion"] == "entrada"]
    salidas = [r for r in renglones if r["direccion"] == "salida"]
    ne, nb, ns = tabla.n_entradas, tabla.n_bits, tabla.n_salidas
    tipo_fila = "uint8_t" if tabla.bits_de_fila() <= 8 else "uint16_t"
    tipo_salidas = "uint8_t" if ns <= 8 else "uint16_t"
    leer_salida = "pgm_read_byte" if ns <= 8 else "pgm_read_word"
    mealy = tabla.tipo == "mealy"

    notas = []
    if ne and entradas_en_bajo:
        notas += ["Entradas con INPUT_PULLUP: cada boton va de la pata a GND y, presionado,",
                  "cuenta como 1."]
    elif ne:
        notas += ["El ATmega no tiene pull-down interno: pon 10 kOhm de cada entrada a GND."]
    if salidas_en_bajo:
        notas.append("Salidas activas en bajo: el LED va de 5 V a la pata, con su resistencia.")
    notas.append("El boton RESET de la placa reinicia el sketch: la maquina vuelve al estado inicial.")
    if con_serial:
        notas.append("Monitor serie a 9600 baudios: imprime cada estado (D0/D1 quedan para el USB).")
    else:
        notas.append("D0/D1 quedan libres para el Serial (el USB).")
    texto_metodo = ("delay(): mientras espera no hace nada mas" if metodo == "delay"
                    else "millis(): sin detener el loop()")

    t = [f"""\
// {_seguro(tabla.nombre)} en {info['titulo']} -- generado por ktool {__version__}
// Nucleo: Arduino AVR (arduino:avr)
// {_descripcion(tabla)}
// Reloj de la maquina: {_texto_frecuencia(f)}, un estado por periodo; el reloj cambia
// cada medio periodo con {texto_metodo}.
//
// Tabla de estados:
{_tabla_comentada(tabla, '//')}
//
// Mapeo de pines (los bits de estado van a LEDs: se ve el numero del estado):
{tabla_de_pines(renglones, '//')}
//
{chr(10).join('// ' + n for n in notas)}
"""]
    for r in renglones:
        t.append(f"const uint8_t PIN_{r['senal']} = {r['pin']};")
    t.append("")
    if ne:
        t.append(f"const uint8_t NUM_ENTRADAS = {ne};   // bits de entrada: "
                 f"{', '.join(tabla.entradas)}")
    t.append(f"const uint8_t ESTADO_INICIAL = {tabla.inicial};   // "
             f"{tabla.nombres[tabla.inicial]} ({_binario(tabla.inicial, nb)})")
    t.append("")
    if ne:
        t.append(f"// Siguiente estado: SIGUIENTE[(estado << {ne}) | entradas]; un renglon por "
                 "codigo de estado.")
    else:
        t.append("// Siguiente estado: SIGUIENTE[estado].")
    t.append("// PROGMEM: la tabla se queda en la flash y no gasta la RAM (2 KB en el Uno).")
    t.append(f"const uint8_t SIGUIENTE[{len(tabla.siguiente)}] PROGMEM = {{")
    t += _renglones_de_tabla(tabla.siguiente, tabla, False, 2, "  ", ",", "//")
    t.append("};")
    if ns:
        t.append("")
        if mealy:
            t.append(f"// Salidas Mealy por renglon de la tabla; {tabla.salidas[0]} es el bit {ns - 1}.")
        else:
            t.append(f"// Salidas Moore por estado; {tabla.salidas[0]} es el bit {ns - 1}.")
        t.append(f"const {tipo_salidas} SALIDAS[{len(tabla.tabla_salidas)}] PROGMEM = {{")
        t += _renglones_de_tabla(tabla.tabla_salidas, tabla, not mealy, 2 if ns <= 8 else 4,
                                 "  ", ",", "//")
        t.append("};")
    if con_serial:
        etiquetas = ", ".join(f'"{_seguro(tabla.etiquetas.get(c, "-"))}"'
                              for c in range(1 << nb))
        t.append("")
        t.append("// Lo que se imprime de cada codigo de estado (\"-\" = sin usar).")
        t.append(f"const char *const ETIQUETAS[{1 << nb}] = {{{etiquetas}}};")
    t.append("")
    t.append("uint8_t estado = ESTADO_INICIAL;")
    t.append("bool reloj = false;   // el reloj de la maquina: avanza en el flanco de subida")
    t.append(retardo["variables"])

    if ne:
        t.append(f"""
// Las entradas como un numero, en el orden de la tabla: {tabla.entradas[0]} es el bit {ne - 1}.
uint8_t leerEntradas() {{
  uint8_t entradas = 0;""")
        nivel = "LOW" if entradas_en_bajo else "HIGH"
        for k, r in enumerate(entradas):
            t.append(f"  if (digitalRead(PIN_{r['senal']}) == {nivel}) entradas |= {1 << (ne - 1 - k)};"
                     f"   // {r['senal']}")
        t.append("  return entradas;\n}")
        t.append(f"""
// El renglon de la tabla: el estado en los bits altos y las entradas en los bajos.
{tipo_fila} fila(uint8_t entradas) {{
  return (({tipo_fila})estado << NUM_ENTRADAS) | entradas;
}}""")

    activo, inactivo = ("LOW", "HIGH") if salidas_en_bajo else ("HIGH", "LOW")
    parametro = f"{tipo_salidas} salidas" if ns else ""
    t.append(f"""
// Escribe los bits de estado (LEDs) y las salidas.
void escribir({parametro}) {{""")
    for r in salidas:
        if r["senal"] in tabla.bits:
            origen, desde = "estado", nb - 1 - tabla.bits.index(r["senal"])
        else:
            origen, desde = "salidas", ns - 1 - tabla.salidas.index(r["senal"])
        t.append(f"  digitalWrite(PIN_{r['senal']}, (({origen} >> {desde}) & 1) ? "
                 f"{activo} : {inactivo});")
    t.append("}")

    if con_serial:
        t.append(f"""
// Imprime una linea por estado: el codigo en binario y su etiqueta.
void imprimir({'uint8_t entradas' if ne else ''}) {{""")
        if ne:
            t.append(f'  Serial.print(F("{"".join(tabla.entradas)} = "));')
            t.append(f"  for (int8_t b = {ne - 1}; b >= 0; b--) Serial.print((entradas >> b) & 1);")
            t.append('  Serial.print(F("  ->  "));')
        t.append(f'  Serial.print(F("{" ".join(tabla.bits)} = "));')
        t.append(f"  for (int8_t b = {nb - 1}; b >= 0; b--) Serial.print((estado >> b) & 1);")
        t.append('  Serial.print(F("  ("));')
        t.append("  Serial.print(ETIQUETAS[estado]);")
        t.append('  Serial.println(F(")"));')
        t.append("}")

    if ns:
        indice = "fila(entradas)" if (mealy and ne) else "estado"
        llamada_escribir = f"escribir({leer_salida}(&SALIDAS[{indice}]));"
    else:
        llamada_escribir = "escribir();"
    llamada_imprimir = ("imprimir(entradas);" if ne else "imprimir();") if con_serial else ""
    t.append("""
// Un flanco de subida del reloj: leer las entradas, pasar al siguiente estado y mostrarlo.
void avanzar() {""")
    if ne:
        t.append("  uint8_t entradas = leerEntradas();")
        t.append("  estado = pgm_read_byte(&SIGUIENTE[fila(entradas)]);")
    else:
        t.append("  estado = pgm_read_byte(&SIGUIENTE[estado]);")
    t.append(f"  {llamada_escribir}")
    if llamada_imprimir:
        t.append(f"  {llamada_imprimir}")
    t.append("}")

    t.append("\nvoid setup() {")
    modo = "INPUT_PULLUP" if entradas_en_bajo else "INPUT"
    for r in entradas:
        t.append(f"  pinMode(PIN_{r['senal']}, {modo});")
    for r in salidas:
        t.append(f"  pinMode(PIN_{r['senal']}, OUTPUT);")
    if con_serial:
        t.append("  Serial.begin(9600);")
    if ne and (llamada_imprimir or (ns and mealy)):
        t.append("  uint8_t entradas = leerEntradas();")
    t.append(f"  {llamada_escribir}   // el estado inicial")
    if llamada_imprimir:
        t.append(f"  {llamada_imprimir}")
    if retardo["setup"]:
        t.append(retardo["setup"])
    t.append("}\n")
    t.append("void loop() {")
    t.append(retardo["en_loop"])
    t.append("}\n")
    return "\n".join(t)


# ===================================================================== MAX II

def _arquitectura(fuente, metodo):
    """La maquina en VHDL por el metodo del ajuste (los tres de vhdl_fsm)."""
    if metodo == "tabla de estados":
        return vhdl_fsm.por_tabla(fuente)
    if metodo == "diagrama de estados":
        return vhdl_fsm.por_estados(fuente)
    flipflop = metodo[metodo.index("flip-flops ") + len("flip-flops "):].rstrip(")")
    return vhdl_fsm.por_ecuaciones(fuente, flipflop)


def _nombres_internos_max2(tabla, entradas_bajo, salidas_bajo):
    """Los identificadores del nivel superior, para que ninguna senal choque con ellos."""
    nombres = {"maquina_max2", "maquina", "divisor", "tarjeta", "clk_maquina", "rst_interno",
               "divisor_de_reloj", "logica"}
    if entradas_bajo:
        nombres |= {f"ent_{e}".lower() for e in tabla.entradas}
    if salidas_bajo:
        nombres |= {f"sal_{s}".lower() for s in tabla.bits + tabla.salidas}
    for senal in tabla.entradas + tabla.bits + tabla.salidas:
        if senal.lower() in nombres:
            raise ValueError(f"la senal {senal} choca con un nombre del nivel superior de la "
                             "MAX II (VHDL no distingue mayusculas); cambiale el nombre")


def vhdl_max2_maquina(tabla, valores, pin_clk=RELOJ_MAX2_OMISION, pin_rst=RESET_MAX2_OMISION):
    """Nivel superior `maquina_max2` para la tarjeta MAX II.

    Instancia el divisor (reloj.vhdl_divisor, de reloj_hz a frecuencia_hz) y la
    entidad `maquina` de vhdl_fsm. El reset de la tarjeta se adapta al ajuste:
    activo en bajo se invierte, activo en alto pasa tal cual y "sin reset" lo
    amarra a '0' (sin puerto rst). Las entradas y salidas activas en bajo se
    invierten aqui, y la maquina queda igual que su tabla (su banco de prueba
    sigue valiendo).
    """
    entradas_bajo = ajustes.entradas_invertidas(valores)
    salidas_bajo = ajustes.salidas_invertidas(valores)
    _nombres_internos_max2(tabla, entradas_bajo, salidas_bajo)
    reset = valores["reset"]
    calculo = reloj.calcular(valores["reloj_hz"], valores["frecuencia_hz"])
    gclk = RELOJES_MAX2.index(pin_clk) if pin_clk in RELOJES_MAX2 else None

    puertos = ["        clk : in  std_logic"]
    if reset != "sin reset":
        puertos.append("        rst : in  std_logic")
    puertos += [f"        {e} : in  std_logic" for e in tabla.entradas]
    puertos += [f"        {s} : out std_logic" for s in tabla.bits + tabla.salidas]

    senales_internas = [
        "    signal clk_maquina : std_logic;   -- el reloj dividido: un estado por flanco de subida",
        "    signal rst_interno : std_logic;   -- reset activo en alto, como lo piden el divisor y la maquina",
    ]
    if entradas_bajo:
        senales_internas += [f"    signal ent_{e} : std_logic;" for e in tabla.entradas]
    if salidas_bajo:
        senales_internas += [f"    signal sal_{s} : std_logic;" for s in tabla.bits + tabla.salidas]

    if reset == "boton activo en bajo":
        linea_reset = ("    -- boton activo en bajo: presionado pone '0' en la pata\n"
                       "    rst_interno <= not rst;")
        texto_reset = (f"rst (pata {pin_rst}): boton activo en bajo; presionado lleva la maquina "
                       "al estado inicial")
    elif reset == "activo en alto":
        linea_reset = "    rst_interno <= rst;   -- activo en alto: tal cual"
        texto_reset = (f"rst (pata {pin_rst}): activo en alto; con '1' la maquina vuelve al estado "
                       "inicial")
    else:
        linea_reset = ("    -- sin reset: amarrado a '0'. Los registros de la MAX II encienden en 0,\n"
                       "    -- asi que la maquina arranca en el codigo 0, no en su estado inicial.\n"
                       "    rst_interno <= '0';")
        texto_reset = "sin reset (amarrado a '0' adentro)"

    mapa = ["            clk => clk_maquina", "            rst => rst_interno"]
    for e in tabla.entradas:
        mapa.append(f"            {e} => {'ent_' + e if entradas_bajo else e}")
    for s in tabla.bits + tabla.salidas:
        mapa.append(f"            {s} => {'sal_' + s if salidas_bajo else s}")
    inversiones = []
    if entradas_bajo:
        inversiones.append("    -- entradas activas en bajo: el boton presionado (0 en la pata) vale 1")
        inversiones += [f"    ent_{e} <= not {e};" for e in tabla.entradas]
    if salidas_bajo:
        inversiones.append("    -- salidas activas en bajo: el LED enciende con 0 en la pata")
        inversiones += [f"    {s} <= not sal_{s};" for s in tabla.bits + tabla.salidas]

    nombre_gclk = f" (GCLK{gclk})" if gclk is not None else ""
    return f"""\
-- maquina_max2 -- generado por ktool {__version__}
-- Nivel superior para la tarjeta MAX II: {_seguro(tabla.nombre)}
-- clk (pata {pin_clk}{nombre_gclk}): el oscilador de {_texto_frecuencia(valores['reloj_hz'])} de la tarjeta.
--   El divisor (divisor.vhd) lo baja a {_texto_frecuencia(calculo.f_real)}: medio periodo de
--   {reloj.formato(calculo.cuenta_medio_periodo)} ciclos (N = f_entrada / (2 f_salida)).
-- {texto_reset}.
-- Entradas activas en {'bajo' if entradas_bajo else 'alto'}; salidas activas en {'bajo' if salidas_bajo else 'alto'}.
-- La maquina (maquina.vhd) se queda igual que su tabla: su banco de prueba sigue valiendo.
-- Las entradas no se sincronizan con el reloj: con botones a {_texto_frecuencia(valores['frecuencia_hz'])}
-- no hace falta; con senales rapidas conviene un par de flip-flops antes.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity maquina_max2 is
    port (
{(";" + chr(10)).join(puertos)}
    );
end entity maquina_max2;

architecture tarjeta of maquina_max2 is
{chr(10).join(senales_internas)}
begin
{linea_reset}

    divisor_de_reloj : entity work.divisor
        port map (
            clk_in  => clk,
            rst     => rst_interno,
            clk_out => clk_maquina
        );

    logica : entity work.maquina
        port map (
{("," + chr(10)).join(mapa)}
        );
{(chr(10) + chr(10).join(inversiones)) if inversiones else ""}
end architecture tarjeta;
"""


def qsf_maquina(tabla, renglones, valores):
    """Restricciones de Quartus para la maquina en la EPM240: patas, IO_STANDARD
    y las patas sin usar como entradas en alta impedancia (igual que logica.qsf)."""
    return f"""\
# maquina_max2 en {placas.EPM240['titulo']} -- generado por ktool {__version__}
# {_seguro(tabla.nombre)}
# Quartus Prime: abre maquina_max2.qpf y compila. El reloj entra por una pata
# GCLK (la red global de reloj) y el reset por la pata elegida.
#
# Mapeo de pines:
{tabla_de_pines(renglones, '#', lambda p: f'PIN_{p}')}
#
# Las patas son de 3.3 V y NO aguantan 5 V directo: los interruptores de las
# entradas van a 3.3 V.

set_global_assignment -name FAMILY "MAX II"
set_global_assignment -name DEVICE EPM240T100C5
set_global_assignment -name TOP_LEVEL_ENTITY maquina_max2
set_global_assignment -name VHDL_FILE divisor.vhd
set_global_assignment -name VHDL_FILE maquina.vhd
set_global_assignment -name VHDL_FILE maquina_max2.vhd

# El VHDL generado se valido en VHDL-1993 estricto.
set_global_assignment -name VHDL_INPUT_VERSION VHDL_1993
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files

# Las patas que el diseno no usa quedan como entradas en alta impedancia. Por
# omision Quartus las deja como salidas a tierra, y en las placas de practica
# hay LEDs y botones en patas sueltas: un boton a VCC contra una pata en
# tierra es un corto.
set_global_assignment -name RESERVE_ALL_UNUSED_PINS "AS INPUT TRI-STATED"

""" + "\n".join(f"set_location_assignment PIN_{r['pin']} -to {r['senal']}" for r in renglones) \
        + "\n\n" + "\n".join(f'set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to '
                             f"{r['senal']}" for r in renglones) + "\n"


def qpf_maquina():
    return ("# Proyecto de Quartus Prime para la maquina de estados -- generado por ktool\n"
            'PROJECT_REVISION = "maquina_max2"\n')


# ===================================================================== Python

def simulacion_python(tabla):
    """Script autonomo que imprime la secuencia de estados con cada combinacion
    de entradas, a partir de la misma tabla que se graba en las placas."""
    ne, nb = tabla.n_entradas, tabla.n_bits
    renglones = _renglones_de_tabla(tabla.siguiente, tabla, False, 2, "    ", ",", "#", ",")
    nombres = ", ".join(f"{c}: {tabla.nombres[c]!r}" for c in sorted(tabla.nombres))
    etiquetas = ", ".join(f"{c}: {_seguro(tabla.etiquetas[c])!r}" for c in sorted(tabla.etiquetas))
    salidas = ""
    if tabla.salidas:
        salidas = ("\n# Salidas: " + ("una por estado (Moore)" if tabla.tipo != "mealy"
                                      else "una por renglon de SIGUIENTE (Mealy)")
                   + f"; {tabla.salidas[0]} es el bit mas alto.\nSALIDAS = "
                   + repr(tabla.tabla_salidas) + "\n")
    return f'''\
#!/usr/bin/env python3
"""Simulacion de {_seguro(tabla.nombre)} -- generado por ktool {__version__}

{_descripcion(tabla)}
Usa la misma tabla de siguiente estado que se graba en el PIC y en el Arduino.
Solo usa la libreria estandar.

    python simular.py                 la secuencia con cada combinacion de entradas
    python simular.py 01 01 11 00     una entrada por ciclo, desde el estado inicial
"""

import sys

ENTRADAS = {tabla.entradas!r}
BITS = {tabla.bits!r}
SALIDAS_NOMBRES = {tabla.salidas!r}
INICIAL = {tabla.inicial}   # {tabla.nombres[tabla.inicial]}
NOMBRES = {{{nombres}}}
ETIQUETAS = {{{etiquetas}}}
CODIGOS = {{nombre: codigo for codigo, nombre in NOMBRES.items()}}

# Siguiente estado: SIGUIENTE[(codigo << {ne}) | entradas]. Los codigos sin usar van al inicial.
SIGUIENTE = [
{chr(10).join(renglones)}
]
{salidas}

def paso(codigo, entradas):
    """El siguiente estado (codigo) desde `codigo` con `entradas` (numero)."""
    return SIGUIENTE[(codigo << len(ENTRADAS)) | entradas]


def simular(entradas_por_ciclo, inicial=INICIAL):
    """Los nombres de los estados visitados, empezando por el inicial; una
    combinacion de entradas (texto como "01") por ciclo de reloj."""
    codigo = inicial
    visitados = [NOMBRES[codigo]]
    for combo in entradas_por_ciclo:
        codigo = paso(codigo, int(combo, 2) if combo else 0)
        visitados.append(NOMBRES[codigo])
    return visitados


def _texto(nombre):
    """'S5 (5)': el nombre del estado y lo que muestra."""
    return f"{{nombre}} ({{ETIQUETAS[CODIGOS[nombre]]}})"


def main(argumentos):
    if argumentos:
        for combo in argumentos:
            if len(combo) != len(ENTRADAS) or set(combo) - {{"0", "1"}}:
                print(f"{{combo!r}} no es una combinacion de {{len(ENTRADAS)}} bits ({{' '.join(ENTRADAS)}})")
                return 1
        visitados = simular(argumentos)
        print("ciclo  entradas  estado")
        print(f"{{0:5d}}  {{'-':8s}}  {{_texto(visitados[0])}}")
        for ciclo, (combo, nombre) in enumerate(zip(argumentos, visitados[1:]), start=1):
            print(f"{{ciclo:5d}}  {{combo:8s}}  {{_texto(nombre)}}")
        return 0
    vueltas = len(NOMBRES) + 1
    combos = [format(c, "0{ne}b") for c in range(1 << len(ENTRADAS))] if ENTRADAS else [""]
    for combo in combos:
        visitados = simular([combo] * vueltas)
        if ENTRADAS:
            print(f"Con {{''.join(ENTRADAS)}} = {{combo}}, desde el estado inicial:")
        else:
            print("Desde el estado inicial:")
        print("  " + " -> ".join(ETIQUETAS[CODIGOS[nombre]] for nombre in visitados))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


# ===================================================================== el kit

def armar(fuente, config):
    """Arma el kit de la maquina en memoria y lo devuelve como kit.Kit.

    `fuente`: el dict de la maquina (Machine.from_dict, con "inicial" opcional)
    o una Machine. `config`: el ConfigKit de la ventana (elegidas, pines por
    placa, ajustes y archivos editados). Un pin que no sirve es un ValueError
    con el motivo, como en kit.armar; una placa que no alcanza sale bloqueada.
    """
    m = _maquina(fuente)
    validar_nombres(m.inputs + m.outputs, m.state_bits)
    tabla = TablaMaquina(fuente)
    datos = como_dict(fuente)
    k = kit.Kit(m)

    for clave in config.elegidas:
        titulo = kit.TITULO_PLATAFORMA.get(clave, clave)
        if clave in PIC18:
            _armar_pic(k, tabla, clave, fuente, config)
        elif clave in ARDUINOS:
            _armar_arduino(k, tabla, clave, fuente, config)
        elif clave == "max2":
            _armar_max2(k, tabla, datos, config)
        elif clave == "python":
            k.archivos["python/simular.py"] = simulacion_python(tabla)
            k.listo(titulo, "python/simular.py")
        elif clave == "hdl":
            k.bloqueado(titulo, MOTIVO_NO_FSM + "; el VHDL de la maquina sale con la MAX II")
        else:
            k.bloqueado(titulo, MOTIVO_NO_FSM)

    kit._aplicar_editados(k, config.editados)
    k.archivos["LEEME.md"] = _leeme(tabla, k.resumen, config)
    return k


def _armar_pic(k, tabla, chip, fuente, config):
    """El .c y/o el .S de un PIC 18F, o su motivo de bloqueo."""
    info = placas.PIC[chip]
    valores = config.valores(chip)
    mapa = _mapa_del_planificador(fuente, chip, config.pines.get(chip))
    try:
        _revisar_tamano(tabla)
        renglones = _renglones(tabla, chip, mapa)
    except Bloqueo as b:
        k.bloqueado(info["titulo"], str(b))
        return
    rutas = []
    archivos = {}
    lenguajes = ajustes.lenguajes_pic(valores)
    try:
        if "c" in lenguajes:
            rutas.append(f"pic/{chip}.c")
            archivos[rutas[-1]] = c_pic18(tabla, chip, renglones, valores)
        if "asm" in lenguajes:
            rutas.append(f"pic/{chip}.S")
            archivos[rutas[-1]] = asm.pic18_maquina(tabla, chip, renglones, valores)
    except ValueError as e:
        k.bloqueado(info["titulo"], f"el reloj de la maquina no se puede: {e}")
        return
    k.archivos.update(archivos)
    k.pines[info["titulo"]] = renglones
    k.listo(info["titulo"], *rutas)


def _armar_arduino(k, tabla, variante, fuente, config):
    """El sketch de un Arduino, o su motivo de bloqueo."""
    info = placas.ARDUINO[variante]
    valores = config.valores(variante)
    mapa = _mapa_del_planificador(fuente, variante, config.pines.get(variante))
    try:
        _revisar_tamano(tabla)
        renglones = _renglones(tabla, variante, mapa)
    except Bloqueo as b:
        k.bloqueado(info["titulo"], str(b))
        return
    ruta = f"arduino/{variante}/{variante}.ino"
    try:
        texto = arduino(tabla, variante, renglones, valores)
    except ValueError as e:
        k.bloqueado(info["titulo"], f"el reloj de la maquina no se puede: {e}")
        return
    k.archivos[ruta] = texto
    k.pines[info["titulo"]] = renglones
    k.listo(info["titulo"], ruta)


def _armar_max2(k, tabla, datos, config):
    """Los archivos de la MAX II (maquina, divisor, nivel superior, banco de
    prueba y proyecto de Quartus), o su motivo de bloqueo."""
    titulo = placas.EPM240["titulo"]
    valores = config.valores("max2")
    mapa = _mapa_del_planificador(datos, "max2", config.pines.get("max2"))
    clk, rst = _control_max2(mapa, valores)
    apartados = [rst] if rst is not None else []
    try:
        renglones_io = _renglones(tabla, "max2", mapa, apartados)
    except Bloqueo as b:
        k.bloqueado(titulo, str(b))
        return
    if tabla.tipo == "mealy" and tabla.salidas and not valores["metodo"].startswith("ecuaciones"):
        k.bloqueado(titulo, "las salidas Mealy en VHDL solo salen por el metodo de ecuaciones "
                            "(la tabla y el diagrama de estados de vhdl_fsm escriben salidas Moore)")
        return
    try:
        maquina_vhd = _arquitectura(datos, valores["metodo"])
        divisor_vhd = reloj.vhdl_divisor(valores["reloj_hz"], valores["frecuencia_hz"], "divisor")
        top_vhd = vhdl_max2_maquina(tabla, valores, clk, rst)
        banco = vhdl_fsm.banco_de_prueba(datos, vhdl_fsm.estimulo_completo(datos))
    except ValueError as e:
        k.bloqueado(titulo, str(e))
        return
    gclk = RELOJES_MAX2.index(clk)
    control = [{"senal": "clk", "pin": clk, "direccion": "reloj",
                "aviso": f"GCLK{gclk}: el oscilador de la tarjeta"}]
    if rst is not None:
        aviso = {44: "DEV_CLRn como I/O comun (el borrado global queda apagado)",
                 43: "DEV_OE como I/O comun"}.get(rst, "")
        control.append({"senal": "rst", "pin": rst, "direccion": "reset", "aviso": aviso})
    renglones = control + renglones_io
    k.archivos["fpga/maquina.vhd"] = maquina_vhd
    k.archivos["fpga/divisor.vhd"] = divisor_vhd
    k.archivos["fpga/maquina_max2.vhd"] = top_vhd
    k.archivos["fpga/tb_maquina.vhd"] = banco
    k.archivos["fpga/maquina_max2.qsf"] = qsf_maquina(tabla, renglones, valores)
    k.archivos["fpga/maquina_max2.qpf"] = qpf_maquina()
    k.pines[titulo] = renglones
    k.listo(titulo, *ARCHIVOS_FPGA)


# ===================================================================== LEEME

def _leeme(tabla, resumen, config):
    """El LEEME.md del kit de la maquina, en el estilo del de kit.py."""
    lineas = [f"""\
# Kit de hardware: {_seguro(tabla.nombre)}

Generado por ktool {__version__}. {_descripcion(tabla)} Cada placa guarda la
misma tabla de siguiente estado (el renglon es el estado con las entradas) y
avanza un estado por periodo de su reloj.

## Tabla de estados

```
{_tabla_comentada(tabla, '')}
```

## Que se genero
""", "| Plataforma | Estado | Archivos o motivo |", "|---|---|---|"]
    for plataforma, estado, detalle in resumen:
        lineas.append(f"| {plataforma} | {estado} | {detalle} |")
    lineas.append("""
Cada archivo trae arriba su tabla de pines (senal -> pin fisico). Los bits de
estado van a LEDs: asi se ve el numero del estado en cada ciclo.

## El reloj de cada placa
""")
    for clave in config.elegidas:
        if clave in PIC18 + ARDUINOS + ["max2"]:
            valores = config.valores(clave)
            f = _texto_frecuencia(valores["frecuencia_hz"])
            titulo = kit.TITULO_PLATAFORMA[clave]
            if clave == "max2":
                lineas.append(f"- {titulo}: el divisor baja {_texto_frecuencia(valores['reloj_hz'])}"
                              f" a {f}. Metodo VHDL: {valores['metodo']}. Reset: {valores['reset']}.")
            elif clave in PIC18:
                lineas.append(f"- {titulo}: oscilador interno a {valores['oscilador']}, maquina a "
                              f"{f}, retardo {valores['retardo']}. MCLR: {valores['mclr']}.")
            else:
                lineas.append(f"- {titulo}: maquina a {f} con {valores['tiempo']}; el boton "
                              "RESET vuelve al estado inicial.")
    lineas.append("""
## Antes de grabar

1. Corre `python python/simular.py`: imprime la secuencia de estados con cada
   combinacion de entradas. Con argumentos (`python simular.py 01 01 11`) sigue
   una entrada por ciclo.
2. Para la MAX II, el banco de prueba aplica las entradas ciclo por ciclo y
   compara el estado con la simulacion: `ghdl -a maquina.vhd tb_maquina.vhd &&
   ghdl -r tb_maquina`. Despues abre `maquina_max2.qpf` en Quartus: el reloj de
   la tarjeta va en la pata GCLK del .qsf y el reset en la suya.
3. Las entradas necesitan pull-down (10 kOhm a GND), o pull-up si se eligieron
   activas en bajo, o leen basura con el interruptor abierto.
""")
    return "\n".join(lineas)


# ===================================================================== documento

def _calculo_de_placa(clave, valores):
    """(Calculo de reloj.calcular, nota) del reloj de la maquina en una placa.

    MAX II: divide el reloj de la tarjeta. PIC: la entrada es el ciclo de
    instruccion (Fosc/4), lo que cuentan __delay_ms, el Timer0 y la subrutina.
    Arduino: la entrada es 1 MHz, la resolucion de micros(). ValueError si no
    se puede.
    """
    f = valores["frecuencia_hz"]
    if clave == "max2":
        calculo = reloj.calcular(valores["reloj_hz"], f)
        nota = (f"El divisor cuenta ciclos del reloj de la tarjeta "
                f"({_texto_frecuencia(valores['reloj_hz'])}): a la mitad de la cuenta "
                "invierte clk_maquina, y la maquina avanza en cada flanco de subida.")
        return calculo, nota
    if clave in PIC18:
        fosc, _texto, _linea = micros.reloj_pic(clave, valores)
        calculo = reloj.calcular(fosc / 4.0, f)
        retardo = reloj.c_pic18_retardo(fosc, f, _metodo_c(valores))
        nota = (f"La entrada es el ciclo de instruccion: Fosc/4 = "
                f"{_texto_frecuencia(fosc / 4.0)}. Cada medio periodo es una espera de "
                f"{reloj.formato(calculo.cuenta_medio_periodo, 'ciclos')} ({valores['retardo']}); "
                f"con el redondeo del retardo sale {_texto_frecuencia(retardo['f_real'])} "
                f"(error {reloj.formato(retardo['error_pct'], '%')}).")
        return calculo, nota
    retardo = reloj.arduino_retardo(f, "millis" if valores.get("tiempo") == "millis()" else "delay")
    calculo = reloj.calcular(1000000.0, f)
    nota = (f"La entrada es 1 MHz, la resolucion de micros(): cada medio periodo dura "
            f"{reloj.formato(calculo.cuenta_medio_periodo, 'us')} con {valores['tiempo']} "
            f"(f real {_texto_frecuencia(retardo['f_real'])}).")
    return calculo, nota


def seccion_reloj(fuente, config):
    """{titulo de placa: html} con el calculo de la frecuencia de cada placa
    elegida: la tabla de datos de reloj.calcular y la onda cuadrada.

    Es el `extra_por_placa` de render.report.seccion_kit: sale bajo los ajustes
    de cada placa. `fuente` no cambia el calculo (solo depende de los ajustes),
    pero se recibe para que la llamada sea igual que la de armar.
    """
    from ..render.report import boton_copiar
    extra = {}
    for clave in config.elegidas:
        if clave not in PIC18 + ARDUINOS + ["max2"]:
            continue
        titulo = kit.TITULO_PLATAFORMA[clave]
        partes = ["<h4>Reloj de la maquina</h4>"]
        try:
            calculo, nota = _calculo_de_placa(clave, config.valores(clave))
        except ValueError as e:
            partes.append(f"<p class='hint'>{html.escape(str(e))}</p>")
            extra[titulo] = "".join(partes)
            continue
        partes.append(f"<p class='hint'>{html.escape(nota)}</p>")
        partes.append("<table class='shared'><thead><tr><th>Dato</th><th>Valor</th><th></th>"
                      "</tr></thead><tbody>")
        for etiqueta, valor, para_copiar in calculo.renglones():
            partes.append(f"<tr><td>{html.escape(etiqueta)}</td><td>{html.escape(valor)}</td>"
                          f"<td>{boton_copiar(para_copiar)}</td></tr>")
        partes.append("</tbody></table>")
        partes.append(f"<div class='diagram'>{reloj.onda_svg(calculo)}</div>")
        extra[titulo] = "".join(partes)
    return extra
