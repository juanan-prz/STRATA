# SIRISYS Live — Guía de uso

Visualizador en tiempo real del sistema SIRISYS. Te permite observar la evolución del campo de constructos ciclo a ciclo, ver las cristalizaciones (cussive collapses), monitorizar la telemetría del pool y filtrar lo que ves del campo, todo desde tu navegador en tu Mac.

-----

## 1. Resumen general

SIRISYS Live consiste en dos piezas que trabajan juntas:

- **Un servidor en Python** (`Sirisys_Server.py`) que ejecuta SIRISYS internamente y expone los resultados a través de un servidor web local en `localhost:8000`.
- **Un visualizador en HTML** (`Sirisys_Live_Visualizer.html`) que se conecta automáticamente al servidor mediante WebSocket y dibuja la evolución del campo en tiempo real.

A diferencia del visualizador clásico (`Sirisys_Static_Visualizer_v6.html`), que carga un JSON guardado para análisis post-hoc, este sistema te muestra el campo evolucionando ciclo a ciclo en directo.

-----

## 2. Archivos del sistema

Los siguientes archivos deben estar **todos en la misma carpeta** en tu Mac:

```
mi_carpeta_sirisys/
├── Sirisys_Framework_v12_1.py         ← el código del sistema SIRISYS
├── Sirisys_Server.py        ← el servidor que ejecuta SIRISYS
├── Sirisys_Live_Visualizer.html        ← el visualizador en tiempo real
├── Sirisys_Static_Visualizer_v6.html  ← el visualizador clásico (post-hoc, opcional)
└── SIRISYS_Live_Guia.md     ← esta guía
```

El visualizador clásico no es necesario para que SIRISYS Live funcione, pero es útil tenerlo a mano para inspeccionar estados guardados con detalle.

-----

## 3. Setup inicial (una sola vez)

### Paso 1: Abre la Terminal

`Aplicaciones → Utilidades → Terminal`, o `⌘ + Espacio` y escribe “Terminal”.

### Paso 2: Instala las dependencias

```bash
pip3 install fastapi uvicorn
```

Si quieres correr SIRISYS con la API de Anthropic activa para que use Claude para nombrar emergentes, también:

```bash
pip3 install anthropic
```

### Paso 3: Navega a la carpeta del sistema

```bash
cd ruta/a/mi_carpeta_sirisys
```

Por ejemplo, si los pusiste en el Escritorio:

```bash
cd ~/Desktop/mi_carpeta_sirisys
```

-----

## 4. Uso diario

### Arranque

En la Terminal, dentro de la carpeta:

```bash
python3 Sirisys_Server.py
```

Verás algo así:

```
  ╭────────────────────────────────────────────────────────────╮
  │  SIRISYS LIVE — http://127.0.0.1:8000                      │
  │                                                            │
  │  open the URL above in your browser                        │
  │  press Ctrl+C in this terminal to stop                     │
  ╰────────────────────────────────────────────────────────────╯
```

### Apertura del visualizador

Abre Safari o Chrome y ve a:

```
http://localhost:8000
```

En la esquina inferior izquierda del visualizador verás un indicador. Cuando ponga **“connected”** en verde, la conexión con el servidor está establecida.

### Arrancar la simulación

Pulsa **Play** en la barra superior central. SIRISYS empezará a correr ciclos y verás:

- El **campo evolucionando** en el canvas central
- Los **stats actualizándose** en el panel izquierdo
- Los **eventos importantes** apareciendo en el panel derecho
- El indicador **“running”** pulsando verde en el header
- El mini-gráfico de **pool telemetry** creciendo abajo a la izquierda

### Cómo parar

- Pausar la simulación temporalmente: pulsa **Pause** (el mismo botón que Play)
- Detener el servidor por completo: en la Terminal donde lo arrancaste, pulsa **Ctrl+C**

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

### Controles centrales (barra de botones flotante)

|Botón             |Función                                                                                                   |
|------------------|----------------------------------------------------------------------------------------------------------|
|**Play / Pause**  |Arranca o pausa la simulación                                                                             |
|**Step**          |Avanza exactamente un ciclo (útil para inspección detallada)                                              |
|**Reset**         |Reinicia la sesión desde cero. Pide confirmación. Borra el campo, la telemetría, el log y vuelve cycle a 0|
|**Fit**           |Ajusta el zoom para ver todo el campo                                                                     |
|**Delay (slider)**|Tiempo de espera entre ciclos. 0 ms = lo más rápido posible. 500 ms = lento para observar con calma       |

### Panel izquierdo (Field State)

Siete secciones, todas se actualizan en cada ciclo.

**1. Counters**

