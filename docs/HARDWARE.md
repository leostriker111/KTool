# Kit de hardware — diseño

Del circuito minimizado al **código que se graba**: el mismo circuito para cada
placa de un laboratorio de sistemas digitales, cada archivo completo y con su
tabla de pines. Se pide con `ktool ... --hw CARPETA`.

Este documento dice qué decide el generador, por qué, y qué se comprobó y con
qué herramienta. El código vive en `ktool/hw/`.

## El alcance

**Solo circuitos combinacionales.** Cada microcontrolador lee, evalúa y escribe
en un ciclo sin fin, sin retardos; el HDL usa asignaciones concurrentes. Las
máquinas de estado (reloj, reset, codificación de estados) necesitan antes que
ktool sepa recibir una; eso es el Release 3 (`docs/TODO.md`). Por eso las patas
GCLK, DEV_OE y DEV_CLRn de la MAX II se dejan libres desde ahora.

**La ecuación es la que eligió el usuario.** `--form` manda igual que en el
documento: `auto` usa la más barata en compuertas, y `sop`, `pos`, `nand` o
`nor` usan esa. En un microcontrolador la forma no cambia el resultado —es la
misma función—, pero el encabezado de cada archivo dice cuál se implementó.

## Las placas

Cada placa es un diccionario en `hw/placas.py`: pines preferidos para entrada,
pines preferidos para salida, y aparte los de **reserva** con el aviso que se
escribe junto a ellos si se llegan a usar. El reparto (`asignar_pines`) toma
entradas primero, luego salidas, y si no alcanza lanza `Bloqueo` con la cuenta.

| placa | lo que se evita, y por qué |
|---|---|
| PIC de 40 patas (18F4550, 18F45K50, 16F877A) | RB6/RB7 (PGC/PGD del PICkit), RA4 (drenador abierto en varios PIC), RC4/RC5 en los 18F (líneas de USB, solo entrada). Entradas en RB0-RB5. |
| 16F628A | RA5 es MCLR (solo entrada). RB6/RB7 quedan de reserva. RA6/RA7 sirven porque se usa el oscilador interno. |
| 16F84A | Solo tiene RA0-RA4 y RB0-RB7. RA4 va de entrada. RB6/RB7 de reserva. |
| ESP32-WROOM-32 | GPIO6-11 (flash), nunca. 34-39 solo entrada y sin pull-down interno. 0, 2, 5, 12, 15 son de *strapping*: reserva con aviso. |
| ESP32-S3 | 19/20 (USB), 43/44 (UART0), 26-32 (flash), 35-37 (PSRAM octal de los módulos R8), 0/3/45/46 (*strapping*). JTAG 39-42 y el LED RGB (38/48) de reserva. |
| ESP32-C3 | 18/19 (USB, por donde se graba), 12-17 (flash). 2, 8, 9 (*strapping*) y 20/21 (UART0) de reserva. Quedan 8 seguros. |
| Arduino Uno/Nano | D0/D1 (el Serial del USB). A6/A7 del Nano son solo analógicos. |
| Blue Pill | PA11/PA12 (USB), PA13/PA14 (SWD), PA15/PB3/PB4 (JTAG), PB2 (BOOT1), PC13-15 (3 mA). Entradas en pines tolerantes a 5 V (FT); salidas en los de 3.3 V. |
| Pico | GP23-25 y GP29 son internos y no salen a la placa. |
| MAX II EPM240T100C5 | Solo las 74 patas que la tabla oficial marca como `IO` (ver abajo). |

Los números de pata de los PIC son del encapsulado DIP. La tabla de la MAX II
salió de *Pin Information for the MAX II EPM240/EPM240G Devices*, versión 1.4
(PT-EPM240-1.4) de Intel/Altera, publicada en docs.altera.com; la prueba
`test_la_max_ii_solo_usa_io_de_usuario` revisa que las 74 + 26 sumen las 100.

## Problemas, y las decisiones que forzaron

**Cada lenguaje ordena los operadores distinto.** El traductor de la sección de
lenguajes (`render/codegen.py`) quita paréntesis por precedencia, con la tabla de
ktool: NOT > AND > XOR > OR. En C y en Python `^` liga *más* fuerte que `&`; en
VHDL mezclar `and` y `or` sin paréntesis ni siquiera compila; y en Python `not A
& B` es `not (A & B)`. Así que el kit tiene su propio emisor
(`modelo.ecuacion`) que pone paréntesis en **toda** operación, y en Python niega
con `x ^ 1` en vez de `not`. Es más feo y no hay forma de que signifique otra
cosa.

