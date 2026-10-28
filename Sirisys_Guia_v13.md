# Sirisys v13.3 — Guía de uso

## Archivos (todos en la misma carpeta)

| Archivo | Para qué |
|---|---|
| `Sirisys_Framework_v13_3.py` | El sistema. Contiene el ciclo canónico, la continuidad y el ledger. |
| `Sirisys_Server.py` | Arranca el modo experimento y sirve el campo al visualizador en vivo. |
| `sirisys_loader.py` | Encuentra y carga la versión más alta del framework. |
| `run_report.py` | Ejecuciones instrumentadas: un brazo con modelo frente a un brazo de control, con los mismos flujos sintéticos. Escribe `sirisys_report.json`. |
| `field_topology.py` | Topología y profundidad del campo, de solo lectura. La registran `run_report.py` y `live_c2.py`. |
| `sirisys_measures.py` | Mediciones compartidas: los criterios de autoajuste y la vigilancia del modelo, que detiene una ejecución si el modelo no responde. |
| `Sirisys_Live_Visualizer.html` | Visualizador en vivo. |
| `Sirisys_Static_Visualizer.html` | Abre en el navegador un `state.json` guardado y muestra su topología (sin servidor). |
| `test_sirisys.py`, `test_phase1.py`, `test_phase2_guarantee.py`, `test_phase4.py`, `test_ontology.py` | Pruebas. Ejecútalas tras cada cambio. |
| `measure_phase3.py` | Mide los criterios de autoajuste (3 flujos × 5.000 ciclos: cristalización, crecimiento, energía, coste). |
| `soak.py`, `live_c2.py` | Pruebas de resistencia: una vida larga (50.000 ciclos) y perceptos reales. |
| `requirements.txt` | Dependencias de pip. |
| `Guia_SIRISYS_Mac.pdf` | Instalación y primeros pasos en un Mac, para quien nunca ha usado la Terminal. |
| `SIRISYS_Concepts_v13_ES.pdf`, `SIRISYS_Concepts_v13_EN.pdf` | Glosario de conceptos (español e inglés). |

## Instalación

```bash
pip3 install -r requirements.txt
```

Para los experimentos con modelo local necesitas además Ollama con al menos un modelo instalado, por ejemplo `ollama pull <modelo>`.

## Modo experimento

```bash
python3 Sirisys_Server.py                         # perceptos reales de esta máquina, en pausa
python3 Sirisys_Server.py --play                  # empieza a ciclar al arrancar
python3 Sirisys_Server.py --stream 0 --play       # perceptos sintéticos: ejecución reproducible
python3 Sirisys_Server.py --profile minimal       # sin narración ni hora del día
```

- Abre `http://127.0.0.1:8000`. Play, Step y Reset controlan el campo; Fit recentra la vista.
- Cada arranque y cada Reset crean una instancia nueva en `sirisys_runs/<fecha-hora>_live/` (o `_stream0/`), que contiene `state.json` y `ledger.jsonl`. Nada se borra.
- **No hay semilla.** El framework no usa ningún generador aleatorio: cada elección se deriva de la historia (el hash de cabeza del ledger). Con `--stream N` y los mismos perceptos, dos ejecuciones son idénticas; con `live`, los perceptos de la máquina las hacen únicas.
- `--profile minimal` quita la narración y la hora del día: el campo solo percibe la máquina en la que corre.
- `--host` fija la dirección en la que escucha el servidor. Por defecto es `127.0.0.1`: solo se puede abrir desde la misma máquina.
- El visualizador se conecta por WebSocket. Si el entorno lo bloquea, consulta al servidor por HTTP y muestra «connected (polling)»; cada 30 s vuelve a probar el WebSocket.
- Modelo: `SIRISYS_LLM_BACKEND=anthropic|ollama|none`, `SIRISYS_LLM_MODEL`, `ANTHROPIC_API_KEY`, `OLLAMA_HOST`.

## Informes

```bash
python3 run_report.py --cycles 150 --seeds 3 --backend none     # 3 flujos sintéticos reproducibles, sin modelo
python3 run_report.py --backend ollama                           # con el modelo local
python3 run_report.py --percepts live                            # perceptos reales
python3 run_report.py --backend ollama --profile minimal         # sin narración ni hora del día
```

Usa siempre el mismo backend, modelo y perfil para las ejecuciones que vayas a comparar.