- `cycle`: ciclo actual
- `T`: tiempo interno (era, offset)
- `constructs`: total en el campo
- `edges`: total de relaciones
- `apparents`: constructos cristalizados (capa APPARENT)
- `terminated`: constructos que fueron podados
- `instability`: nivel de inestabilidad global (con barra de progreso bajo)

**2. Modes** — Distribución de modos de existencia

- `OMEGA`: contradicción colapsada hacia coherencia
- `LEMNISCATE`: contradicción sostenida (BOTH dominante)
- `NEUTRAL`: estado intermedio

Con LLM activo verás OMEGA dominar progresivamente (es el patrón documentado).

**3. Layers** — Distribución por capa ontológica

- `NULL_00`: vacío anclado
- `UMBRA_0`: pre-emergente
- `UNIT_1`: emergente operativo
- `APPARENT`: cristalizado, estructuralmente irreversible

**4. Lagrangian** — Distribución por punto Lagrangian

- `L1`, `L2`, `L3`, `L4`, `L5`: cada punto Lagrangian representa un rol funcional del constructo en el campo
- `—`: sin tag (constructos sin Lagrangian asignado todavía)

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
- `bug surface`: si “YES” (en amarillo), significa que el bug del scan_and_apply se manifestaría aquí. Es el indicador empírico clave para los experimentos con API activa
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

Además, **las edges ancladas a un APPARENT** llevan un halo dorado tenue debajo. Esto indica que están **estructuralmente protegidas por el `prune_floor`** (la modificación B que añadimos al código). No decaen con el tiempo de la misma manera que las edges normales.

Los nodos APPARENT también llevan un halo dorado alrededor.

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
|Verde menta                        |Evento normal: operación `[::]` que produjo emergentes              |
|Amarillo (con fondo amarillo tenue)|`[CUSSIVE]` promotion — un constructo cristalizó a una capa superior|
|Rojo (con fondo rojo tenue)        |`TERMINATE` — un constructo fue podado                              |
|Gris                               |Otros mensajes informativos (invariantes, etc.)                     |

Cada entrada va prefijada con el ciclo (`c47`, `c48`, etc.).

### Interacciones con el canvas

- **Arrastrar el ratón**: mueve la vista (pan)
- **Rueda del ratón**: zoom in / out apuntando con el cursor
- **Hover sobre un nodo**: aparece un tooltip con los datos detallados del construct:
  - El nombre del constructo en la cabecera
  - Un punto coloreado al lado del nombre indicando su capa
  - `layer`, `witness`, `energy`, `proofs`, `born`

-----

## 6. Modo con API de Anthropic activa

