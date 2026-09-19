# Protoboard — diseño

Del diagrama de compuertas al **armado físico**: qué chips, dónde van, y qué cable va
de dónde a dónde. No es simulación; es la hoja que sigues con la protoboard enfrente.

Este documento es el contrato de la función. Las decisiones de aquí ya están tomadas;
lo que quede abierto vive en la última sección.

## Lo que cambia de raíz

En el papel el costo son **compuertas**. En la mesa el costo son **encapsulados**:

- Un 74LS08 trae *cuatro* AND de dos entradas. Usar una o usar cuatro cuesta lo mismo.
- Un SOP con 3 AND + 1 OR son 4 compuertas y **2 chips** (7408 + 7432).
- Ese mismo SOP en puro NAND son 4 compuertas y **1 chip** (7400).

Por eso `simplify.py` seguirá eligiendo por compuertas —que es lo correcto para la tarea
escrita— pero el protoboard reporta su propio costo **en chips**, y puede ganar una
realización que en el papel perdía.

## Las realizaciones

Hoy el proyecto genera SOP, POS y XOR. Faltan dos, y no sólo su dibujo: **hay que
generarlas**.

| forma | de dónde sale | estructura |
|---|---|---|
| SOP | ya existe | AND-OR |
| POS | ya existe | OR-AND |
| XOR | ya existe | cadena XOR/XNOR |
| **NAND** | nueva, del SOP | NAND de los NAND por término |
| **NOR** | nueva, del POS | NOR de los NOR por término |

La identidad es directa: el NAND de n entradas es el complemento de su producto, así que
el NAND de los NAND por término devuelve la suma de los términos. Dual para NOR.

Dos casos que hay que cuidar:

- **Término de un solo literal.** En `Y = AB + C`, la `C` suelta necesita inversión antes
  del NAND final.
- **Literales negados.** No existen físicamente (ver abajo).

El usuario **decide cuáles realizaciones deja, cuáles quita, y cuál inspira el
protoboard**. Por omisión se generan todas y el armado sale de la recomendada.

## Los inversores

El diagrama de hoy asume rieles con los literales negados disponibles. **En la protoboard
no existen.** La herramienta agrega los **7404** que hagan falta, dibuja el cable de la
variable a su negado, y los cuenta en el costo de chips. Es un chip extra casi siempre, y
es lo que de verdad armas.

En las realizaciones NAND/NOR una inversión puede resolverse con un 7404 o amarrando las
entradas de una compuerta libre del chip que ya pusiste. Esa decisión la toma la etapa de
selección, no la de generación.

## Selección de chips — tres modos

1. **Fiel al diagrama.** Una compuerta del chip por cada compuerta dibujada, con el ancho
   que el diagrama muestra: un término de 4 literales pide una AND de 4 entradas (7421).
   Aunque sólo uses una compuerta del encapsulado.
2. **Forzado.** El usuario dice con qué chips quiere armarlo (7408 y 7432, y ya). Los
   términos más anchos se arman en cascada.
3. **Automático.** Toma el ancho **mayor** que el circuito necesita y usa ese chip para
   todo: si el término más grande es de 3, todo va en 7411, y las entradas sobrantes se
   amarran — a Vcc en AND/NAND, a GND en OR/NOR.

En los tres modos, las compuertas libres de un chip ya colocado se reutilizan: es el chip
lo que cuesta, no la compuerta.

## Chips contemplados

Los pinouts viven como **datos**, no como código — un diccionario por chip, igual que
`OPS` en `codegen.py`. Agregar uno es una entrada, no un caso nuevo.

| chip | qué trae | verificado |
|---|---|---|
| 7400 | cuatro NAND de 2 | sí — dos lecturas del datasheet + sn74hc00 |
| 7402 | cuatro NOR de 2 | sí (ojo: las salidas van primero) |
| 7404 | seis inversores | sí |
| 7408 | cuatro AND de 2 | sí |
| 7410 | tres NAND de 3 | sí |
| 7411 | tres AND de 3 | sí |
| 7420 | dos NAND de 4 | sí |
| 7421 | dos AND de 4 | sí |
| 7427 | tres NOR de 3 | sí |
| 7432 | cuatro OR de 2 | sí |
| 7486 | cuatro XOR de 2 | sí — dos datasheets independientes |
| 4075 | tres OR de 3 | sí — tapa el hueco: la serie 74xx no trae OR de 3 |
| 7430 | NAND de 8 | falta |
| 7447 / 7448 | decodificador BCD a 7 segmentos (ánodo / cátodo común) | falta, y hace falta para los displays |
| 7474 / 7476 | flip-flops D y JK | falta, para el Release 3 |
| 74138 | decodificador 3 a 8 | leído, sin meter aún (no es compuerta) |

