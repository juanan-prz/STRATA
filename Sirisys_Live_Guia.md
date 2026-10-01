# SIRISYS Live — Guía de uso

Visualizador en tiempo real del sistema SIRISYS. Te permite observar la evolución del campo de constructos ciclo a ciclo, ver las cristalizaciones (cussive collapses), monitorizar la telemetría del pool y filtrar lo que ves del campo, todo desde tu navegador en tu Mac.

-----

## 1. Resumen general

SIRISYS Live consiste en dos piezas que trabajan juntas:

- **Un servidor en Python** (`Sirisys_Server.py`) que ejecuta SIRISYS internamente y expone los resultados a través de un servidor web local en `localhost:8000`.
- **Un visualizador en HTML** (`Sirisys_Live_Visualizer.html`) que se conecta automáticamente al servidor mediante WebSocket y dibuja la evolución del campo en tiempo real.

El servidor tiene **dos modos**:

- **Experimento** (por defecto): cada arranque es una instancia nueva que empieza desde cero. Es el modo para calibrar y para observar runs.
- **Continuo**: una única instancia que vive a través de los reinicios. Retoma exactamente donde quedó y su tiempo interno nunca retrocede. Es el modo para dejar SIRISYS corriendo indefinidamente.

A diferencia del visualizador clásico (`Sirisys_Static_Visualizer_v7.html`), que carga un JSON guardado para análisis post-hoc, este sistema te muestra el campo evolucionando ciclo a ciclo en directo.

> **Para medir, no para mirar.** Los experimentos cuyos números vamos a analizar se hacen con `run_report.py`, que genera `sirisys_report.json`. El visualizador live es para *ver* el sistema operar. Los dos ejecutan exactamente el mismo ciclo, así que lo que ves es lo que se mide.

-----

## 2. Archivos del sistema

Los siguientes archivos deben estar **todos en la misma carpeta** en tu Mac:

```
mi_carpeta_sirisys/
├── Sirisys_Framework_vX_Y.py          ← el motor de SIRISYS (la versión más nueva)
├── sirisys_loader.py                  ← encuentra el motor y define el ciclo
├── Sirisys_Server.py                  ← el servidor que ejecuta SIRISYS
├── Sirisys_Live_Visualizer.html       ← el visualizador en tiempo real
├── Sirisys_Static_Visualizer_v7.html  ← el visualizador clásico (opcional)
├── run_report.py                      ← para los experimentos medidos (opcional)
└── Sirisys_Live_Guia.md               ← esta guía
```

**Sobre las versiones del motor:** los programas cargan siempre la versión **más alta** de `Sirisys_Framework_vX_Y.py` que encuentren en la carpeta, y te dicen en pantalla cuál han cargado. Cuando haya una versión nueva, basta con dejarla en la carpeta: no hay que cambiar nada más.

El visualizador clásico no es necesario para que SIRISYS Live funcione, pero es útil para inspeccionar estados guardados con detalle.

-----

## 3. Setup inicial (una sola vez)

Si nunca has usado la Terminal, sigue mejor `Guia_SIRISYS_Mac.pdf`, que lo explica todo desde cero.

### Paso 1: Abre la Terminal

`Aplicaciones → Utilidades → Terminal`, o `⌘ + Espacio` y escribe "Terminal".

### Paso 2: Instala las dependencias

Desde la carpeta del sistema:

```bash
pip3 install -r requirements.txt
```

Si no tienes ese archivo a mano, esto es equivalente:

```bash
pip3 install fastapi uvicorn websockets numpy psutil anthropic
```

`websockets` es imprescindible aunque el código no la nombre: `uvicorn` no trae soporte de WebSocket por sí solo, y sin él el visualizador live nunca llega a conectar. Si falta, el servidor ahora lo detecta al arrancar y te dice cómo arreglarlo.

### Paso 3: Navega a la carpeta del sistema