Para correr con LLM activo (lo más interesante para los experimentos):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 Sirisys_Server.py
```

El servidor detectará la key automáticamente y SIRISYS usará Claude para nombrar emergentes. Los ciclos serán más lentos (~200-500 ms con LLM activo, frente a ~60 ms sin LLM) pero el sistema generará mucha más diversidad nominal y verás patrones más ricos.

### Qué observar específicamente

Cuando corras con API activa, tres cosas son particularmente informativas:

1. **¿Aparece `bug surface: YES` alguna vez?**
   El indicador en el panel izquierdo, sección “Pool telemetry”. Si en algún ciclo se pone en amarillo con “YES”, es la primera evidencia empírica de que el bug original del `scan_and_apply` se manifiesta con LLM activo. Eso confirmaría que el refinamiento que hicimos cubre un problema real.
1. **¿Cuántos APPARENT acumula el sistema?**
   Sin LLM eran solo los 5 iniciales (los Zero Points). Con LLM activo podrían surgir muchos más a través de cussive collapse. Cada nuevo APPARENT activa la protección B (`apparent_floor`) que añadimos al `prune`. Si pasan de 5 a, digamos, 50, entonces la protección está haciendo trabajo real.
1. **¿Crecen constructos en `UMBRA_0`?**
   Sin LLM apenas hay 3-4 UMBRA_0. Si LLM produce más diversidad, UMBRA_0 podría poblarse más. Entonces los thresholds escalonados (cambio C: `threshold_unit_1=0.396`, `threshold_apparent=0.88`) empezarán a producir promociones UMBRA→UNIT que antes no ocurrían.

Si alguna de las tres ocurre, los refinamientos cubrieron un problema real. Si ninguna ocurre, son defensivos pero inertes en este régimen — cualquiera de los dos resultados es informativo y digno de registro.

-----

## 7. Convivencia con el visualizador clásico

Los dos visualizadores son **independientes** y sirven para cosas distintas:

|                   |Visualizador clásico               |SIRISYS Live                             |
|-------------------|-----------------------------------|-----------------------------------------|
|Archivo            |`Sirisys_Static_Visualizer_v6.html`|`Sirisys_Live_Visualizer.html`           |
|Cómo se abre       |Doble click                        |A través del servidor en `localhost:8000`|
|Origen de datos    |Drag-drop de archivos JSON         |WebSocket en tiempo real                 |
|Layout             |Anillos concéntricos por capa      |Force-directed dinámico                  |
|Filtros            |Por layer, edge state, Lagrangian  |Por layer, edge state                    |
|Telemetría del pool|No tiene                           |Sí (panel izquierdo)                     |
|Timeline navegable |Sí (si cargas varios JSONs)        |Solo avanza hacia delante                |
|Event log en vivo  |No tiene                           |Sí (panel derecho)                       |
|Proof overlay      |Sí                                 |No                                       |

Comparten formato compatible: si el servidor guarda el estado al cerrarse, ese JSON se puede inspeccionar después con el visualizador clásico. Esto es útil si quieres revisar con detalle un momento específico de un run con la capacidad del clásico de navegar proofs y filtrar por Lagrangian.

**Recomendación de uso combinado:**

- Mientras corre el experimento → SIRISYS Live (ves el sistema operar)
- Después del experimento → Visualizador clásico (cargas el JSON guardado, exploras con calma)

-----

## 8. Resolución de problemas

**Error `No module named fastapi` al arrancar**
Te faltan las dependencias. Corre:

```bash
pip3 install fastapi uvicorn
```

**Error `Address already in use`**
Ya hay otro servidor corriendo en el puerto 8000. Dos opciones:

- Cierra el otro servidor (Ctrl+C en la Terminal donde está)
- O edita la línea `PORT = 8000` al final de `Sirisys_Server.py` y ponla en `8001` (o cualquier otro)

**El navegador muestra `Sirisys_Live_Visualizer.html not found`**
El archivo `Sirisys_Live_Visualizer.html` no está en la misma carpeta que `Sirisys_Server.py`. Asegúrate de tener los tres archivos juntos.

**El indicador inferior izquierdo dice `disconnected — retrying`**
El servidor no está corriendo o se cayó. Vuelve a la Terminal y ejecuta `python3 Sirisys_Server.py` de nuevo. El navegador reintentará la conexión automáticamente cada 2 segundos.

**Los ciclos van demasiado rápido y no veo nada**
Sube el slider de delay a 200 ms o 500 ms. También puedes pulsar Pause y luego Step para avanzar uno a uno.

**Los ciclos van demasiado lento**
Baja el slider a 0 ms. Si aun así va lento, posiblemente estás corriendo con LLM activo (~200-500 ms/ciclo es normal con LLM). Sin LLM debería estar en ~60 ms/ciclo.

**Reset borra todo lo que tenía en pantalla, ¿es normal?**
Sí. Reset reinicia la sesión completa: el campo vuelve al estado inicial (solo los Zero Points y la identidad recursiva), la telemetría se borra, el event log se limpia, y el contador de ciclos vuelve a 0.

**Hago click en un filtro y se queda apagado entre ciclos**
Es el comportamiento correcto. El estado del filtro persiste entre snapshots para que puedas tener una vista enfocada. Si quieres volver a verlo todo, haz click otra vez en el mismo filtro.

**Algo va mal pero no estoy seguro qué**
Abre la consola del navegador para ver errores detallados:

- Safari: `⌘ + ⌥ + I`
- Chrome: `⌘ + ⌥ + J`

Si hay errores ahí (en rojo), cópialos y los miramos.

-----

## 9. Referencia técnica resumida

### Arquitectura del sistema

```
Tu Mac
├── Terminal: python3 Sirisys_Server.py
│   ├── SIRISYS engine (en thread worker)
│   ├── FastAPI + uvicorn (en localhost:8000)
│   └── WebSocket (en /ws)
└── Navegador: http://localhost:8000
    └── Sirisys_Live_Visualizer.html
        └── WebSocket cliente → recibe snapshots en tiempo real
```

### Endpoints del servidor

|Método|Path                   |Función                                         |
|------|-----------------------|------------------------------------------------|
|GET   |`/`                    |Sirve el visualizador HTML                      |
|GET   |`/api/status`          |Estado actual del engine en JSON                |
|POST  |`/api/control/{action}`|Controla el engine (play/pause/step/reset/speed)|
|WS    |`/ws`                  |Stream de snapshots ciclo a ciclo               |

### Acciones de control

- `play`, `pause`, `step`, `reset`, `speed`

### Configuración por defecto

- Host: `127.0.0.1` (solo accesible localmente)
- Puerto: `8000`
- Seed por defecto: `42`
- Delay inicial entre ciclos: `80 ms`

Si quieres cambiar alguno de estos valores, edita las constantes al final de `Sirisys_Server.py`.