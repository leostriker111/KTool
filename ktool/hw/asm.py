"""Ensamblador para los PIC 18F (18F45K50 y 18F4550), con pic-as.

pic-as es el ensamblador que viene con XC8 desde la version 2.20 (el MPASM de
antes ya no existe en MPLAB X 6). Cada funcion devuelve el texto de un archivo
.S: con S mayuscula pic-as pasa el archivo por el preprocesador, que es lo que
hace funcionar `#include <xc.inc>` (los nombres OSCCON, LATD, TRISB...).

Combinacional: igual que el .c, en un ciclo sin fin se leen las entradas a un
byte (fila_, el numero de renglon de la tabla), se compara ese byte contra la
mascara de cada termino minimizado y se escribe cada puerto de un golpe. Un
termino como A'BC es "andlw mascara; xorlw valor": si da cero, coincide.

Se escribe siempre una suma de productos (SOP) o un producto de sumas (POS):
las formas NAND y XOR se traducen a su SOP equivalente y la NOR a su POS, porque
en ensamblador no hay compuertas que imitar, solo comparaciones de bits.
"""

from __future__ import annotations

from .. import __version__
from ..core.simplify import format_product, format_sum, literal_pairs
from . import ajustes, placas, reloj
from .micros import IRCF_PIC18, _puerto, config_pic, reloj_pic
from .modelo import tabla_de_pines

# Registro STATUS: el bit 2 es Z (el resultado de la ultima operacion fue cero)
BIT_Z = 2


# Proteccion de codigo y de escritura, todo apagado. XC8 las pone solo en el
# .c; pic-as avisa por cada palabra de configuracion que falta, asi que se
# escriben. Mismos nombres en el 18F45K50 y el 18F4550.
PROTECCIONES = ["CP0", "CP1", "CP2", "CP3", "CPB", "CPD", "WRT0", "WRT1", "WRT2", "WRT3",
                "WRTC", "WRTB", "WRTD", "EBTR0", "EBTR1", "EBTR2", "EBTR3", "EBTRB"]


def config_asm(chip, valores):
    """Los '#pragma config' del .c pasados a la directiva CONFIG de pic-as.

    Son los mismos bits que el archivo en C, para que los dos programas
    arranquen igual: se convierten linea por linea, comentario incluido.
    """
    lineas = []
    for renglon in config_pic(chip, valores).splitlines():
        if not renglon.startswith("#pragma config"):
            lineas.append("; " + renglon.lstrip("/ "))
            continue
        cuerpo, _, comentario = renglon[len("#pragma config"):].partition("//")
        asignaciones = [a.strip() for a in cuerpo.split(",") if a.strip()]
        for k, a in enumerate(asignaciones):
            nota = f"   ; {comentario.strip()}" if comentario and k == 0 else ""
            lineas.append(f"    CONFIG  {a}{nota}")
    lineas.append("    ; sin proteccion de lectura ni de escritura")
    lineas += [f"    CONFIG  {bit} = OFF" for bit in PROTECCIONES]
    return "\n".join(lineas)


def _forma_para_asm(circuito, salida):
    """La solucion que se escribe: SOP o POS (ver el docstring del modulo)."""
    elegida = circuito.elegidas[salida]
    if elegida.const is not None or elegida.form in ("sop", "pos"):
        return elegida
    forma = "pos" if elegida.form == "nor" else "sop"
    return circuito.soluciones[salida][forma]


def _analogico(chip):
    """Apagar lo analogico, como en el .c: si no, las patas AN leen siempre 0."""
    if chip == "pic18f45k50":
        # ANSELA..ANSELE estan en F5Bh-F5Fh, fuera del banco de acceso (F60h
        # en adelante): se llega a ellas con BANKSEL y el operando ", b".
        lineas = ["    banksel ANSELA"]
        lineas += [f"    clrf    ANSEL{p}, b       ; puerto {p} digital" for p in "ABCDE"]
        lineas += ["    clrf    CM1CON0, a      ; comparadores apagados",
                   "    clrf    CM2CON0, a"]
        return lineas
    return ["    movlw   0x0F",
            "    movwf   ADCON1, a       ; PCFG = 1111: todas las patas AN digitales",
            "    movlw   0x07",
            "    movwf   CMCON, a        ; comparadores apagados"]