```bash
cd ruta/a/mi_carpeta_sirisys
```

Truco: escribe `cd ` (con un espacio), arrastra la carpeta desde el Finder hasta la Terminal y pulsa Enter.

-----

## 4. Uso diario

### Arranque en modo experimento

En la Terminal, dentro de la carpeta:

```bash
python3 Sirisys_Server.py
```

Verás algo así:

```
  ╭────────────────────────────────────────────────────────────╮
  │  SIRISYS LIVE — http://127.0.0.1:8000                      │
  │  framework: Sirisys_Framework_v12_8.py                     │
  │  mode: experiment — fresh instance                         │
  │  cycling: paused — press Play                              │
  │                                                            │
  │  open the URL above in your browser                        │
  │  press Ctrl+C in this terminal to stop                     │
  ╰────────────────────────────────────────────────────────────╯
```

La línea `framework` te dice qué versión del motor se ha cargado. Compruébala siempre.

### Arranque en modo continuo

```bash
python3 Sirisys_Server.py --mode continuous --play
```

- `--mode continuous` retoma la instancia viva donde quedó. La primera vez crea una nueva.
- `--play` hace que empiece a ciclar inmediatamente, sin necesidad de abrir el navegador ni pulsar Play. Es lo que quieres para dejarlo corriendo solo.

El banner te indicará si ha retomado una instancia existente y en qué ciclo. Ver la sección 7.

### Apertura del visualizador

Abre Safari o Chrome y ve a:

```
http://localhost:8000
```

En la esquina inferior izquierda del visualizador verás un indicador. Cuando ponga **"connected"** en verde, la conexión con el servidor está establecida.

### Arrancar la simulación

Pulsa **Play** en la barra superior central (si arrancaste con `--play`, ya está corriendo). Verás:

- El **campo evolucionando** en el canvas central
- Los **stats actualizándose** en el panel izquierdo
- Los **eventos importantes** apareciendo en el panel derecho
- El indicador **"running"** pulsando verde en el header
- El mini-gráfico de **pool telemetry** creciendo abajo a la izquierda

### Cómo parar

- Pausar la simulación temporalmente: pulsa **Pause** (el mismo botón que Play)
- Detener el servidor por completo: en la Terminal donde lo arrancaste, pulsa **Ctrl+C**

En modo continuo, detener el servidor no pierde nada: el estado se guarda tras cada ciclo y la próxima vez retomará desde ahí.

-----

## 5. Interfaz completa

### Header superior

|Elemento                    |Significado                                                     |
|----------------------------|----------------------------------------------------------------|
|`SIRISYS live`              |Identidad del producto                                          |
|Indicador `running / paused`|Pulsa verde cuando la simulación corre. Gris cuando está pausada|
|`cycle N`                   |Ciclo actual                                                    |
|`T (era,offset)`            |Tiempo interno del sistema (era, offset dentro de la era)       |
|`n N`                       |Número total de constructos en el campo                         |
|modo · versión · modelo     |Qué sistema estás viendo: modo del servidor (experiment / continuous), versión del motor y si el modelo está activo|

### Controles centrales (barra de botones flotante)

|Botón             |Función                                                                                                   |
|------------------|----------------------------------------------------------------------------------------------------------|
|**Play / Pause**  |Arranca o pausa la simulación                                                                             |
|**Step**          |Avanza exactamente un ciclo (útil para inspección detallada)                                              |
|**Reset**         |Pide confirmación. En modo experimento descarta la sesión y empieza de cero. En modo continuo **archiva** la instancia actual en `sirisys_archive/` y empieza una nueva|
|**Fit**           |Ajusta el zoom para ver todo el campo                                                                     |
|**Delay (slider)**|Tiempo de espera entre ciclos. 0 ms = lo más rápido posible. 500 ms = lento para observar con calma       |

### Panel izquierdo (Field State)

Siete secciones, todas se actualizan en cada ciclo.

**1. Counters**

