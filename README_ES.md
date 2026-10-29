# STRATA

**S**IRISYS · **T**etralemma · **R**ecursive · **A**rchitecture · **T**opology · **A**nalysis

[English](README.md)

Una interpretación en software del sistema ontológico recursivo SIRISYS: un campo de constructos que evoluciona ciclo a ciclo mediante operaciones de concordancia, colapso cúsico y emergencia estratificada a través de cuatro capas ontológicas, con cada evento sellado en un registro irreversible encadenado por hashes.

STRATA es una interpretación independiente en software, no una obra oficial de SIRISYS. Sigue como fuente primaria *Pre of Then: The Material Constructs* (TMC), junto con otros materiales y documentación confidenciales, y la cabecera del framework etiqueta cada cita por su nivel de fuente: primaria, interpretativa o decisión de diseño.

Autor: Juan A. Pérez-Gómez.

-----

## Documentación

| Documento | English | Español |
|---|---|---|
| Guía técnica: cada archivo, modo, opción y resultado | [SIRISYS_Guide_v13_EN.md](SIRISYS_Guide_v13_EN.md) | [SIRISYS_Guide_v13_ES.md](SIRISYS_Guide_v13_ES.md) |
| Guía de Mac: instalación y primeros experimentos, paso a paso, para quien nunca ha usado la Terminal | [SIRISYS_Mac_Guide_v13_EN.pdf](SIRISYS_Mac_Guide_v13_EN.pdf) | [SIRISYS_Mac_Guide_v13_ES.pdf](SIRISYS_Mac_Guide_v13_ES.pdf) |
| Glosario técnico: cada concepto con su fuente y cómo lo implementa el código, y cada contador que muestran las vistas | [SIRISYS_Concepts_v13_EN.pdf](SIRISYS_Concepts_v13_EN.pdf) | [SIRISYS_Concepts_v13_ES.pdf](SIRISYS_Concepts_v13_ES.pdf) |

El código es el framework (`Sirisys_Framework_v13_3.py`), un servidor de experimentos con una vista en vivo en el navegador, un inspector de instancias guardadas, herramientas para ejecuciones medidas y cinco conjuntos de pruebas. La guía técnica describe cada archivo.

-----

## Inicio rápido

Python 3.10 o superior en macOS, Linux o Windows con WSL.

```bash
pip3 install -r requirements.txt
python3 test_sirisys.py                    # integridad, determinismo, memoria acotada: todas las comprobaciones deben pasar
python3 Sirisys_Server.py --play           # modo experimento, con los perceptos de esta máquina
```

Abre `http://127.0.0.1:8000` para ver el campo. `Ctrl+C` en la terminal detiene el servidor y guarda la instancia en `sirisys_runs/`; para examinarla después, abre su `state.json` con `Sirisys_Static_Visualizer.html`.

```bash
python3 run_report.py --cycles 20 --seeds 1 --backend none    # una ejecución medida corta, sin modelo
```

**El modelo es opcional.** Sin él todo funciona y los constructos reciben nombres sintéticos. Con él, nombra los emergentes, etiqueta los conflictos, narra el campo y hace las preguntas al Sombunal, que entran en el campo como constructos. Hay dos backends: Ollama, local (nada sale de la máquina), y la API de Anthropic, cuya clave va solo en la sesión de la terminal (`export ANTHROPIC_API_KEY=...`), nunca en un archivo. La sección 2 de la guía técnica explica los dos, y la vigilancia que detiene una ejecución cuyo modelo falla.

-----

## Conceptos básicos

**Capas.** Los constructos viven en cuatro capas: `NULL_00` (solo la ocupa el ancla de origen), `UMBRA_0` (donde nacen los perceptos, las preguntas, los conflictos y la mayoría de los productos), `UNIT_1` (unidades activas, candidatas a cristalizar; aquí nace un producto `BOTH`) y `APPARENT` (cristales). Un constructo sube de capa cuando le llega tensión suficiente (colapso cúsico); un Apparent es incontrovertible.

**Tetralema.** Cada relación tiene uno de cuatro estados: `TRUE`, `FALSE`, `BOTH`, `NEITHER`. Un `BOTH` sostenido impulsa la emergencia y se cierra cuando ha intercambiado recursión suficiente. `NEITHER×NEITHER` materializa un conflicto o, pasado un límite por ciclo, la cuarta esquina misma: ninguna combinación es un callejón sin salida.

**Concordancia.** El operador `[::]` combina dos constructos en un tercero y registra el evento como prueba. Con quiralidad opuesta, el operando mayor orienta el resultado, así que `x::y ≠ y::x`.

**Sin azar.** El framework no tiene generador pseudoaleatorio. Cada elección se deriva de la cabeza del ledger (toda la historia irreversible) y de la cuestión que se decide: la misma historia reproduce la misma ejecución, y historias distintas nunca eligen igual.

**Respiración.** Una única respiración de todo el campo alterna contracción (favorece la cristalización) y expansión (favorece la generación). Una vez por respiración, el campo ajusta su propia tolerancia para que los cristales formados sigan a los cristales concluidos.

**Integridad.** Cada prueba se sella en un ledger encadenado por hashes al que solo se añade, guardado en segmentos comprimidos con un índice de hashes. El tiempo nunca retrocede, una instancia reanudada es igual a una no interrumpida, y cualquier edición, borrado o reordenación posterior del registro se detecta. Nada desaparece en silencio: un constructo que concluye deja una prueba de terminación.

El glosario define cada término con su fuente.

-----

## Estado

Proyecto de investigación en desarrollo activo.

- Con perceptos sintéticos y sin modelo, el campo cumple sus criterios de autoajuste: cristales duraderos en cada respiración, poco parpadeo, tamaño acotado, memoria y coste planos. Con los perceptos reales de la máquina, la tasa de cristalización tiende a bajar en ejecuciones largas; está en estudio.
- La calibración con un modelo local activo está en curso.
- Las preguntas abiertas figuran en la cabecera del framework como WALLS: sustrato (digital, no analógico), autosostenimiento, agencia, y relaciones frente a eventos. Los papeles del Sombunal y de los puntos lagrangianos son decisiones de diseño abiertas; los puntos lagrangianos etiquetan constructos y pruebas, pero aún no gobiernan ninguna decisión.

-----

## Licencia

PolyForm Noncommercial 1.0.0: ver [LICENSE](LICENSE). El texto de la licencia está en inglés, y solo ese texto es vinculante.