**El 16F84A no tiene dónde guardar una ecuación grande.** Escrita tal cual, una
ecuación de 6 entradas con decenas de términos falla de dos formas en XC8:
primero `no space for auto/param` (el 84A tiene 68 bytes de RAM y el compilador
guarda todos los resultados intermedios), y luego, partida en renglones, `can't
find words for psect maintext` (no cabe en sus 1024 palabras: XC8 gratuito
traduce cada `&` y cada `!` a varias instrucciones). La salida fue cambiar la
forma de evaluar en los PIC: las entradas se leen en un byte `x` —con la primera
variable como bit alto, igual que el número de fila— y cada término minimizado
es una comparación de máscara:

```c
if ((x & 0x06) == 0x02) out_Y = 1;   // A'B
```

Unas cinco instrucciones por término sin importar cuántas letras tenga. El caso
peor que antes no cabía (6 entradas, 7 salidas al azar, en NAND) quedó en el 88 %
del 84A. En Arduino y los demás, con memoria de sobra, se queda la ecuación
legible.

**Ni así cabe todo, y el compilador avisa tarde.** Cuatro paridades de 6
variables en NAND son 128 términos. Se midió el costo con XC8 v3.10 (-O1): unas
40 palabras fijas y de 8.7 a 9.3 por término. `micros.palabras_estimadas`
cuenta 45 + 10 por término, y si pasa de la memoria del chip la variante se
bloquea con la cuenta, en vez de entregar un archivo que el compilador va a
rechazar. Comprobado contra el compilador: de 1 a 7 paridades, el 84A y el
628A se bloquean exactamente en los casos en los que XC8 falla, y en ningún
otro.

**Una resistencia de 10 kΩ no es un pull-down para un 74LS.** Una entrada LS en
bajo *empuja* hasta 0.4 mA hacia afuera; sobre 10 kΩ eso son 4 V y la entrada
lee 1. Para quedar bajo VIL = 0.8 V la resistencia no puede pasar de 2 kΩ, así
que la lista de materiales pide 1 kΩ y dice por qué. (En los PIC y en el Arduino
sí van 10 kΩ: sus entradas casi no consumen.)

**La GAL22V10 no tiene macroceldas iguales.** De la pata 14 a la 23 admiten 8,
10, 12, 14, 16, 16, 14, 12, 10 y 8 términos producto. Las salidas que más piden
van a las macroceldas más grandes, y si la suma de productos no cabe se prueba
el complemento (`!Y = ...`), que la GAL implementa con su fusible de polaridad.
Si tampoco, se bloquea y sugiere la MAX II.

**La lista 74LS no se inventó aparte.** Reusa el netlist del armado en
protoboard (`proto/netlist.py`), cuyos pinouts se leyeron de hoja de datos.
Prueba SOP, POS, solo NAND y solo NOR, se queda con la de menos encapsulados, y
antes de escribirla la evalúa contra la tabla de verdad fila por fila.

## Qué se comprobó, y con qué