def pic18_combinacional(circuito, chip, renglones, valores=None):
    """Archivo .s completo para pic-as: el circuito combinacional en un PIC 18F."""
    valores = valores or {}
    info = placas.PIC[chip]
    puertos = ["A", "B", "C", "D", "E"]
    _frecuencia, texto_reloj, _linea = reloj_pic(chip, valores)
    entradas_en_bajo = ajustes.entradas_invertidas(valores)
    salidas_en_bajo = ajustes.salidas_invertidas(valores)
    entradas = [r for r in renglones if r["direccion"] == "entrada"]
    salidas = [r for r in renglones if r["direccion"] == "salida"]
    n = circuito.n_entradas

    def pata(pin):
        return f"{pin} (pata {info['patas'][pin]})"

    tris = {p: 0 for p in puertos}
    for r in entradas:
        p, bit = _puerto(r["pin"])
        tris[p] |= 1 << bit
    # mascara de salidas por puerto (para escribir e invertir solo esos bits)
    mascara_salidas = {}
    for r in salidas:
        p, bit = _puerto(r["pin"])
        mascara_salidas[p] = mascara_salidas.get(p, 0) | (1 << bit)

    ecuaciones = "\n".join(f";   {s} = {_forma_para_asm(circuito, s).equation}"
                           f"   ({_forma_para_asm(circuito, s).form.upper()})"
                           for s in circuito.salidas)
    frecuencia = ajustes.hz(valores["oscilador"]) if "oscilador" in valores else info["xtal"]
    ircf = IRCF_PIC18[chip][frecuencia]
    osccon = (ircf << 4) | (0b10 if chip == "pic18f4550" else 0b00)

    t = [f"""\
; {circuito.nombre} en {info['titulo']} -- generado por ktool {__version__}
; Ensamblador: pic-as (viene con XC8). Reloj: {texto_reloj}.
;
; Para ensamblar en MPLAB X: proyecto nuevo con el compilador pic-as, y en
; Project Properties > pic-as Linker > Custom linker options escribe
;     -presetVec=0h
; Desde la terminal:
;     pic-as -mcpu={info['titulo'][3:]} -Wl,-presetVec=0h {chip}.S
;
; Ecuaciones (como se evaluan aqui):
{ecuaciones}
;
; Mapeo de pines:
{tabla_de_pines(renglones, ';', pata)}

    PROCESSOR {info['titulo'][3:]}

; Configuracion ANTES del include: xc.inc define nombres de bits como BOR (de
; RCON) que chocarian con los nombres de la configuracion.
{config_asm(chip, valores)}

#include <xc.inc>

; ------------------------------------------------------------ variables
; En el banco de acceso: se leen y escriben con ", a" sin cambiar de banco.
    PSECT udata_acs
fila_:      DS 1        ; las entradas como numero de renglon (bit {n - 1} = {circuito.entradas[0]})"""]
    for p in sorted(mascara_salidas):
        t.append(f"puerto{p}_:   DS 1        ; lo que se va a escribir en LAT{p}")

    t.append(f"""
; ------------------------------------------------------------ arranque
    PSECT resetVec, class=CODE, reloc=2
resetVec:
    goto    inicio

    PSECT code
inicio:
    movlw   0x{osccon:02X}
    movwf   OSCCON, a       ; IRCF = {ircf:03b}: oscilador interno a {ajustes.hz_texto(frecuencia)}""")
    t += _analogico(chip)
    for p in puertos:
        t.append(f"    clrf    LAT{p}, a        ; salidas en bajo antes de habilitarlas")
    for p in puertos:
        t.append(f"    movlw   0x{tris[p]:02X}")
        t.append(f"    movwf   TRIS{p}, a       ; 1 = entrada, 0 = salida")
    if entradas_en_bajo:
        mascara_b = sum(1 << _puerto(r["pin"])[1] for r in entradas if _puerto(r["pin"])[0] == "B")
        if mascara_b and chip == "pic18f45k50":
            t += [f"    movlw   0x{mascara_b:02X}",
                  "    movwf   WPUB, a         ; pull-up interna en las entradas de PORTB",
                  "    bcf     INTCON2, 7, a   ; nRBPU = 0: habilita las pull-up"]
        elif mascara_b:
            t.append("    bcf     INTCON2, 7, a   ; RBPU = 0: habilita las pull-up de PORTB")

    t.append("""
; ------------------------------------------------------------ ciclo
bucle:
    ; 1. leer las entradas a fila_ (el numero de renglon de la tabla)
    clrf    fila_, a""")
    salto = "btfss" if entradas_en_bajo else "btfsc"
    if entradas_en_bajo:
        t.append("    ; activas en bajo: la pata en 0 (boton presionado) cuenta como 1")
    for k, r in enumerate(entradas):
        p, bit = _puerto(r["pin"])
        t.append(f"    {salto}   PORT{p}, {bit}, a")
        t.append(f"    bsf     fila_, {n - 1 - k}, a      ; {r['senal']}")

    t.append("\n    ; 2. evaluar: cada termino es una mascara (que bits mira) y un valor")
    t.append("    ;    (como deben estar). xorlw da cero (Z = 1) cuando coincide.")
    for p in sorted(mascara_salidas):
        t.append(f"    clrf    puerto{p}_, a")
    for r in salidas:
        t += _salida(circuito, r)

    t.append("\n    ; 3. escribir cada puerto de un golpe")
    for p in sorted(mascara_salidas):
        t.append(f"    movf    puerto{p}_, w, a")
        if salidas_en_bajo:
            t.append(f"    xorlw   0x{mascara_salidas[p]:02X}         "
                     "; activas en bajo: se invierten las salidas")
        t.append(f"    movwf   LAT{p}, a")
    t.append("    goto    bucle\n\n    END     resetVec\n")
    return "\n".join(t)