> **Cómo se verifican.** `herramientas/leer_pinout.py` lee el pinout del PDF de tres
> maneras independientes —el dibujo en texto, la tabla *Pin Functions*, y el dibujo
> vectorial por coordenadas— y si se contradicen no devuelve nada. Entre los varios
> encapsulados de una hoja se queda con el DIP por la convención de la serie: GND en el
> pin n/2 y VCC en el n. Un pin equivocado aquí le cuesta la práctica a alguien; es el
> único dato del proyecto que no se puede sacar de memoria.
>
> Las hojas de la familia **74LS son escaneadas** y no tienen capa de texto: no hay forma
> de leerlas automático. Los pinouts salieron de la familia **74HC**, que es la misma
> patita para estos números y sí trae hojas modernas.

## Los extremos

Todo es elegible por el usuario, y **la polaridad importa**:

| extremo | qué se dibuja | cuándo enciende |
|---|---|---|
| Puntos etiquetados | sólo el riel marcado | — |
| LED + resistencia | LED con su 220 Ω a GND | en alto |
| Display de 7 segmentos, cátodo común | los 7 segmentos + común a GND | en **alto** |
| Display de 7 segmentos, ánodo común | los 7 segmentos + común a Vcc | en **bajo** |
| Display de 16 segmentos, cátodo común | los 16 segmentos + común a GND | en **alto** |
| Display de 16 segmentos, ánodo común | los 16 segmentos + común a Vcc | en **bajo** |

**El detalle que importa:** con ánodo común el segmento prende cuando la señal va en
**bajo**, así que hay que manejar el complemento de la salida. Y el complemento ya está
calculado — es la minimización de los ceros, la misma que el motor produce hoy para armar
el POS. O sea: ánodo común **no cuesta un inversor por segmento**, cuesta usar la otra
ecuación que el motor ya tiene.

## La protoboard

- **Unidad: la de 63 columnas** (830 puntos). Chips a caballo del canal central.
- **Sin colisiones**: dos señales nunca comparten columna; los chips no se enciman.
- **Más compuertas, más tableros**: cuando no cabe se agrega otra protoboard y se dibujan
  los **puentes de + y −** entre los rieles de las dos.
- **Colores** por señal, como ya hace el circuito combinado.

## El dibujo

Cuadraditos, con **relieve ligero** — ese estilo de figura plana que se ve un poquito 3D.
SVG autocontenido, sin dependencias, dentro del mismo reporte HTML.

Además del dibujo va la **lista de cables** (de qué pin de qué chip a qué pin de cuál, con
su color), que es lo que de verdad sigues mientras armas y lo único verificable a mano.

## Cómo se prueba

La función no simula, pero la herramienta sí tiene que **comprobarse a sí misma**:

- El netlist reconstruye el mismo circuito que el diagrama: cada compuerta, cada entrada,
  cada inversor.
- Ningún pin queda al aire ni doblemente manejado.
- Ningún chip se encima con otro; ninguna columna lleva dos señales.
- Todo chip tiene su Vcc y su GND conectados.
- Todas las protoboards quedan unidas por sus puentes de + y −.

## Orden de trabajo

1. ~~**NAND y NOR en el motor**~~ — hecho.
2. ~~**Modelo de chips y netlist**~~ — hecho: pinouts como datos, los tres modos, los
   7404, los extremos con su polaridad.
3. ~~**Colocación y ruteo**~~ — hecho. Los cables van con **ángulos rectos**, por carriles
   repartidos por intervalos (dos cables comparten carril sólo si no se traslapan), y se
   meten en los **agujeros libres** de la columna de cada pin — que para eso son cinco del
   mismo nodo. Y dos señales nunca comparten columna, eso sale de cómo está hecha la
   protoboard.
4. ~~**El dibujo**~~ — hecho, con relieve, colores y la lista de cables.
5. **GUI** — falta: los botones para elegir realización, modo y extremos. La CLI ya
   los tiene (`--proto`, `--proto-modo`, `--proto-chips`, `--proto-extremos`).

## Abierto

- Más componentes y más tamaños de protoboard: *capaz somos limitados de pensamiento*.
  Candidatos: matriz de LEDs, display de 14 segmentos, barra de LEDs, protoboard de media
  y de 63 dobles.
- Qué hacer cuando ni con varias protoboards cabe: ¿avisar y parar, o dibujar hasta donde
  llegue?
- Si conviene que el modo forzado acepte chips que el circuito no pidió, para armar con lo
  que uno tenga en la caja.