**Criterios.** Cada ejecución se juzga con los criterios de autoajuste, con el mismo código que `measure_phase3.py`:
- cristales duraderos en cada ventana de 1.000 ciclos;
- parpadeo ≤ 5 %;
- sin tendencia de crecimiento;
- coste plano del ciclo (sin contar el tiempo del modelo);
- energía de los 3 constructos más cargados, acotada.

El informe compara los dos brazos sobre los mismos flujos.

**Vigilancia del modelo.** Un modelo que falla o responde vacío deja el campo con nombres sintéticos sin avisar. Con modelo, `run_report.py` y `live_c2.py`:
- hacen antes dos llamadas reales y no empiezan si las respuestas faltan o llegan vacías;
- se detienen (código 3) si fallan 3 llamadas seguidas, o si fallan o llegan vacías más del 10 % de las últimas 50.

El resultado se escribe igualmente, marcado como `aborted` y con el motivo.

**Perceptos reales.** `live_c2.py` registra lo que percibió el campo (recuentos por cada 1.000 ciclos y la secuencia completa) y las preguntas al Sombunal que entraron. Los perceptos reales leen la máquina: no la uses mientras corre una ejecución que quieras comparar.

**Topología.** `run_report.py` y `live_c2.py` guardan además un `topology_trace`: dos muestras por respiración, una en expansión y otra en contracción. Cada muestra recoge la forma del campo:
- componentes débiles y ciclos dirigidos;
- reciprocidad y agrupamiento;
- el constructo con más aristas;
- aristas por estado tetralemático y por par de capas;
- qué parte del `BOTH` está en la componente mayor;
- la profundidad de cada conflicto, que el campo limita en el umbral Adsurdic;
- la profundidad genealógica por capa: cuántas generaciones de `[::]` separan a cada constructo de lo que el campo no produjo él mismo (perceptos, anclas, preguntas).

Los Zero Points quedan fuera, y cada muestra lleva su ciclo, su respiración, su contracción y su tolerancia. La medición solo lee el campo: la cabeza del ledger es idéntica con ella y sin ella.

## Continuidad y disco

- **Continuidad.** Una instancia reanudada es idéntica a una no interrumpida, y el tiempo nunca retrocede: tras un corte, avanza más allá de la última prueba sellada. Nunca se reinicia en silencio sobre un registro dañado.
- **Ledger.** Se guarda en segmentos comprimidos (`ledger.NNNNNN.jsonl.gz`) con un índice (`ledger.index.json`) que registra el hash de cada uno: borrar, cambiar o añadir un segmento se detecta. `SIRISYS_SEGMENT_BYTES` cambia el tamaño de segmento (32 MB por defecto).
- **Versión del framework.** Para reproducir una ejecución con un archivo concreto, fíjalo con `SIRISYS_FRAMEWORK=<archivo>`.

## Pruebas

```bash
python3 test_sirisys.py      # integridad, determinismo sin azar, memoria acotada
python3 test_phase1.py       # motor del experimento, backends del modelo y capa web (no necesita Ollama ni FastAPI)
python3 test_phase2_guarantee.py   # medir topología y profundidad no altera el ledger ni el campo
python3 test_phase4.py       # ledger por segmentos, manipulación, cortes durante una rotación, disco
python3 test_ontology.py     # invariantes del campo, ciclo a ciclo, con y sin modelo
python3 measure_phase3.py    # criterios de autoajuste (≈1 min)
python3 soak.py 50000 > soak_result.json                   # vida larga (≈3 min)
python3 live_c2.py 10000 none minimal > live_none.json     # perceptos reales, sin modelo (≈10 min)
python3 live_c2.py 3000 ollama minimal > live_ollama.json  # perceptos reales, con el modelo local
```

`test_ontology.py` comprueba lo que el campo debe ser según la fuente primaria:
- los Zero Points nunca son operandos;
- el operando mayor lidera y transmite su quiralidad;
- un cristal nunca se degrada ni se altera;
- nada desaparece sin prueba de terminación;
- ningún cristal concluye en el ciclo en que se forma;
- con modelo, cada petición lleva una semilla orientada por la historia.

Hay un caso conocido, que solo se admite durante la primera respiración: un cristal nuevo cuyo soporte `BOTH` erosiona la UCO en ese mismo ciclo.