def _salida(circuito, renglon):
    """Las instrucciones de una salida: un bloque de comparacion por termino."""
    s = renglon["senal"]
    p, bit = _puerto(renglon["pin"])
    destino = f"puerto{p}_, {bit}, a"
    sol = _forma_para_asm(circuito, s)
    variables = circuito.entradas
    n = len(variables)

    def peso(v):
        return 1 << (n - 1 - variables.index(v))

    lineas = [f"\n    ; {s} = {sol.equation}"]
    if sol.const is not None:
        if sol.const:
            lineas.append(f"    bsf     {destino}      ; constante 1")
        else:
            lineas.append("    ; constante 0: el bit ya quedo en 0")
        return lineas
    suma_de_productos = sol.form == "sop"
    if not suma_de_productos:   # pos: empieza en 1 y cada factor en 0 lo apaga
        lineas.append(f"    bsf     {destino}      ; POS: vale 1 salvo que un factor valga 0")
    for patron in sol.patterns:
        mascara = valor = 0
        for v, negada in literal_pairs(patron, variables):
            mascara |= peso(v)
            if not negada:
                valor |= peso(v)
        if suma_de_productos:
            comentario = format_product(patron, variables)
            accion = f"bsf     {destino}"
        else:
            comentario = f"{format_sum(patron, variables)} vale 0"
            accion = f"bcf     {destino}"
        lineas += [f"    movf    fila_, w, a      ; {comentario}",
                   f"    andlw   0x{mascara:02X}",
                   f"    xorlw   0x{valor:02X}",
                   f"    btfsc   STATUS, {BIT_Z}, a",
                   f"    {accion}"]
    return lineas


# ===================================================== maquinas de estado

# Registro STATUS: el bit 0 es C (acarreo), el que entra al recorrer con rlcf
BIT_C = 0

POR_QUE_TBLRD = """\
; Por que TBLRD y no una tabla de retlw: en el PIC18 la memoria de programa se
; lee byte por byte con TBLRD y el apuntador de 21 bits TBLPTR. Asi la tabla
; ocupa 1 byte por dato (db), puede estar en cualquier direccion y medir mas
; de 256 bytes. Un computed goto con retlw gasta 2 bytes por dato, obliga a
; duplicar el indice (cada instruccion mide 2 bytes), a cargar PCLATH/PCLATU
; y a cuidar que la tabla no cruce un limite de 256 bytes."""


