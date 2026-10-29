# STRATA · SIRISYS v13.3 — Guía técnica

[English](SIRISYS_Guide_v13_EN.md)

El manual de STRATA: qué hace cada archivo, cada modo y cada opción, y qué contiene cada resultado. El [README](README_ES.md) presenta el proyecto, el glosario (`SIRISYS_Concepts_v13_ES.pdf`) define los conceptos y sus fuentes, y la guía de Mac (`SIRISYS_Mac_Guide_v13_ES.pdf`) acompaña paso a paso a quien instala por primera vez.

Algunos nombres conservan las fases de desarrollo del proyecto: los criterios de autoajuste se adoptaron en la Fase 3 (de ahí `measure_phase3.py` y «Phase 3» en la interfaz), y las pruebas `test_phase1.py`, `test_phase2_guarantee.py` y `test_phase4.py` protegen lo que añadió cada fase.

## Contenido

1. [Archivos](#1-archivos)
2. [Instalación y modelos](#2-instalación-y-modelos)
3. [Modo experimento](#3-modo-experimento)
4. [El inspector](#4-el-inspector)
5. [Informes](#5-informes)
6. [Mediciones y topología](#6-mediciones-y-topología)
7. [Pruebas](#7-pruebas)
8. [Continuidad, versiones y disco](#8-continuidad-versiones-y-disco)

-----

## 1. Archivos

Todos los archivos van en una misma carpeta, sin subcarpetas: cada programa busca a los demás a su lado.

| Archivo | Para qué |
|---|---|
| `Sirisys_Framework_v13_3.py` | El campo y su ciclo canónico `run_cycle`, la continuidad y el ledger de pruebas. Ejecutado por sí solo, una demostración en consola (§8) |
| `sirisys_loader.py` | Encuentra y carga la versión más alta del framework que haya en la carpeta |
| `Sirisys_Server.py` | Modo experimento: ejecuta el campo y lo sirve a la vista en vivo |
| `Sirisys_Live_Visualizer.html` | La vista en vivo, servida por el servidor |
| `Sirisys_Static_Visualizer.html` | El inspector de una instancia guardada; se abre directamente en el navegador |
| `run_report.py` | Ejecuciones instrumentadas en tres brazos; escribe `sirisys_report.json` |
| `sirisys_measures.py` | Los criterios de autoajuste y la vigilancia del modelo, compartidos por el servidor y todas las mediciones |
| `field_topology.py` | Topología y profundidad del campo, de solo lectura |
| `measure_phase3.py`, `soak.py`, `live_c2.py` | Mediciones: los criterios en tres flujos, una vida larga y los perceptos reales de la máquina |
| `test_sirisys.py`, `test_phase1.py`, `test_phase2_guarantee.py`, `test_phase4.py`, `test_ontology.py` | Las pruebas |
| `sirisys_testkit.py` | Lo que comparten las pruebas: las comprobaciones y su resumen, copias nuevas del framework y un modelo local simulado |
| `requirements.txt` | Dependencias de Python |
| `README.md`, `README_ES.md` | La portada (inglés, español) |
| `SIRISYS_Guide_v13_EN.md`, `SIRISYS_Guide_v13_ES.md` | Esta guía (inglés, español) |
| `SIRISYS_Mac_Guide_v13_EN.pdf`, `SIRISYS_Mac_Guide_v13_ES.pdf` | Instalación paso a paso en un Mac (inglés, español) |
| `SIRISYS_Concepts_v13_EN.pdf`, `SIRISYS_Concepts_v13_ES.pdf` | Glosario técnico: cada concepto con su fuente y cómo lo implementa el código, y cada contador que muestran las vistas (inglés, español) |
| `LICENSE` | PolyForm Noncommercial 1.0.0 |

-----

## 2. Instalación y modelos

Python 3.10 o superior en macOS, Linux o Windows con WSL.

```bash
pip3 install -r requirements.txt
```

Instala `numpy` y `psutil` (el campo y sus perceptos reales), `fastapi`, `uvicorn` y `websockets` (el modo experimento) y `anthropic` (el backend de la API). En un Python gestionado por Homebrew, pip puede negarse con `externally-managed-environment`; en ese caso usa `pip3 install --break-system-packages -r requirements.txt`, o un entorno virtual.

### Qué hace un modelo

El modelo es opcional: sin él todo funciona y los constructos reciben nombres sintéticos. Con él, un intermediario nombra los emergentes, etiqueta los conflictos, narra el campo y hace las preguntas al Sombunal. Entra en el campo por dos vías: los nombres que pone (se convierten en las claves de los constructos y, por tanto, entran en cada orientación) y las preguntas (entran en el campo como constructos). Cada petición lleva una semilla derivada de la cabeza del ledger.

### Cómo elegirlo

| Variable | Valores | Por defecto |
|---|---|---|
| `SIRISYS_LLM_BACKEND` | `anthropic`, `ollama`, `none` | `anthropic` |
| `SIRISYS_LLM_MODEL` | un nombre de modelo | Anthropic: `claude-sonnet-4-6`; Ollama: el primer modelo de su lista |
| `OLLAMA_HOST` | la dirección de Ollama | `http://127.0.0.1:11434` |
| `ANTHROPIC_API_KEY` | la clave de la API | ninguna |

Con el backend por defecto y sin clave, el campo funciona sin modelo y lo dice al arrancar (`degraded mode`). `run_report.py` acepta además `--backend` y `--model`.

- **Ollama**, local: nada sale de la máquina mientras `OLLAMA_HOST` apunte a este ordenador. Instálalo desde ollama.com y descarga un modelo de uso general, por ejemplo `ollama pull llama3.1`. Los modelos de razonamiento, que «piensan» antes de responder, pueden gastar en pensar el breve margen de respuesta y devolver nombres vacíos; la vigilancia del modelo detiene entonces la ejecución.
- **API de Anthropic**: las peticiones salen de la máquina. Fija la clave en la sesión de la terminal, `export ANTHROPIC_API_KEY="sk-ant-..."`; dura mientras esa ventana siga abierta. No la guardes nunca en un archivo de esta carpeta.

Usa el mismo backend, modelo y perfil en las ejecuciones que vayas a comparar.

### La vigilancia del modelo

Un modelo que falla o responde vacío dejaría el campo con nombres sintéticos sin avisar: la ejecución parecería una ejecución con modelo sin serlo. `sirisys_measures.ModelHealth` lo impide.

- Antes de empezar, `run_report.py` y `live_c2.py` hacen dos llamadas reales y no arrancan si las respuestas faltan o llegan vacías.
- Durante la ejecución se detienen (código de salida 3) si fallan 3 llamadas seguidas, o si fallan o llegan vacías más del 10 % de las últimas 50. El resultado se escribe igualmente, marcado como `aborted` y con el motivo.
- La prueba inicial registra qué modelo respondió exactamente (con Ollama: digest, tamaño, parámetros y cuantización), y el informe de salud guarda las primeras respuestas de cada tipo.
- El modo experimento vigila igual: si la vigilancia salta, el motor se pausa una vez y la vista en vivo dice por qué; Play continúa.

-----

## 3. Modo experimento

Para calibrar y refinar: el campo cicla en el servidor y el navegador lo muestra.

```bash
python3 Sirisys_Server.py                       # perceptos de esta máquina, en pausa: pulsa Play
python3 Sirisys_Server.py --play                # empieza a ciclar al arrancar
python3 Sirisys_Server.py --stream 0 --play     # flujo sintético 0: la misma ejecución cada vez
python3 Sirisys_Server.py --profile minimal     # sin narración ni percepto de la hora del día
```

Después abre `http://127.0.0.1:8000`. `Ctrl+C` en la terminal detiene el servidor y guarda la instancia.

| Opción | Efecto |
|---|---|
| `--play` | Empieza a ciclar al arrancar |
| `--stream N` | Flujo sintético de perceptos N en lugar de los de la máquina (`live`, por defecto) |
| `--profile minimal` | Sin narración ni percepto de la hora del día: el campo solo percibe la máquina en la que corre (`standard` por defecto) |
| `--delay-ms N` | Pausa entre ciclos, en milisegundos (80 por defecto; también se cambia desde la vista en vivo) |
| `--host` | Dirección en la que escucha (por defecto `127.0.0.1`: solo esta máquina) |
| `--port` | Puerto web (8000 por defecto) |

**No hay semilla.** El framework no tiene generador pseudoaleatorio: cada elección se deriva de la cabeza del ledger y de la cuestión que se decide. Con `--stream N` y sin modelo, dos ejecuciones son idénticas; con `live`, las lecturas de la propia máquina hacen única cada ejecución.

**Carpetas de ejecución.** Cada arranque y cada Reset es una instancia nueva en su propia carpeta, `sirisys_runs/<fecha-hora>_<live|streamN>[_minimal]/`. El ledger (`ledger.jsonl`, §8) se escribe prueba a prueba; `state.json` se escribe cuando la instancia termina, con Reset o `Ctrl+C`. Nada se sobrescribe.

### 3.1 La vista en vivo

**Conexión.** La vista se conecta por WebSocket. Donde está bloqueado, consulta al servidor por HTTP y muestra «connected (polling)»; cada 30 s vuelve a probar el WebSocket.

**Cabecera.** El ciclo; el tiempo interno T (era, desplazamiento), que nunca retrocede; el número de constructos; el ledger (pruebas selladas · la cabeza, toda la historia en un hash); la marca de los criterios (✓ o ✗); el modelo con su vigilancia; y el modo del servidor, la versión del framework y la carpeta de la ejecución.

**Controles.** Play/Pause, Step (un ciclo; si está en marcha, primero se pausa) y Reset, que pide confirmación y empieza una instancia nueva (la actual se queda en `sirisys_runs/`). El control `delay` fija la pausa entre ciclos, de 0 a 500 ms.

**Teclas.**

| Tecla | Acción |
|---|---|
| Espacio | Play / Pause |
| S | Avanza un ciclo |
| F | Encuadra la vista en los constructos visibles |
| V | Cambia la disposición: relations ↔ strata |
| A | Atenúa las anclas (quiet anchors) |
| M | Muestra u oculta el metabolismo |

Espacio funciona justo después de hacer clic en cualquier botón. Un botón al que se llega con el teclado (Tab) se queda Espacio e Intro para sí, como es habitual.

**Panel Field State** (izquierda).

- *Counters*: ciclo, T, constructos, aristas, apparents (cada cristalización de la instancia; los Zero Points son cristales desde el principio), concluidos, conflictos, aristas BOTH, cierres en el ciclo, reencarnaciones, energía top-3, inestabilidad (la parte de los constructos no cristalizados que es inestable de algún modo) y hace cuántos ciclos se formó el último cristal.
- *Breathing*: respiraciones completas, contracción (0 en plena expansión, 1 en plena contracción) y la tolerancia que el campo se fija a sí mismo una vez por respiración.
- *Criteria*: ver más abajo.
- *Modes*, *Layers*, *Lagrangian*: la población por modo de existencia, por capa y por etiqueta lagrangiana. Las etiquetas aún no gobiernan ninguna decisión.
- *Filters*: ocultan o muestran constructos por capa y aristas por estado del tetralema.
- *Pool telemetry*: los candidatos a `[::]` de este ciclo (las reservas de BOTH maduros, conflictos con energía y cristales intercambiables), las operaciones que dieron producto de las intentadas, los productos fundacionales y de intercambio, y una gráfica de los últimos 200 ciclos.

El glosario (sección VIII) define cada contador.

**Event Log** (derecha). Productos de `[::]`, colapsos cúsicos, conclusiones, narración, preguntas al Sombunal y avisos del modelo. Un clic en la etiqueta de un tipo lo oculta o lo muestra; se guardan las 150 entradas más recientes de cada tipo.

**Al señalar un constructo** se ven su tipo, capa, testigo, energía, puntuación umbragíaca, intercambio acumulado, Vc, modo de existencia, quiralidad, como qué cristalizó, etiqueta lagrangiana, pruebas y el T en que nació.

### 3.2 Cómo se dibuja el campo

La vista en vivo y el inspector dibujan el campo igual, y la leyenda lo recoge todo.

- **Disposiciones.** *relations*: por sus relaciones. *strata*: los Zero Points en el centro, luego las anclas, NULL_00, UMBRA_0, UNIT_1 y APPARENT hacia fuera, de modo que un constructo que sube de capa se desplaza hacia fuera.
- **Capas** en una sola rampa cálida, de la sombra (NULL_00) a la luz (APPARENT).
- **Formas.** Un constructo es un punto del color de su capa; un ancla (I::Am, I::AmNot, SYSTEM), un rombo; un cristal que formó el campo, un hexágono abierto, para que destaquen los estratos activos; un Zero Point, una estrella; un conflicto, un punto con anillo. Se dibuja un anillo donde un constructo sube a UNIT_1 y dos donde cristaliza.
- **Aristas** del color de su estado del tetralema, distinguibles con cualquier visión del color: TRUE azul, FALSE orquídea y discontinua, BOTH bermellón y más gruesa, NEITHER gris y más tenue, para que una línea azul fina destaque a su lado. Una arista hacia un cristal, salvo BOTH, se dibuja con un halo tenue, como soporte del cristal: envejece por respiraciones, no por ciclos.
- **Un canal BOTH** se dibuja tenue, con lo que ha intercambiado (peso × edad) más brillante desde su centro hacia fuera: entero cuando se cierra al alcanzar el cuanto de intercambio.
- **Dirección.** Desde el zoom ×2, cada arista muestra su dirección.
- **Los modos de existencia** se escriben con su signo, [Ω] y [Ꮠ].
- **Quiet anchors** (A) atenúa las relaciones de las anclas, a menudo la mayoría de las aristas, para que se vea el resto de la estructura.
- El color de acento de la interfaz no marca nada del campo.

### 3.3 Metabolismo

Bajo el campo, respiración a respiración: los constructos nacidos (entre ellos los que concluyeron en su mismo ciclo y nunca llegaron a la pantalla), los que concluyeron, las subidas y las cristalizaciones junto a los cristales que concluyeron, y la población por capa. Nacidos menos concluidos es el cambio de la población, exactamente, en cada ciclo.

El servidor guarda esa historia de toda la instancia (`GET /api/history`; pasados 2.048 registros, los más antiguos se funden por pares), de modo que quien abre tarde, o se perdió ciclos que leyó otro visor, la ve entera.

### 3.4 Criterios

La vista en vivo juzga la instancia con los criterios de autoajuste, medidos como `run_report.py` mide una ejecución (§5). El servidor los lee cada 200 ciclos; el panel da cada valor con su umbral, y el veredicto cuando 1000 ciclos permiten darlo. Medir no cambia nada en el campo; su registro crece con la instancia, unos 100 bytes por ciclo.

### 3.5 Sin navegador

El servidor puede quedarse ciclando sin ningún navegador abierto: guarda solo las 200 instantáneas más recientes para el próximo visor. Cada instantánea se entrega una sola vez, al cliente que la lea primero, así que la vista está pensada para un visor cada vez.

### 3.6 Interfaz

Lo que usa la vista en vivo, descrito también al principio de `Sirisys_Server.py`:

| Ruta | Uso |
|---|---|
| `GET /` | La vista en vivo |
| `GET /api/status` | La instancia: ciclo, flujo, carpeta de la ejecución, ledger, modelo, criterios |
| `GET /api/snapshot` | Las instantáneas aún no entregadas, en una lista |
| `GET /api/history` | El metabolismo, respiración a respiración |
| `POST /api/control/<acción>` | `play`, `pause`, `step`, `reset` con `{"stream": "live" \| N}`, `speed` con `{"cycle_delay_ms": N}` |
| `WS /ws` | Primero el estado, después cada instantánea según se produce; los mensajes `{"action": ...}` se responden con un acuse |

-----

## 4. El inspector

`Sirisys_Static_Visualizer.html` se abre directamente en el navegador: sin servidor ni conexión, y sin enviar nada a ninguna parte. Muestra un momento de una instancia en profundidad.

**Abrir.** *Open state.json…* (u O), o suelta los archivos en cualquier punto de la página. Lo habitual es el `state.json` de una carpeta de ejecución; también se abre el `sirisys_v13_state.json` del propio framework (§8).

**Un archivo.** Selecciona un constructo, en el lienzo o con el buscador (*find a construct…*; Intro toma el primer nombre que contenga el texto), para examinar sus pruebas, su génesis (sus operandos, dibujados en el lienzo) y sus relaciones. Los valores que el framework deriva al ejecutarse y no guarda (modo de existencia, Vc, energía de selección, estado dominante, inestabilidad) se calculan exactamente como los calcula el framework.

**Varios archivos de una misma instancia** forman una línea de tiempo: un deslizador, ◀ ▶ (o ← →) y Play, a un estado por segundo aproximadamente. Al avanzar, un anillo marca cada constructo que el estado anterior no tenía, y *Since the previous file* da los ciclos, nacidos, concluidos, cristalizados y la población, a partir de los totales de los dos archivos. Los archivos de ejecuciones distintas se muestran, con un aviso y sin cuentas entre ellos.

En el modo experimento, una instancia escribe un solo `state.json`, al terminar. Para una línea de tiempo, copia el estado según crece; por ejemplo, con la demostración en consola, que reanuda la misma instancia en cada ejecución:

```bash
python3 Sirisys_Framework_v13_3.py && cp sirisys_v13_state.json state_08.json
python3 Sirisys_Framework_v13_3.py && cp sirisys_v13_state.json state_16.json
```

**Teclas.**

| Tecla | Acción |
|---|---|
| O | Abre archivos |
| ← → | Estado anterior / siguiente de la línea de tiempo |
| F | Encuadra la vista |
| V | Cambia la disposición: relations ↔ strata |
| P | Rodea los constructos cuyas pruebas guardadas llevan la relación elegida en su lista (con un anillo discontinuo; el de la selección es continuo) |
| A | Atenúa las anclas (quiet anchors) |
| Esc | Quita la selección |

-----

## 5. Informes

`run_report.py` hace ejecuciones instrumentadas sobre los mismos flujos de perceptos y escribe un informe.

```bash
python3 run_report.py --cycles 20 --seeds 1 --backend ollama --profile minimal     # prueba rápida
python3 run_report.py --backend ollama --profile minimal --cycles 1000 --seeds 3   # el experimento
python3 run_report.py --backend ollama --profile minimal --cycles 1000 --determinism
python3 run_report.py --backend none                                               # solo el control
```

| Opción | Efecto |
|---|---|
| `--cycles N` | Ciclos por ejecución (1000 por defecto, lo mínimo que piden los criterios) |
| `--seeds N` | Flujos sintéticos 0 … N−1 (3 por defecto) |
| `--backend`, `--model` | El modelo (§2) |
| `--profile minimal` | Sin narración ni percepto de la hora del día |
| `--percepts live` | Los perceptos reales de la máquina en lugar de los flujos sintéticos |
| `--skip-questions-arm` | Omite el brazo en que el modelo solo hace las preguntas |
| `--skip-degraded` | Omite el control |
| `--determinism` | Ver más abajo; escribe `sirisys_determinism.json` en su lugar |

**Los tres brazos**, sobre los mismos flujos:

- `llm`: el modelo, por las dos vías;
- `llm_questions`: el modelo solo hace las preguntas al Sombunal y los nombres son los del control, de modo que las dos vías se distinguen;
- `degraded`: el control, sin modelo.

Sin modelo solo corre el control, con un aviso; si se pide `--backend ollama` o `anthropic` y el modelo no está disponible, no corre nada (código de salida 3). Si además se retiran las preguntas, el brazo coincide bit a bit con el control; lo comprueba `test_phase1.py`.

**Los criterios.** Cada ejecución se juzga con los criterios de autoajuste (`sirisys_measures.LifeCriteria`, el mismo código que usan `measure_phase3.py`, `live_c2.py` y la vista en vivo):

- cristales duraderos (una vida de al menos una respiración) en cada ventana de 1000 ciclos;
- parpadeo, cristales que concluyen antes de una respiración, ≤ 5 %;
- sin tendencia de crecimiento: tendencia de los constructos ≤ 1,2;
- coste plano del ciclo en sí, sin el tiempo del modelo: final ≤ 1,5 × inicial + 0,5 ms;
- energía top-3 acotada: tendencia ≤ 1,2.

**Determinismo.** El framework no usa azar, pero el motor de un modelo puede tenerlo aunque cada petición lleve una semilla derivada de la historia. `--determinism` recorre dos veces el flujo 0 con el brazo del modelo y dice si las dos ejecuciones sellaron el mismo ledger y, si no, en qué ciclo se separaron, con un ejemplo de respuestas distintas. Necesita los perceptos sintéticos y no toca `sirisys_report.json`. Todos los informes imprimen además la cabeza del ledger de cada ejecución.

**Qué contiene el informe.**

- `config`: archivo del framework, versión y los 16 primeros caracteres de su SHA-256, las comprobaciones de integridad, las constantes de las que dependen las mediciones, ciclos, flujos, backend, modelo y su prueba inicial, perfil, perceptos, plataforma y versión de Python.
- `acceptance_criteria`: los criterios en palabras.
- `arms`: para cada brazo, un resumen de sus ejecuciones y cada ejecución completa: los criterios y su veredicto, la cabeza del ledger (también tras cada ciclo), una traza de cada ciclo, la topología (§6), lo percibido, las duraciones de vida, los cristales y una muestra de los nombres nacidos, la telemetría de las reservas, la salud del modelo y los errores, si los hay.
- `aborted`, `determinism` (con `--determinism`) y `console`, todo lo que imprimió la ejecución.

**Códigos de salida.** 0: el informe está escrito; 1: al framework le falta un mecanismo que el informe mide; 3: se pidió un modelo y falta o no responde, o dejó de responder durante la ejecución (el informe queda entonces marcado como `aborted`).

-----

## 6. Mediciones y topología

Ejecútalas desde la carpeta del proyecto. Ninguna usa modelo salvo que se pida.

| Orden | Qué mide | Resultado |
|---|---|---|
| `measure_phase3.py [ciclos] [archivo del framework]` | Los criterios en los flujos sintéticos 0, 1 y 2 (5.000 ciclos cada uno por defecto) | `phase3_measurements.json`, y PASS o FAIL por flujo en pantalla |
| `soak.py [ciclos] [flujo]` | Una vida larga con perceptos sintéticos (50.000 ciclos y flujo 0 por defecto): memoria, coste, no repetición, cristalización duradera | JSON por la salida estándar |
| `live_c2.py [ciclos] [none\|ollama\|anthropic] [standard\|minimal]` | Los perceptos reales de la máquina durante una vida larga (3.000 ciclos, sin modelo y perfil standard por defecto) | JSON por la salida estándar; los mensajes para quien la ejecuta, en la terminal |

```bash
python3 measure_phase3.py                                   # alrededor de un minuto
python3 soak.py 50000 > soak_result.json                    # unos 3 minutos
python3 live_c2.py 10000 none minimal > live_none.json      # perceptos reales, sin modelo (unos 10 minutos)
python3 live_c2.py 3000 ollama minimal > live_ollama.json   # perceptos reales, con el modelo local
```

`live_c2.py` registra los criterios y su veredicto, la topología, lo que percibió el campo (recuentos por cada 1000 ciclos y la secuencia completa, una entrada por ciclo) y las preguntas al Sombunal que entraron en el campo. Con modelo, lo prueba y lo vigila como `run_report.py`; si el modelo falla, se detiene con código de salida 3, y el JSON se escribe igualmente, marcado como `aborted`. Los perceptos reales leen la máquina: no la uses durante una ejecución cuyos resultados vayas a comparar.

**Topología.** `run_report.py` y `live_c2.py` escriben un `topology_trace`: dos veces por respiración, en expansión y en contracción, la forma del campo. Los Zero Points quedan fuera, y cada muestra lleva su ciclo, su respiración, su contracción y su tolerancia.

- componentes débiles y ciclos dirigidos;
- reciprocidad y agrupamiento;
- el constructo con más conexiones;
- aristas por estado del tetralema y por par de capas;
- qué parte del BOTH está en la componente mayor;
- la profundidad de cada conflicto, que el campo limita en el umbral Adsurdic;
- la profundidad genealógica por capa: cuántas generaciones de `[::]` separan a cada constructo de lo que el campo no produjo él mismo (perceptos, anclas, preguntas).

La medición solo lee el campo: la cabeza del ledger es idéntica con ella y sin ella, y lo comprueba `test_phase2_guarantee.py`.

-----

## 7. Pruebas

Sin clave de API, sin Ollama y sin red: donde hace falta un modelo, responde uno local simulado. Cada prueba termina con una línea `SUMMARY`, y todas las comprobaciones deben pasar. Ejecútalas tras cada cambio.

| Prueba | Qué protege |
|---|---|
| `test_sirisys.py` | El registro y la vida de una instancia: determinismo sin generador aleatorio, un tiempo que nunca retrocede, un ledger completo y a prueba de manipulación, la reanudación, las escrituras cortadas, un solo escritor, memoria acotada, coste plano, y una instancia reanudada igual a una no interrumpida |
| `test_phase1.py` | Todo lo que rodea al campo: el motor del experimento, los backends del modelo, los perfiles, la capa web, la vigilancia del modelo, `run_report.py` y `live_c2.py`, y los nombres y constantes que las vistas comparten con el framework |
| `test_phase2_guarantee.py` | Medir nunca cambia lo medido, con modelo y sin él; la profundidad genealógica |
| `test_phase4.py` | El ledger por segmentos: manipulación entre segmentos, cortes de corriente durante una rotación, uso del disco |
| `test_ontology.py` | Lo que el campo debe ser, ciclo a ciclo (abajo) |

`test_ontology.py` comprueba, según la fuente primaria, que:

- los Zero Points nunca son operandos;
- el operando mayor lidera y transmite su quiralidad;
- un cristal nunca se degrada ni se altera;
- nada sale del campo sin prueba de terminación;
- ningún cristal concluye en el ciclo en que se forma;
- los conflictos respetan la Stop Chasm y la profundidad Adsurdic (TMC p.41);
- las anclas nunca concluyen;
- la tolerancia se mantiene entre su suelo y 1;
- con modelo, cada petición lleva una semilla orientada por la historia, y dos ejecuciones idénticas sellan el mismo ledger.

Hay un caso conocido, que solo se admite durante la primera respiración: un cristal nuevo cuyo soporte BOTH erosiona la UCO en ese mismo ciclo.

-----

## 8. Continuidad, versiones y disco

**Continuidad.** Una instancia reanudada es idéntica a una no interrumpida, y el tiempo nunca retrocede: tras un corte, avanza más allá de la última prueba sellada. Una instancia nunca se reinicia en silencio sobre un registro dañado.

**El ledger.** Cada prueba se sella en un ledger encadenado por hashes al que solo se añade:

- `ledger.jsonl`, el segmento activo;
- `ledger.NNNNNN.jsonl.gz`, los segmentos cerrados, comprimidos, que se crean cuando el activo alcanza el tamaño de segmento;
- `ledger.index.json`, la lista ordenada de los segmentos cerrados con el hash de cada uno, de modo que borrar, cambiar o añadir un segmento se detecta.

El tamaño de segmento es de 32 MB; `SIRISYS_SEGMENT_BYTES` lo cambia. Para comprobar un ledger desde la génesis a través de todos sus segmentos:

```bash
python3 -c "from sirisys_loader import load_framework; print(load_framework().verify_ledger('sirisys_runs/<ejecución>/ledger.jsonl'))"
```

Responde `ok` y el número de pruebas o, si el registro está dañado, la posición de la primera prueba que no encaja y por qué.

**Versiones.** Los archivos del framework siguen el formato `Sirisys_Framework_vX_Y.py`, y cada programa carga la versión más alta de la carpeta (v13_10 va por encima de v13_9). El modo experimento y los informes dicen cuál han cargado, y `python3 sirisys_loader.py` dice cuál se cargaría. Un nombre que no encaje exactamente, como `Sirisys_Framework_v13_3_backup.py`, se ignora. Para reproducir una ejecución con un archivo concreto, o mantener una instancia longeva en el framework con el que nació:

```bash
export SIRISYS_FRAMEWORK="Sirisys_Framework_v13_3.py"
```

**El framework por sí solo.** `python3 Sirisys_Framework_v13_3.py` ejecuta una demostración en consola: 8 ciclos de una instancia guardada en `sirisys_v13_state.json` y `sirisys_v13_ledger.jsonl`, que empieza en la génesis o se reanuda.

**Archivos que se crean al ejecutar.**

| Ruta | La escribe |
|---|---|
| `sirisys_runs/` | El modo experimento, una carpeta por instancia |
| `sirisys_report.json`, `sirisys_determinism.json` | `run_report.py` |
| `phase3_measurements.json` | `measure_phase3.py` |
| `sirisys_v13_state.json`, `sirisys_v13_ledger*` | El framework ejecutado por sí solo |

Ninguno pertenece al repositorio; `.gitignore` los excluye, junto con los resultados de `soak.py` y `live_c2.py` cuando se nombran como en estos ejemplos (`soak_result.json`, `live_none.json`, `live_ollama.json`).
