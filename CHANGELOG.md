# Cambios

## Sin publicar

- Arreglado: pegar dos letras vuelve a significar AND (`AB` = A AND B). Se leia como
  una sola variable llamada `AB` y devolvia una funcion equivocada sin avisar (#1).
- Pruebas automatizadas (`unittest`, sin dependencias) y la CI ya las corre.
- Arreglado: con 6 variables la minimizacion tardaba de 18 s a mas de 100 s, y de paso
  congelaba la ventana. La cobertura ya no expande el producto de Petrick: reduce por
  esenciales y dominancia, y solo ramifica con poda sobre lo que quede. La misma respuesta
  exacta y minima, en centesimas de segundo (#2).
- Arreglado: la CLI ya valida sus entradas. `MIN_VARS`/`MAX_VARS` existian pero solo la
  GUI los respetaba, asi que `-n 9` daba basura, un mintermino fuera de rango tronaba con
  un traceback y uno negativo se envolvia en silencio a otra tabla. Ahora cada caso sale
  con su motivo y codigo distinto de cero (#3).

## Protoboard (en construccion)

- Realizaciones **NAND-only** y **NOR-only**: el motor las genera, con su ecuacion, su
  costo, su diagrama con bolitas de negacion y sus siete lenguajes. `--form nand` y
  `--form nor` en la CLI; en `--text` salen siempre junto al SOP y al POS.
- No compiten por la forma recomendada: en compuertas casi nunca ganan, y su ventaja
  real es en encapsulados, que es cosa del protoboard.
- Diseno completo de la funcion de protoboard en `docs/PROTOBOARD.md`.
- Catalogo de circuitos integrados (`ktool/proto/chips.py`): 12 chips con su pinout
  **leido de la hoja de datos**, no de memoria. Cada entrada dice de donde salio y como
  se comprobo. La estructura de compuertas se deduce de los nombres de los pines, para
  que no haya una segunda copia del dato que se desincronice.
- Molde ajustable del encapsulado (`ktool/proto/dip.py`): un solo dibujo que se calcula
  del numero de pines, en vez de un SVG por chip. Sirve de 4 a 40 patas, con el ancho
  de hilera correcto y el relieve del plastico.
- `herramientas/leer_pinout.py`: el lector que saco los pinouts de los datasheets,
  cruzando hasta tres lecturas independientes del mismo documento.
- Reparto de compuertas en encapsulados (`ktool/proto/seleccion.py`): los tres modos
  --fiel al diagrama, forzado a los chips que tengas, y automatico al ancho mayor--
  con cascada cuando no hay encapsulado tan ancho, reuso de las compuertas libres, y
  los 7404 de los literales negados.
- Arreglado: `--form nand` y `--form nor` dibujaban su circuito pero el reporte nunca
  imprimia su ecuacion, asi que el diagrama no se podia leer.
- Arreglado: el "Circuito completo sugerido" se armaba siempre en SOP aunque pidieras
  NAND o NOR. Ahora sigue la realizacion elegida, y los terminos reutilizables tambien.
- **Netlist** (`ktool/proto/netlist.py`): de las ecuaciones a la lista de conexiones
  fisicas, pin por pin. Plan logico, expansion en cascada de lo que no cabe,
  empaquetado en pastillas (U1, U2...) y nodos. Trae `comprobar()`, que evalua el
  netlist como circuito y lo compara contra la tabla de verdad.
- **Protoboard** (`ktool/proto/tablero.py`): colocacion por zonas --entradas a la
  izquierda, encapsulados en medio, indicadores al final--, mas tableros cuando no
  cabe, puentes de + y - entre ellos, y el dibujo con relieve.
- CLI: `--proto`, `--proto-modo`, `--proto-chips` y `--proto-extremos` (puntos, led,
  7seg_cc, 7seg_ca, 16seg_cc, 16seg_ca).
- El cableado de la protoboard, planchado: **angulos rectos** en vez de curvas, carriles
  repartidos por intervalos para que dos cables no se crucen yendo en paralelo, y los
  cables metidos en los **agujeros libres** de cada columna. Los puentes largos entre
  tableros bajan en haz por la orilla, sin cruzar el campo de agujeros.
- `--proto-separado`: una protoboard por salida, en vez de una sola con todo.
- El cableado, otra vez: **cada cable con su propia altura**. Antes los carriles caian
  en las filas enteras de la cuadricula y dos cables acababan encimados; ahora la banda
  se reparte en float --con N cables, el k-esimo va a (k+1)/(N+1)-- con margen a los dos
  lados. A lo alto el dibujo crece, asi que no hay razon para compartir altura.
- Se fue el punteado: todos los cables son linea solida. El punteado solo marcaba los
  saltos largos y confundia mas de lo que ayudaba.
- **Los colores dicen algo**: los cables que entran a una misma compuerta van del mismo
  color. El de las salidas se elige con `--proto-color-salidas`: arcoiris, un nombre
  (red, blue...) o un hex.
- Las resistencias, los LEDs y el display se dibujan como **componentes de verdad**,
  ocupando sus columnas, en vez de un muñon por pin. De ahi salian las "salidas de mas"
  y la protoboard vacia: ya no se abre un tablero que no lleve piezas.
- La protoboard como **dos matrices** (`ktool/proto/rejilla.py`). La de pistas dice de
  quien es cada columna y que agujero esta ocupado: un cable ya no sale de la patita del
  chip sino del agujero libre mas cercano, y de una entrada pueden salir varios cables.
  Si una columna se llena, el nodo se estira a una columna vacia. La de ruteo busca el
  camino con **A***: los cables ya puestos encarecen la celda pero no la bloquean, asi
  que rodean en vez de hacer escalerita y aprovechan el hueco libre.
- Dos reglas mas en el ruteo: **las horizontales no corren a la altura de los pines**
  --de lado solo por los renglones de en medio, para que un cable que va de largo no se
  confunda con uno que se clava-- y **dos cables no comparten tramo**. Lo segundo se
  cuenta por *arista* y no por celda: cruzarse en un punto esta bien, dos jumpers se
  montan; correr encimados por el mismo trecho no.
- Lo unico que queda pegado es la salida de una columna hacia el aire --un agujero solo
  tiene dos aristas de acceso, y para salir de la fila 3 hay que pasar por la 4--, y eso
  se dibuja con un **desfase** por coloreo de grafos: los cables que van juntos se ven
  uno al lado del otro, no uno encima del otro.

## 0.4.0

- Reestructura en subpaquetes: core/render/gui.
- Traductor de lenguajes reescrito sobre AST (lexer→parser→ast→codegen):
  parentesis por precedencia y traduccion de expresiones libres (CLI --to, GUI).

## 0.3.0

- Displays insertables en la interfaz (menu Insertar > Display): 7 segmentos y LED.
  Los segmentos encienden en verde segun la fila/estado activo y se conectan por
  nombre con las salidas; la etiqueta de cada segmento o LED se edita con un clic.

## 0.2.2

- GUI: las columnas se cargan con Enter o el boton Aplicar (las flechas ya no
  redibujan en cada clic); los controles se bloquean durante el redibujo. Adios lag.
- GUI: navegacion con flechas y Enter entre celdas; hasta 32 salidas.
- GUI: la barra acepta numeros (b1011, h4D, d77, 0b../0x..) ademas de expresiones.
- Documento: orden correcto de las senales de entrada en el circuito combinado.
- Documento: boton para copiar la tabla de verdad (TSV, pega como tabla en Excel).
- Documento: comparativa de componentes SOP vs POS vs mezcla, con detalle de
  terminos oculto por default.

## 0.2.1

- Circuito completo combinado: ruteo por columnas virtuales (los cables ya no se
  enciman), cada cable en su color y un punto en cada derivacion.
- Interfaz: clic en zona vacia de la tabla deselecciona.
- Documento: las ecuaciones por lenguaje van al final, agrupadas por lenguaje, con un
  boton para copiar el bloque completo de cada lenguaje.
- CLI: `--langs verilog,c,vhdl` para elegir lenguajes y `--no-langs` para omitirlos.
- C usa `bool` (stdbool.h) en lugar de `int`.

## 0.2.0

- Interfaz: seleccion multiple de celdas (arrastrando o con Shift), resaltadas en
  azul; las teclas 1, 0 y x cambian todas las seleccionadas a la vez.
- Interfaz: copiar / pegar / cortar (Ctrl+C/V/X) en formato compatible con Excel.
- Interfaz: renombrar las salidas haciendo clic en su encabezado.
- Interfaz: menu de Ayuda con guia rapida, atajos de teclado y enlace al repositorio.
- XOR/XNOR ahora compite como un camino mas y se elige si es la realizacion mas barata.
- Documento: ecuaciones exportadas a Matematico, Verilog, VHDL, ABEL, Logisim, C,
  Python y LaTeX, con boton para copiar.
- Documento: seccion de circuito completo sugerido con las compuertas AND compartidas
  entre salidas.
- Documento: guia de lectura incluida.

## 0.1.0

Primera versión.

- Tabla de verdad con hasta 6 variables, hasta 10 salidas y columna de notas.
- Minimización SOP y POS con Quine-McCluskey y don't cares.
- Elección automática de la forma más barata por costo de compuertas.
- Detección de XOR/XNOR por paridad.
- Términos reutilizables entre salidas.
- Mapas de Karnaugh y circuitos en SVG dentro de un documento HTML.
- Entrada por expresión, minterminos (decimal/hex/binario) o vector de verdad.
- Interfaz de línea de comandos (`kmap`) e interfaz gráfica (`kmap gui`).
