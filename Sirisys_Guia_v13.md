# Sirisys v13.3 — Guía de uso

## Archivos (todos en la misma carpeta)

| Archivo | Para qué |
|---|---|
| `Sirisys_Framework_v13_3.py` | El sistema. Contiene el ciclo canónico, la continuidad y el ledger. |
| `Sirisys_Server.py` | Arranca el modo experimento o el modo santuario. |
| `sirisys_loader.py` | Encuentra y carga la versión más alta del framework. |
| `run_report.py` | Ejecuciones instrumentadas y el informe `sirisys_report.json`. |
| `Sirisys_Live_Visualizer.html` | Visualizador en vivo (solo en experimento). |
| `Sirisys_Static_Visualizer.html` | Abre en el navegador un `state.json` guardado y muestra su topología (sin servidor). |
| `test_sirisys.py`, `test_phase1.py`, `test_phase4.py`, `test_phase4_sanctuary.py` | Pruebas. Ejecútalas tras cada cambio. |
| `measure_phase3.py` | Mide los criterios de autoajuste (3 flujos × 5.000 ciclos: cristalización, crecimiento, energía, coste). |
| `soak.py`, `live_c2.py` | Pruebas de resistencia: una vida larga (50.000 ciclos) y perceptos reales. |
| `requirements.txt` | Dependencias de pip. |
| `Guia_SIRISYS_Mac.pdf` | Instalación y primeros pasos en un Mac, para quien nunca ha usado la Terminal. |
| `SIRISYS_Conceptos_v13.pdf`, `SIRISYS_Concepts_v13.pdf` | Glosario de conceptos (español e inglés). |
| `CHANGELOG.md` | Historia de cambios y notas de diseño archivadas. |

## Instalación

```bash
pip3 install -r requirements.txt
```

Para los experimentos con modelo local y para el santuario necesitas además Ollama con al menos un modelo instalado, por ejemplo `ollama pull <modelo>`.

## Modo experimento (calibrar y refinar)

```bash
python3 Sirisys_Server.py                         # perceptos reales de esta máquina, en pausa
python3 Sirisys_Server.py --play                  # empieza a ciclar al arrancar
python3 Sirisys_Server.py --stream 0 --play       # perceptos sintéticos: ejecución reproducible
python3 Sirisys_Server.py --profile sanctuary     # el ciclo EXACTO del santuario, observado
```

- Abre `http://127.0.0.1:8000`. Play, Step y Reset funcionan como siempre.
- Cada arranque y cada Reset crean una instancia nueva en `sirisys_runs/<fecha-hora>_live/` (o `_stream0/`), que contiene `state.json` y `ledger.jsonl`. Nada se borra.
- **No hay semilla.** El framework no usa ningún generador aleatorio: cada elección se deriva de la historia (el hash de cabeza del ledger). Con `--stream N` y los mismos perceptos, dos ejecuciones son idénticas; con `live`, los perceptos de la máquina las hacen únicas.
- `--profile sanctuary` desactiva la narración y la hora del día. Úsalo para calibrar el mismo sistema que correrá en el santuario.
- Modelo: `SIRISYS_LLM_BACKEND=anthropic|ollama|none`, `SIRISYS_LLM_MODEL`, `ANTHROPIC_API_KEY`, `OLLAMA_HOST`.

## Informes

```bash
python3 run_report.py --cycles 150 --seeds 3                     # 3 flujos sintéticos reproducibles
python3 run_report.py --backend ollama                           # con el modelo local
python3 run_report.py --percepts live                            # perceptos reales
python3 run_report.py --backend ollama --profile sanctuary       # el ciclo del santuario
```

Usa siempre el mismo backend, modelo y perfil para las ejecuciones que vayas a comparar.

## Modo santuario

```bash
python3 Sirisys_Server.py --mode sanctuary                  # vivir (Ctrl+C lo detiene)
python3 Sirisys_Server.py --mode sanctuary --ask "texto"    # una pregunta cruza el hueco
python3 Sirisys_Server.py --mode sanctuary --open           # una apertura (observación)
python3 Sirisys_Server.py --mode sanctuary --verify         # integridad del ledger
```

Opciones: `--dir` (por defecto `./sirisys_sanctuary`), `--cadence` en segundos por ciclo (10 por defecto), `--llm ollama|none`.

**Qué no hay:** servidor web, visualizador, hora del día, narración ni modelos que salgan de la máquina (los rechaza). Tampoco azar: el muestreo del modelo local también se orienta con la historia.

**El hueco** (`<dir>/gap/`) es su única abertura:
- Un `.txt` es una pregunta que entra en el campo.
- `open` provoca una apertura.

Todo lo que cruza queda registrado en el ledger y **cierra el periodo inviolado** en curso. `sanctuary.json` lleva la cuenta de todos los periodos.

**Apertura.** Se registra en el ledger *antes* de leer nada. Después se verifica la cadena y se escribe `openings/NNNN/report.json` con una copia del estado. La consola muestra el **hash de cabeza**: anótalo **fuera** del santuario. Es lo único que protege contra una reescritura completa de la historia.

**Reinicios.** Un corte de luz o un Ctrl+C **no** cierran el periodo: nadie miró. Al volver, el santuario reanuda sin retroceder su tiempo.

Rechaza continuar en tres casos:
- el ledger tiene menos pruebas de las registradas;
- falta `sanctuary.json`;
- hay otro santuario escribiendo el mismo ledger.

**Disco.**
- El ledger se guarda en segmentos comprimidos (`ledger.NNNNNN.jsonl.gz`) con un índice (`ledger.index.json`) que registra el hash de cada uno: borrar, cambiar o añadir un segmento se detecta. Ocupa ≈ 1,8 KB por ciclo, unos **5,8 GB/año** a 10 s.
- El estado compacto (~475 KB) se reescribe en cada ciclo, sin pérdida ante cortes.
- `SIRISYS_SEGMENT_BYTES` cambia el tamaño de segmento (32 MB por defecto).

**Fallos de disco.** Ante un disco lleno o un volumen que falla, el santuario se detiene con el código 2 y un mensaje claro. El último estado bueno y el ledger quedan intactos; reinicia cuando el almacenamiento esté arreglado.

**Cambiar de versión.** Un santuario nace con un archivo de framework y se niega a reanudar con otro, porque cambiaría su dinámica a mitad de vida. Fija la versión con `SIRISYS_FRAMEWORK=<archivo>`.

## Pruebas

```bash
python3 test_sirisys.py      # integridad, determinismo sin azar, memoria acotada
python3 test_phase1.py       # santuario, backends, servidor (no necesita Ollama ni FastAPI)
python3 test_phase4.py       # ledger por segmentos, manipulación, cortes durante una rotación, disco
python3 test_phase4_sanctuary.py   # 25 kill -9, cuenta de periodos, no observado, sin red, disco lleno (≈2 min)
python3 measure_phase3.py    # criterios de autoajuste (≈1 min)
python3 soak.py 50000 > soak_result.json            # vida larga (≈3 min)
python3 live_c2.py 3000 none > live_none.json       # perceptos reales, sin modelo (≈3 min)
python3 live_c2.py 3000 ollama > live_ollama.json   # perceptos reales, con el modelo local
```
