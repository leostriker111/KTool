# Ejemplos

Documentos ya generados, para verlos sin instalar nada. Los `.pdf` se abren aquí
mismo en GitHub; los `.html` son el formato real que produce ktool —interactivo,
con los botones de copiar— y se ven descargándolos.

| Ejemplo | Qué muestra | Ver |
|---|---|---|
| **LED simple** | `Y = B'C + A` con un LED y su resistencia en la salida. Tres encapsulados, cables planchados, puentes de alimentación. | [PDF](led-simple.pdf) · [HTML](led-simple.html) |
| **BCD a 7 segmentos** | Cuatro entradas, siete salidas que comparten términos, display de cátodo común. Nueve encapsulados en dos tableros. | [PDF](bcd-7segmentos.pdf) · [HTML](bcd-7segmentos.html) |

## Cómo se regeneran

El chico sale de una línea de CLI:

```
python -m ktool -n 3 -m 1,4,5,6 -d 2,7 --proto --proto-extremos led \
    --title "Y = B'C + A, armada en protoboard" --out ejemplos/led-simple.html
```

El grande tiene siete salidas, y eso todavía no se puede pedir desde la CLI, así
que va con su script:

```
python ejemplos/bcd_7segmentos.py
```

Los PDF se sacaron imprimiendo el HTML desde el navegador (Ctrl+P → Guardar como
PDF). No hace falta ninguna dependencia: ktool no genera PDF, genera HTML.

## Ojo

El armado en protoboard está **en beta**. Se ve bonito y la lista de cables está
verificada contra la tabla de verdad, pero **nadie lo ha armado todavía en una
mesa de verdad**, y en circuitos grandes el dibujo se enreda
([#8](https://github.com/leostriker111/KTool/issues/8)). El BCD de arriba es
justamente el caso que se enreda: está puesto a propósito, para que se vea.