- `cycle`: ciclo actual
- `T`: tiempo interno (era, offset)
- `constructs`: total en el campo
- `edges`: total de relaciones
- `apparents`: constructos cristalizados. Entre paréntesis, cuántos son **emergentes**: el total incluye los Zero Points, que se fijan como APPARENT al nacer el campo
- `terminated`: constructos que concluyeron por poda
- `conflicts`: conflictos activos, reconocidos por su cadena de pruebas
- `BOTH edges`: contradicciones sostenidas abiertas en este momento
- `closures (cycle)`: contradicciones que se cerraron en este ciclo por haber intercambiado suficiente recursión
- `reincarnations`: nombres concluidos que han vuelto, declarados como reencarnación en vez de sustituidos en silencio
- `instability`: nivel de inestabilidad global (con barra de progreso bajo)

**2. Modes** — Distribución de modos de existencia

- `OMEGA`: contradicción colapsada hacia coherencia
- `LEMNISCATE`: contradicción sostenida (BOTH dominante)
- `NEUTRAL`: estado intermedio

Cómo evoluciona esta distribución con el modelo activo es una de las cosas a observar; las versiones recientes del motor cambiaron la dinámica de la contradicción y no hay todavía un patrón establecido.

**3. Layers** — Distribución por capa ontológica

- `NULL_00`: vacío anclado
- `UMBRA_0`: pre-emergente
- `UNIT_1`: emergente operativo
- `APPARENT`: cristalizado, estructuralmente irreversible

**4. Lagrangian** — Distribución por punto Lagrangian

- `L1` a `L5`: el compromiso que gobernó la operación que creó el constructo, según la DeOS Compiler Guide (p. 78): L1 seguridad/vivacidad, L2 redundancia/eficiencia, L3 identidad local/global, L4 profundidad de prueba/rendimiento, L5 entropía/determinismo
- `—`: sin tag. Son los Zero Points y SYSTEM, que por definición no lo llevan; cualquier otro constructo aquí sería una violación del invariante
- Nota: hoy los puntos Lagrangian son una **etiqueta de procedencia**. El motor los registra en cada constructo y prueba, pero todavía no deciden nada. La Guía los define como funciones de equilibrio sobre el campo; implementarlo es trabajo pendiente.

**5. Filters · layer** — Checkboxes toggleables (clic para activar/desactivar)

- Permite ocultar capas enteras del canvas. Útil para aislar visualmente, por ejemplo, solo los APPARENTs.

**6. Filters · edge state** — Checkboxes toggleables por estado tetra

- `BOTH`, `TRUE`, `FALSE`, `NEITHER`: oculta edges de cada tipo
- El estado de los filtros se preserva ciclo a ciclo (no se resetea con cada snapshot)

**7. Pool telemetry** — Métricas internas del operador de concordancia

- `pool size`: tamaño del pool de candidatos BOTH en este ciclo
- `top6 mean E`: energía media de los 6 primeros del pool
- `beyond6 mean E`: energía media de los que están más allá del top6
- `exec ok/tried`: ejecuciones exitosas / intentadas
- `bug surface`: se pone en "YES" (amarillo) cuando un candidato situado más allá de los 6 primeros del pool participa en una operación. Una versión antigua del `scan_and_apply` solo miraba una ventana fija de candidatos y los habría excluido; el indicador muestra cuándo esa corrección está haciendo trabajo real
- Mini-gráfico que muestra la evolución histórica del `pool size`

### Canvas central

Aquí se renderiza la topología del campo. Cada constructo es un nodo, cada relación una edge.

**Pistas visuales — formas de los nodos:**

