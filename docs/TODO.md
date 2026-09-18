# Pendientes

## Backlog (pedido, por construir)

### Subsistema de Layout / visualizacion (grande)
- HECHO v0.3.0: Insertar > Display con 7 segmentos y LED, encendido por nombre y
  etiquetas editables.
- Falta: 16 segmentos, matriz de LEDs, semaforo y plantillas comunes.
- Guardar / cargar "layouts" como archivo (JSON probable).
- La columna de **notas como puente** (dos usos):
  1. Biblioteca de estados con nombre: si una fila tiene nota "hola" y existe un
     estado guardado "hola", carga esos valores de salida en la fila.
  2. Etiquetas que conectan el layout con la tabla: un segmento/LED nombrado igual
     que una salida se enciende cuando esa salida vale 1 en el estado seleccionado.
- Previsualizar en vivo los displays/LEDs encendiendose segun la fila/estado, para
  cazar errores antes de fabricar.

### Opciones de documento (configurables desde la GUI)
- Elegir desde la GUI: que lenguajes incluir, ecuaciones vs tabla, mostrar/ocultar
  comparativa y detalle.
- HDL: emitir **ecuaciones** o **tabla de verdad** (case / with-select) en VHDL,
  Verilog, etc.

### Hecho en v0.2.2
- GUI: cargar columnas con Enter/Aplicar + bloqueo durante el redibujo (sin lag).
- GUI: navegacion con flechas y Enter entre celdas; hasta 32 salidas.
- Entrada por numero (b.., h.., d.., 0b/0x) ademas de expresiones.
- Documento: orden correcto de las senales de entrada; boton copiar tabla;
  comparativa SOP/POS/mezcla con detalle de terminos oculto por default.



### Protoboard (en diseno, ver docs/PROTOBOARD.md)

- Generar las realizaciones NAND-only y NOR-only: hoy no existen ni su diagrama.
- Modelo de chips con pinouts como datos, y los tres modos de seleccion (fiel al
  diagrama, forzado por el usuario, automatico al ancho mayor).
- Colocacion y ruteo sin colisiones, varias protoboards con sus puentes de + y -.
- Extremos elegibles: puntos, LED+resistencia, display de 7 y de 16 segmentos en
  anodo y en catodo comun. Ojo con la polaridad: anodo comun enciende en bajo.
- **Nota:** el tope de 63 columnas y esta lista de componentes son por donde se
  empieza, no por donde se acaba. Incluir mas componentes y mas tamanos de
  protoboard; capaz estamos limitados de pensamiento.


## Release 3 — Maquinas de estado (en diseño)

Objetivo: que ktool reciba un diagrama / tabla de estados y entregue los pasos
completos de diseño de una maquina de estados sincrona, reutilizando el motor de
minimizacion que ya existe.

### Flujo previsto

1. **Entrada de la maquina**
   - Estados, entradas y, por transicion, el estado siguiente y la salida.
   - Soportar Moore (salida depende del estado) y Mealy (salida depende de estado
     y entrada).
   - Formatos a considerar: un DSL de texto sencillo, JSON, o una pestaña en la GUI
     con tabla de transiciones. Probablemente arrancar por texto/JSON para la CLI.

2. **Asignacion de estados (encoding)**
   - Binario, Gray o one-hot. Asignar bits -> variables de estado Q1..Qm.
   - Dejar el encoding elegible; por defecto binario.

3. **Tabla de transiciones expandida**
   - Para cada (bits de estado actual, bits de entrada) -> bits de estado siguiente
     y salidas. Esto ya es una tabla de verdad sobre (Q..., entradas).

4. **Tipo de flip-flop y tabla de excitacion**
   - Elegir D, JK o T.
   - Derivar la excitacion: D = bit siguiente; para JK/T usar la transicion
     actual->siguiente con la tabla de excitacion del flip-flop.

5. **Ecuaciones y circuito**
   - Cada entrada de flip-flop (D, J, K, T) y cada salida es una funcion sobre
     (Q..., entradas): se pasa por `solve_output` para minimizar (SOP/POS/XOR).
   - Aprovechar `build_shared_circuit` para compartir compuertas entre las
     ecuaciones de excitacion y de salida.
   - Render: diagrama de estados, tabla de transiciones/excitacion, ecuaciones y
     el circuito con los flip-flops.

### Como encaja con lo que ya hay

- `core` / `qm` / `simplify` se reutilizan tal cual: una maquina de estados son
  varias tablas de verdad (una por entrada de flip-flop y por salida).
- Modulo nuevo `ktool/fsm.py` para el modelo (estados, transiciones, encoding,
  excitacion) y `render` para el diagrama de estados (SVG) y el circuito con FFs.
- CLI: subcomando `kmap fsm ...` que lea el archivo de la maquina.
- GUI: una pestaña aparte para capturar transiciones.

### Preguntas abiertas / decisiones a tomar

- Formato de entrada de la maquina (DSL propio vs JSON vs tabla en GUI).
- Minimizacion de estados (tabla de implicaciones) antes de asignar: ¿se incluye o
  se asume que el usuario ya tiene los estados minimos?
- Dibujo del diagrama de estados: layout automatico (es lo mas complicado) o
  posiciones simples en circulo.
- Manejo de don't cares en transiciones no especificadas.