def _apuntar_tabla(etiqueta):
    """Las instrucciones que dejan TBLPTR al principio de una tabla de la memoria
    de programa (los 21 bits: U, H y L)."""
    return [f"    movlw   low highword({etiqueta})",
            "    movwf   TBLPTRU, a",
            f"    movlw   high({etiqueta})",
            "    movwf   TBLPTRH, a",
            f"    movlw   low({etiqueta})",
            "    movwf   TBLPTRL, a"]


def pic18_maquina(tabla, chip, renglones, valores=None):
    """Archivo .S completo para pic-as: una maquina de estados en un PIC 18F.

    `tabla` es una kit_fsm.TablaMaquina: el siguiente estado de cada renglon
    (estado << entradas | entradas) y las salidas, ya como numeros. El
    siguiente estado se lee de una tabla en memoria de programa con TBLRD (el
    porque va en el comentario del archivo) y el reloj de la maquina son dos
    llamadas a la subrutina de medio periodo de reloj.asm_pic18_retardo
    (lazos anidados o Timer0, segun el ajuste "retardo"). ValueError si el
    retardo no se puede con ese oscilador.
    """
    valores = valores or {}
    info = placas.PIC[chip]
    puertos = ["A", "B", "C", "D", "E"]
    fosc, texto_reloj, _linea = reloj_pic(chip, valores)
    f = valores["frecuencia_hz"]
    metodo = "timer0" if valores.get("retardo") == "Timer0" else "subrutina"
    retardo = reloj.asm_pic18_retardo(fosc, 1.0 / (2 * f), metodo, "medio_periodo")
    entradas_en_bajo = ajustes.entradas_invertidas(valores)
    salidas_en_bajo = ajustes.salidas_invertidas(valores)
    entradas = [r for r in renglones if r["direccion"] == "entrada"]
    salidas = [r for r in renglones if r["direccion"] == "salida"]
    ne, nb, ns = tabla.n_entradas, tabla.n_bits, tabla.n_salidas
    mealy = tabla.tipo == "mealy"

    def pata(pin):
        return f"{pin} (pata {info['patas'][pin]})"

    tris = {p: 0 for p in puertos}
    for r in entradas:
        p, bit = _puerto(r["pin"])
        tris[p] |= 1 << bit
    # de donde sale cada bit que se escribe: el estado o las salidas de la tabla
    por_puerto = {}
    for r in salidas:
        p, bit = _puerto(r["pin"])
        if r["senal"] in tabla.bits:
            variable, desde = "estado_", nb - 1 - tabla.bits.index(r["senal"])
        else:
            desde = ns - 1 - tabla.salidas.index(r["senal"])
            variable = "salidas_" if desde < 8 else "salidash_"
            desde = desde % 8
        por_puerto.setdefault(p, []).append((bit, r["senal"], variable, desde))
    mascara = {p: sum(1 << b for b, _s, _v, _d in lista) for p, lista in por_puerto.items()}

    ircf = IRCF_PIC18[chip][fosc]
    osccon = (ircf << 4) | (0b10 if chip == "pic18f4550" else 0b00)
    if valores.get("mclr") == "entrada RE3":
        texto_reset = "sin reset externo (pata 1 = RE3); arranca en el estado inicial al encender"
    else:
        texto_reset = "MCLR (pata 1, 10 kOhm a VDD): reinicia el PIC y la maquina vuelve al inicial"
    nombre_metodo = "Timer0" if metodo == "timer0" else "lazos anidados"

    t = [f"""\
; {tabla.nombre} en {info['titulo']} -- generado por ktool {__version__}
; {tabla.descripcion()}
; Ensamblador: pic-as (viene con XC8). Reloj del PIC: {texto_reloj}.
; Reloj de la maquina: {reloj.formato(f, 'Hz')}, un estado por periodo: dos llamadas a
; medio_periodo ({nombre_metodo}).
; Reset: {texto_reset}.
;
; Para ensamblar en MPLAB X: proyecto nuevo con el compilador pic-as, y en
; Project Properties > pic-as Linker > Custom linker options escribe
;     -presetVec=0h
; Desde la terminal:
;     pic-as -mcpu={info['titulo'][3:]} -Wl,-presetVec=0h {chip}.S
;
; Tabla de estados:
{tabla.comentario(';')}
;
; Mapeo de pines (los bits de estado van a LEDs: se ve el numero del estado):
{tabla_de_pines(renglones, ';', pata)}
;
{POR_QUE_TBLRD}

    PROCESSOR {info['titulo'][3:]}

; Configuracion ANTES del include: xc.inc define nombres de bits como BOR (de
; RCON) que chocarian con los nombres de la configuracion.
{config_asm(chip, valores)}

#include <xc.inc>

; ------------------------------------------------------------ variables
; En el banco de acceso: se leen y escriben con ", a" sin cambiar de banco.
    PSECT udata_acs
estado_:    DS 1        ; codigo del estado actual ({' '.join(tabla.bits)})"""]
    if ne:
        t.append(f"entradas_:  DS 1        ; las entradas como numero ({' '.join(tabla.entradas)})")
    t.append("fila_:      DS 1        ; renglon de la tabla: byte bajo")
    t.append("filah_:     DS 1        ; renglon de la tabla: byte alto")
    if ns:
        t.append("salidas_:   DS 1        ; salidas de la tabla, bits 7-0")
    if ns > 8:
        t.append("salidash_:  DS 1        ; salidas de la tabla, bits 15-8")
    for p in sorted(por_puerto):
        t.append(f"puerto{p}_:   DS 1        ; lo que se va a escribir en LAT{p}")

    t.append(f"""
; ------------------------------------------------------------ arranque
    PSECT resetVec, class=CODE, reloc=2
resetVec:
    goto    inicio

    PSECT code
inicio:
    movlw   0x{osccon:02X}
    movwf   OSCCON, a       ; IRCF = {ircf:03b}: oscilador interno a {ajustes.hz_texto(fosc)}""")
    t += _analogico(chip)
    for p in puertos:
        t.append(f"    clrf    LAT{p}, a        ; salidas en bajo antes de habilitarlas")
    for p in puertos:
        t.append(f"    movlw   0x{tris[p]:02X}")
        t.append(f"    movwf   TRIS{p}, a       ; 1 = entrada, 0 = salida")
    if entradas_en_bajo:
        mascara_b = sum(1 << _puerto(r["pin"])[1] for r in entradas if _puerto(r["pin"])[0] == "B")
        if mascara_b and chip == "pic18f45k50":
            t += [f"    movlw   0x{mascara_b:02X}",
                  "    movwf   WPUB, a         ; pull-up interna en las entradas de PORTB",
                  "    bcf     INTCON2, 7, a   ; nRBPU = 0: habilita las pull-up"]
        elif mascara_b:
            t.append("    bcf     INTCON2, 7, a   ; RBPU = 0: habilita las pull-up de PORTB")
    t.append(f"    movlw   0x{tabla.inicial:02X}")
    t.append(f"    movwf   estado_, a      ; estado inicial: {tabla.nombres[tabla.inicial]} "
             f"({format(tabla.inicial, f'0{nb}b')})")
    if ne:
        t.append("    call    leer_entradas")
    t.append("    call    escribir")

    t.append("""
; ------------------------------------------------------------ el reloj de la maquina
bucle:
    call    medio_periodo   ; medio periodo con el reloj en bajo

    ; flanco de subida: se leen las entradas (como lo hace un flip-flop) y la
    ; tabla da el siguiente estado""")
    if ne:
        t.append("    call    leer_entradas")
    t.append("    call    calcular_fila")
    t += _apuntar_tabla("tabla_siguiente")
    t.append("    call    leer_tabla")
    t.append("    movwf   estado_, a")
    t.append("    call    escribir")
    t.append("")
    t.append("    call    medio_periodo   ; medio periodo con el reloj en alto")
    t.append("    goto    bucle")

    # --- leer las entradas
    if ne:
        t.append(f"""
; Las entradas a entradas_, en el orden de la tabla: {tabla.entradas[0]} es el bit {ne - 1}.
leer_entradas:
    clrf    entradas_, a""")
        salto = "btfss" if entradas_en_bajo else "btfsc"
        if entradas_en_bajo:
            t.append("    ; activas en bajo: la pata en 0 (boton presionado) cuenta como 1")
        for k, r in enumerate(entradas):
            p, bit = _puerto(r["pin"])
            t.append(f"    {salto}   PORT{p}, {bit}, a")
            t.append(f"    bsf     entradas_, {ne - 1 - k}, a   ; {r['senal']}")
        t.append("    return")

    # --- calcular la fila
    t.append(f"""
; fila = (estado << {ne}) | entradas, en 16 bits (filah_:fila_): el renglon de la tabla.
calcular_fila:
    movf    estado_, w, a
    movwf   fila_, a
    clrf    filah_, a""")
    for _ in range(ne):
        t.append(f"    bcf     STATUS, {BIT_C}, a    ; C = 0: entra un 0 por la derecha")
        t.append("    rlcf    fila_, f, a")
        t.append("    rlcf    filah_, f, a    ; el bit que sale de fila_ entra a filah_")
    if ne:
        t.append("    movf    entradas_, w, a")
        t.append("    iorwf   fila_, f, a     ; las entradas en los bits bajos")
    t.append("    return")

    # --- leer un byte de una tabla
    t.append(f"""
; W = tabla[fila]. TBLPTR ya apunta al principio de la tabla: se le suma la
; fila (con acarreo hasta TBLPTRU) y TBLRD* copia ese byte a TABLAT.
leer_tabla:
    movf    fila_, w, a
    addwf   TBLPTRL, f, a
    movf    filah_, w, a
    addwfc  TBLPTRH, f, a
    movlw   0
    addwfc  TBLPTRU, f, a
    tblrd*
    movf    TABLAT, w, a
    return""")

    # --- escribir estado y salidas
    t.append("""
; Escribe los bits de estado (LEDs) y las salidas, cada puerto de un golpe.
escribir:""")
    if ns:
        if mealy and ne:
            t.append("    call    calcular_fila   ; Mealy: las salidas dependen del estado y las entradas")
        else:
            t += ["    movf    estado_, w, a   ; Moore: las salidas dependen solo del estado",
                  "    movwf   fila_, a",
                  "    clrf    filah_, a"]
        t += _apuntar_tabla("tabla_salidas")
        t += ["    call    leer_tabla", "    movwf   salidas_, a"]
        if ns > 8:
            t += _apuntar_tabla("tabla_salidas_alto")
            t += ["    call    leer_tabla", "    movwf   salidash_, a"]
    for p in sorted(por_puerto):
        t.append(f"    clrf    puerto{p}_, a")
        for bit, senal, variable, desde in por_puerto[p]:
            t.append(f"    btfsc   {variable}, {desde}, a")
            t.append(f"    bsf     puerto{p}_, {bit}, a   ; {senal} -> R{p}{bit}")
        t.append(f"    movf    puerto{p}_, w, a")
        if salidas_en_bajo:
            t.append(f"    xorlw   0x{mascara[p]:02X}         ; activas en bajo: se invierten")
        t.append(f"    movwf   LAT{p}, a")
    t.append("    return")

    # --- el retardo
    t.append("""
; ------------------------------------------------------------ medio periodo""")
    t.append(retardo.rstrip("\n"))

    # --- las tablas
    t.append(f"""
; ------------------------------------------------------------ tablas
; En la memoria de programa, despues del codigo. Cada tabla tiene un numero
; par de bytes (2^n), asi lo que siga queda alineado a palabra.
    PSECT code
tabla_siguiente:   ; renglon = (estado << {ne}) | entradas""")
    t += tabla.renglones_numericos(tabla.siguiente, False, 2, "    db      ", "", ";")
    if ns:
        bajos = [v & 0xFF for v in tabla.tabla_salidas]
        t.append(f"tabla_salidas:     ; {'por renglon (Mealy)' if mealy else 'por estado (Moore)'}"
                 f", bits 7-0")
        t += tabla.renglones_numericos(bajos, not mealy, 2, "    db      ", "", ";")
        if ns > 8:
            altos = [v >> 8 for v in tabla.tabla_salidas]
            t.append("tabla_salidas_alto:   ; bits 15-8")
            t += tabla.renglones_numericos(altos, not mealy, 2, "    db      ", "", ";")
    t.append("\n    END     resetVec\n")
    return "\n".join(t)