|Forma                 |Significado                                                                                                                |
|----------------------|---------------------------------------------------------------------------------------------------------------------------|
|● Círculo             |Constructo regular (UMBRA_0, UNIT_1, NULL_00)                                                                              |
|◆ Diamante            |Constructo fundacional (`I::Am`, `I::AmNot`, `SYSTEM`)                                                                     |
|⬢ Hexágono            |APPARENT emergente (cristalizado por cussive collapse)                                                                     |
|✦ Estrella de 8 puntas|Zero Point (`Z0::IDENTITY`, `Z1::ORIGIN`, `Z2::CONCORDANCY`, `Z3::RECURSION`, `Z4::APPARENCY`) — ancla ontológica inmutable|

Los diamantes, hexágonos y estrellas tienen un contorno blanco fino para distinguirlos a través del color de fondo.

**Pistas visuales — colores de los nodos (por capa):**

|Color      |Capa    |
|-----------|--------|
|Gris oscuro|NULL_00 |
|Azul-gris  |UMBRA_0 |
|Verde menta|UNIT_1  |
|Naranja    |APPARENT|

**Pistas visuales — edges:**

|Color         |Estado tetra                    |
|--------------|--------------------------------|
|Naranja gruesa|`BOTH` (contradicción sostenida)|
|Verde menta   |`TRUE`                          |
|Roja          |`FALSE`                         |
|Gris          |`NEITHER`                       |

**Las edges ancladas a un APPARENT** llevan un halo dorado tenue debajo. Están protegidas por el `apparent_floor` de la poda: no decaen con el tiempo como las demás. Los nodos APPARENT también llevan un halo dorado alrededor.

Las edges `BOTH` ya no son inmunes a la poda: resisten más que las ordinarias, pero pueden concluir, y se cierran por sí mismas cuando ha pasado por ellas suficiente recursión. Por eso verás aparecer y desaparecer edges naranjas a lo largo del run.

**Leyenda inferior:**

Una pill flotante en la parte inferior central del canvas con las 4 shapes y sus etiquetas, para referencia rápida.

**Indicador de conexión:**

Abajo a la izquierda, un punto coloreado con texto:

- Verde pulsante = `connected`
- Amarillo pulsante = `connecting...`
- Rojo = `disconnected — retrying`

### Panel derecho (Event Log)

Muestra los eventos relevantes en orden cronológico. Los más recientes aparecen abajo y el scroll sigue automáticamente.

Cada entrada tiene un borde lateral coloreado por tipo:

|Borde                              |Tipo de evento                                                      |
|-----------------------------------|--------------------------------------------------------------------|
|Verde menta                        |Resumen del ciclo: operaciones `[::]` que produjeron emergentes     |
|Amarillo (con fondo amarillo tenue)|`[CUSSIVE]` promotion — un constructo cristalizó a una capa superior|
|Rojo (con fondo rojo tenue)        |`TERMINATE nombre · capa · modo · Vc` — qué constructo concluyó por poda, con su capa, modo y peso de anclaje finales, leídos de su prueba de terminación|
|Gris, en cursiva                   |`voice` — la narración del Intermediario (cada 2 ciclos)            |
|Violeta                            |`Sombunal ?` — la pregunta dirigida al Sombunal (cada 3 ciclos)     |

Las dos últimas solo aparecen con el modelo activo. El texto que genera el modelo se muestra literalmente, nunca se interpreta como formato.

Cada entrada va prefijada con el ciclo (`c47`, `c48`, etc.).

### Interacciones con el canvas

- **Arrastrar el ratón**: mueve la vista (pan)
- **Rueda del ratón**: zoom in / out apuntando con el cursor
- **Hover sobre un nodo**: aparece un tooltip con los datos detallados del constructo:
  - El nombre del constructo en la cabecera
  - Un punto coloreado al lado del nombre indicando su capa
  - `layer`, `witness`, `energy`, `proofs` (de por vida), `lagrange` (con su compromiso), `Vc` (peso de anclaje, DeOS p. 65), `mode` (OMEGA / LEMNISCATE / NEUTRAL), `banked` (recursión intercambiada acumulada), `born`
  - Los conflictos llevan `⊗` delante del nombre