Con el código final se generaron **21 circuitos** de prueba: uno chico de la
CLI, uno XNOR, uno con salidas constantes, tablas al azar de 4, 5 y 6 entradas
en SOP, NAND y NOR (hasta 24 salidas), los peores casos de memoria del 16F84A y
del 16F628A (6 entradas, 7 y 9 salidas al azar sin *don't cares*), y de 1 a 7
paridades de 6 variables en NAND. Cada archivo pasó por la herramienta real:

| qué | con qué | resultado |
|---|---|---|
| 88 archivos `.c` de PIC (los 5 chips) | MPLAB XC8 v3.10, `-O1`, con los DFP de MPLAB X 6.25 | 88 compilan, sin una advertencia. Los que no caben ya venían bloqueados. |
| 21 sketches de Uno o Mega | `arduino-cli` 1.6 con `arduino:avr` 1.8.8, `--warnings all` | 21 compilan, sin advertencias en el código generado. |
| sketches de ESP32 (WROOM-32, S3, C3) y Blue Pill | `arduino-cli` con `esp32:esp32` 4.0.0 y `STMicroelectronics:stm32` 3.1.0 | 31 compilan (8 circuitos variados en las 4 placas; el C3 bloqueado en el de 16 pines), sin advertencias en el código generado. |
| 21 bancos de prueba VHDL | GHDL 6.0.0, en VHDL-93 **y** VHDL-2008 estrictos, con `-Wall` | 21 recorren todas las combinaciones y coinciden con la tabla, sin una advertencia. |
| 21 síntesis del VHDL | GHDL 6.0.0 `--synth` | 21 sintetizan a compuertas, y **el mismo banco corrido contra el netlist sintetizado** coincide en todas las combinaciones (simulación post-síntesis). |
| 21 bancos de prueba Verilog | Icarus Verilog 12.0 (`-Wall`) | 21 coinciden, sin advertencias. |
| 21 `simular.py` | Python 3.12 | 21 coinciden con la tabla. |

Y en `tests/test_hw.py`, sin herramientas externas, la lógica de cada salida
se evalúa fila por fila contra la tabla en unas 150 tablas al azar (de 2 a 6
variables, las cinco formas, XOR y constantes):

- la ecuación en C, con un evaluador que respeta la precedencia de C;
- las máscaras del PIC, interpretando renglón por renglón lo generado;
- el `main.py` de MicroPython de las cuatro placas, corrido con un módulo
  `machine` de mentira;
- y la simulación en Python, corrida tal cual.

Para saber que esas pruebas sí atrapan errores, se metieron dos a propósito (el
NOT de Python escrito con `not` y una máscara de PIC volteada) y las dos
truenan la prueba.

## La MAX II en particular

El VHDL es lo que Quartus compila para la EPM240, así que tiene su propia pasada:

- **VHDL-1993 estricto.** Es la versión que Quartus usa por omisión, y el `.qsf`
  la fija con `VHDL_INPUT_VERSION VHDL_1993`. El código también pasa en VHDL-2008.
- **Sintetizable, y la síntesis no cambia la función.** GHDL lo baja a compuertas
  y el banco de prueba se corre otra vez *contra ese netlist*: si la síntesis
  interpretara algo distinto, ahí saldría.
- **Siempre cabe.** Cada celda lógica (LE) de la MAX II es una tabla de 4
  entradas: una función de 6 entradas pide a lo más 5. Con los topes de ktool
  (6 entradas, 32 salidas) son 160 de 240 celdas; `logica.celdas_max_ii` lo
  calcula y el kit lo revisa de todos modos, por si un día suben los topes.
- **Las patas sin usar quedan como entradas.** Quartus, si no se le dice nada,
  las deja como salidas a tierra; en las placas de práctica de la EPM240 hay
  LEDs y botones en patas sueltas, y un botón a VCC contra una pata en tierra es
  un corto. El `.qsf` pone `RESERVE_ALL_UNUSED_PINS "AS INPUT TRI-STATED"`.
- **3.3 V.** Las patas de la MAX II no aguantan 5 V directo; el `.qsf` lo
  advierte y dice cómo bajar el nivel si la señal viene de un chip TTL.
- **Las patas de tu placa.** Las placas de práctica traen LEDs y botones en
  patas fijas, así que `--max2-pines 26,28,33,...` pone cada señal donde haga
  falta (primero las entradas, luego las salidas). Cada pata se revisa contra la
  tabla de Intel: VCC, GND y JTAG se rechazan con el motivo, y las GCLK, DEV_OE y
  DEV_CLRn también, para dejarlas libres.

Las asignaciones del `.qsf` no se pudieron leer del manual de Intel (sus páginas
redirigen a un 404), así que se confirmaron contra archivos que escribió el
propio Quartus: `RESERVE_ALL_UNUSED_PINS` en el `.qsf` de una MAX II guardado por
Quartus Prime 20.1.1 Lite (también confirma que esa versión todavía soporta la
familia), `PROJECT_OUTPUT_DIRECTORY output_files` en uno de un EPM240T100C5, y
`VHDL_INPUT_VERSION VHDL_1993` junto con el valor por omisión
`RESERVE_ALL_UNUSED_PINS "As output driving ground"` en un
`assignment_defaults.qdf` generado por Quartus.

## Qué falta

- **Grabarlos.** Nada de esto se ha cargado en una placa de verdad todavía. Las
  matemáticas están comprobadas; el armado no.
- **WinCUPL y Quartus.** El `.pld` sigue la sintaxis de WinCUPL y el `.qsf` la
  de Quartus Prime, pero ninguno de los dos programas estaba instalado para
  pasarles los archivos. Del lado de la MAX II lo que falta es solo eso: el
  VHDL ya está sintetizado y simulado después de la síntesis (arriba).
- **Las máquinas de estado**, con el Release 3.
- **En la GUI** está el botón *Kit de hardware…*, junto a *Generar documento*:
  usa la tabla que está en pantalla (con varias salidas, cosa que la CLI no
  permite), la forma elegida y, opcional, las patas de la MAX II.

## Cómo se agrega una placa

Una entrada más en el diccionario que le toca en `hw/placas.py`: los pines de
entrada y de salida en orden de preferencia, `reserva` con el aviso de cada pin
que estorba a algo, y `solo_entrada` si los hay. Si es de una familia nueva (no
PIC, no Arduino, no MicroPython), una función en `hw/micros.py` que reciba el
circuito y el reparto y devuelva el texto, y una línea en `hw/kit.py`.
