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

| chip | qué trae |
|---|---|
| 7400 | cuatro NAND de 2 |
| 7402 | cuatro NOR de 2 |
| 7404 | seis inversores |
| 7408 | cuatro AND de 2 |
| 7410 | tres NAND de 3 |
| 7411 | tres AND de 3 |
| 7420 | dos NAND de 4 |
| 7421 | dos AND de 4 |
| 7427 | tres NOR de 3 |
| 7432 | cuatro OR de 2 |
| 7486 | cuatro XOR de 2 |

> **Antes de publicar:** cada pinout se verifica contra su hoja de datos y se marca en el
> archivo con la fuente. Un pin equivocado aquí le cuesta la práctica a alguien; es el
> único dato del proyecto que no se puede sacar de memoria.

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

1. **NAND y NOR en el motor**, con su diagrama y sus switches. Independiente y útil solo.
2. **Modelo de chips y netlist** — pinouts como datos, los tres modos de selección, los
   7404, los extremos con su polaridad.
3. **Colocación y ruteo** — colisiones, varias protoboards, puentes de rieles.
4. **El dibujo** con relieve y colores, integrado al reporte.
5. **GUI y CLI** — botones, switches, y elegir qué realización inspira el armado.

## Abierto

- Más componentes y más tamaños de protoboard: *capaz somos limitados de pensamiento*.
  Candidatos: matriz de LEDs, display de 14 segmentos, barra de LEDs, protoboard de media
  y de 63 dobles.
- Qué hacer cuando ni con varias protoboards cabe: ¿avisar y parar, o dibujar hasta donde
  llegue?
- Si conviene que el modo forzado acepte chips que el circuito no pidió, para armar con lo
  que uno tenga en la caja.