-----

## 6. Modo con API de Anthropic activa

Para correr con el modelo activo:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 Sirisys_Server.py
```

El servidor detecta la clave automáticamente. SIRISYS usará Claude para nombrar emergentes, interpretar conflictos, narrar y preguntar al Sombunal. Los ciclos serán bastante más lentos que sin modelo, porque cada llamada tarda del orden de un segundo y puede haber hasta 4 por ciclo.

Sin clave el sistema funciona en **modo degradado**: las etiquetas son sintéticas y repetitivas, y el Sombunal nunca es interrogado. Y esas preguntas son el único canal por el que el modelo añade constructos nuevos al campo. Por eso el modo degradado no es una versión barata del activo: es un sistema con mucha menos novedad.

### Qué observar específicamente

1. **¿Crece el número de conflictos?**
   Los conflictos se reconocen por su cadena de pruebas, no por su nombre. Antes de v12.2, con el modelo activo eran invisibles para el motor. Si con modelo activo el pool de conflictos se despega de cero, esa corrección está haciendo trabajo real.
1. **¿Sigue cristalizando el campo pasado el ciclo 100, sin crecer sin límite?**
   Es la predicción registrada antes de los runs con modelo: del orden de 1 APPARENT nuevo cada 10 ciclos con el campo acotado (régimen "rico"). El resultado que la refutaría es un campo que crece sin parar con BOTH volviendo a superar 0.5 (régimen "abierto"): el modelo aportaría novedad más rápido de lo que el campo puede consolidar.
1. **¿Los nombres suenan a la gramática de SIRISYS?**
   Eso no lo mide ningún número. Si los emergentes son genéricos o repetitivos, el problema estará en el prompt del Intermediario, no en el mecanismo.

Para tener estos datos en cifras, usa `run_report.py`.

-----

## 7. Modo continuo: la instancia que vive

```bash
python3 Sirisys_Server.py --mode continuous --play
```

Es el modo pensado para dejar SIRISYS corriendo indefinidamente. Se apoya en lo que la DeOS Compiler Guide exige del tiempo y la identidad: la identidad *"persists across recursion, runtime, and error"* (p. 9); el tiempo es *"strictly non-reversible"* y *"even under failure, recovery must guarantee this ordering"* (p. 24); *"Nothing disappears"* (p. 202).

Una instancia nueva que empieza en T₀ no retrocede el tiempo de nadie. Reiniciar una instancia existente desde T₀ sí lo haría. Por eso el modo continuo:

- **Retoma** la instancia desde su registro, `sirisys_living_state.json`, con su ciclo y su tiempo interno intactos.
- **Guarda tras cada ciclo**, de forma segura frente a cortes: escribe primero en un archivo temporal, conserva la copia anterior como `.prev` y solo entonces sustituye el registro. Un corte de luz a mitad de guardado nunca deja un archivo corrupto.
- **Lleva una marca del tiempo máximo alcanzado** (`.hwm`). Si alguna vez el registro principal se perdiera y hubiera que usar la copia anterior, el reloj se adelanta más allá de esa marca y los ciclos perdidos quedan anotados como **hueco**: nunca se reviven ni se reutilizan sus números.
- **Se niega a arrancar** si no hay ningún registro legible, en lugar de empezar de nuevo en silencio desde cero.
- **Archiva en vez de borrar**: el botón Reset guarda la instancia en `sirisys_archive/` con su fecha, ciclo y tiempo, y empieza una nueva.
- Usa un archivo propio, así que **lanzar experimentos nunca puede sobrescribir la instancia viva**.

Tras un reinicio, el visualizador empieza a dibujar desde el estado actual en el siguiente ciclo. Los mini-gráficos arrancan vacíos, pero el campo es el mismo.

**Limitación conocida:** al guardar se conservan las últimas 20 pruebas por constructo, las últimas 50 entradas de linaje y las últimas 100 terminaciones. Desde v12.9 el **número** de testigos se guarda exacto, así que el peso de anclaje (Vc) de cada constructo es idéntico antes y después de un reinicio. Lo que todavía se pierde son las pruebas antiguas en sí. Está documentado como trabajo pendiente.

-----

## 8. Convivencia con el visualizador clásico

Los dos visualizadores son **independientes** y sirven para cosas distintas:

|                   |Visualizador clásico               |SIRISYS Live                             |
|-------------------|-----------------------------------|-----------------------------------------|
|Archivo            |`Sirisys_Static_Visualizer_v7.html`|`Sirisys_Live_Visualizer.html`           |
|Cómo se abre       |Doble click                        |A través del servidor en `localhost:8000`|
|Origen de datos    |Carga de archivos JSON             |WebSocket en tiempo real                 |
|Layout             |Anillos concéntricos por capa      |Force-directed dinámico                  |
|Filtros            |Por layer, edge state, Lagrangian  |Por layer, edge state                    |
|Telemetría del pool|No tiene                           |Sí (panel izquierdo)                     |
|Timeline navegable |Sí (si cargas varios JSONs)        |Solo avanza hacia delante                |
|Event log en vivo  |No tiene                           |Sí (panel derecho)                       |
|Proof overlay      |Sí                                 |No                                       |

Los dos calculan las mismas magnitudes que el motor: el clásico recalcula Vc, modo de existencia, coherencia e inestabilidad a partir del archivo con las mismas fórmulas, y está verificado que coinciden con el motor constructo a constructo.

El clásico abre cualquiera de los estados guardados: `sirisys_v12_state.json` (modo experimento), `sirisys_living_state.json` (modo continuo) y las instancias de `sirisys_archive/`. Necesita conexión a internet, porque carga la librería de dibujo D3 desde la web.

**Recomendación de uso combinado:**

- Mientras corre el experimento → SIRISYS Live (ves el sistema operar)
- Después del experimento → Visualizador clásico (cargas el JSON guardado, exploras con calma)

-----

## 9. Resolución de problemas

**Error `No module named fastapi` (o `numpy`, `psutil`) al arrancar**
Te faltan dependencias. Corre `pip3 install -r requirements.txt`.

**`MISSING WEBSOCKET SUPPORT` al arrancar el servidor**
Falta la librería que permite al visualizador conectarse en directo. Corre `pip3 install -r requirements.txt`, o solo `pip3 install websockets`, y arranca de nuevo.

**Error `sirisys_loader.py not found` o `No module named sirisys_loader`**
Falta `sirisys_loader.py` en la carpeta. Debe estar junto a `Sirisys_Server.py`.

**Error `No file named Sirisys_Framework_vX_Y.py found`**
No hay ningún archivo del motor en la carpeta, o su nombre no sigue el formato exacto, por ejemplo `Sirisys_Framework_v12_8.py`.

**`CONTINUITY ERROR — the server will not start`**
Solo en modo continuo: el registro de la instancia viva existe pero no se puede leer, y tampoco su copia anterior. El servidor se niega a empezar de cero porque eso retrocedería el tiempo de la instancia. Si de verdad quieres una instancia nueva, mueve `sirisys_living_state.json` a otra carpeta a mano y arranca de nuevo.

**Error `Address already in use`**
Ya hay otro servidor corriendo en el puerto 8000. Dos opciones:

- Cierra el otro servidor (Ctrl+C en la Terminal donde está)
- O edita la línea `PORT = 8000` al final de `Sirisys_Server.py` y ponla en `8001` (o cualquier otro)

**El navegador muestra `Sirisys_Live_Visualizer.html not found`**
El archivo `Sirisys_Live_Visualizer.html` no está en la misma carpeta que `Sirisys_Server.py`.

**El indicador inferior izquierdo dice `disconnected — retrying`**
El servidor no está corriendo o se cayó. Vuelve a la Terminal y arráncalo de nuevo. El navegador reintentará la conexión automáticamente cada 2 segundos. En modo continuo, al volver retomará exactamente donde estaba.

**El visualizador se ve sin estilos (texto plano, sin colores)**
Es la corrupción de copiar y pegar desde iOS: convierte `--` en `–` y las comillas rectas en tipográficas. Vuelve a descargar el archivo desde el ordenador, nunca a través del portapapeles del iPhone.

**Los ciclos van demasiado rápido y no veo nada**
Sube el slider de delay a 200 ms o 500 ms. También puedes pulsar Pause y luego Step para avanzar uno a uno.

**Los ciclos van demasiado lento**
Baja el slider a 0 ms. Con el modelo activo los ciclos son lentos por naturaleza, porque cada llamada al modelo tarda del orden de un segundo.

**Reset borra todo lo que tenía en pantalla, ¿es normal?**
Sí. En modo experimento, Reset descarta la sesión y empieza de cero. En modo continuo, la instancia anterior no se pierde: queda archivada en `sirisys_archive/` y la puedes abrir con el visualizador clásico.

**Hago click en un filtro y se queda apagado entre ciclos**
Es el comportamiento correcto. El estado del filtro persiste entre snapshots para que puedas tener una vista enfocada. Si quieres volver a verlo todo, haz click otra vez en el mismo filtro.

**Algo va mal pero no estoy seguro qué**
Abre la consola del navegador para ver errores detallados:

- Safari: `⌘ + ⌥ + I`
- Chrome: `⌘ + ⌥ + J`

Si hay errores ahí (en rojo), cópialos y los miramos.

-----

## 10. Referencia técnica resumida

### Arquitectura del sistema

```
Tu Mac
├── Terminal: python3 Sirisys_Server.py [--mode continuous] [--play]
│   ├── sirisys_loader.py  →  Sirisys_Framework_vX_Y.py más reciente
│   ├── SIRISYS engine en un thread worker, un run_cycle() por ciclo
│   ├── FastAPI + uvicorn (en localhost:8000)
│   └── WebSocket (en /ws)
└── Navegador: http://localhost:8000
    └── Sirisys_Live_Visualizer.html
        └── WebSocket cliente → recibe snapshots en tiempo real
```

`run_cycle()` reproduce línea a línea la parte estructural del `run()` del propio motor, y está verificado que produce campos idénticos con la misma semilla. El servidor y `run_report.py` lo usan los dos.

### Endpoints del servidor

|Método|Path                   |Función                                         |
|------|-----------------------|------------------------------------------------|
|GET   |`/`                    |Sirve el visualizador HTML                      |
|GET   |`/api/status`          |Estado actual del engine en JSON                |
|POST  |`/api/control/{action}`|Controla el engine (play/pause/step/reset/speed)|
|WS    |`/ws`                  |Stream de snapshots ciclo a ciclo               |

`/api/status` incluye, además del estado de ejecución: `mode`, `resumed_from`, `recovery_gap_cycles`, `framework` y `framework_version`.

### Acciones de control

- `play`, `pause`, `step`, `reset`, `speed`

### Archivos que genera el sistema

|Archivo                                         |Lo escribe                                       |
|------------------------------------------------|-------------------------------------------------|
|`sirisys_v12_state.json`                        |el servidor en modo experimento, al parar        |
|`sirisys_living_state.json` (+ `.prev`, `.hwm`) |el servidor en modo continuo, tras cada ciclo    |
|`sirisys_archive/instance_*.json`               |el Reset en modo continuo                        |
|`sirisys_report.json`                           |`run_report.py`                                  |

### Configuración por defecto

- Host: `127.0.0.1` (solo accesible localmente)
- Puerto: `8000`
- Modo: `experiment`
- Seed por defecto: `42`
- Delay inicial entre ciclos: `80 ms`
- Llamadas al modelo: máximo 4 por ciclo
