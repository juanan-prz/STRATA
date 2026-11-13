# STRATA

**S**IRISYS · **T**etralemma · **R**ecursive · **A**rchitecture · **T**opology · **A**nalysis

[English](README.md)

Una interpretación en software del sistema ontológico recursivo SIRISYS: un campo de constructos que evoluciona ciclo a ciclo mediante operaciones de concordancia, colapso cúsico y emergencia estratificada a través de cuatro capas ontológicas, con cada evento sellado en un registro irreversible encadenado por hashes.

STRATA es un proyecto independiente, no una obra oficial de SIRISYS. Sigue como fuente primaria *Pre of Then: The Material Constructs* (TMC), junto con otros materiales y documentación confidenciales, y la cabecera del framework etiqueta cada cita por su nivel de fuente: primaria, interpretativa o decisión de diseño.

Autor: Juan A. Pérez-Gómez.

-----

## Documentación

| Documento | English | Español |
|---|---|---|
| Guía técnica: cada archivo, modo, opción y resultado | [SIRISYS_Guide_v13_EN.md](SIRISYS_Guide_v13_EN.md) | [SIRISYS_Guide_v13_ES.md](SIRISYS_Guide_v13_ES.md) |
| Guía de Mac: instalación y primeros experimentos, paso a paso, para quien nunca ha usado la Terminal | [SIRISYS_Mac_Guide_v13_EN.pdf](SIRISYS_Mac_Guide_v13_EN.pdf) | [SIRISYS_Mac_Guide_v13_ES.pdf](SIRISYS_Mac_Guide_v13_ES.pdf) |
| Glosario técnico: cada concepto con su fuente y cómo lo implementa el código, y cada contador que muestran las vistas | [SIRISYS_Concepts_v13_EN.pdf](SIRISYS_Concepts_v13_EN.pdf) | [SIRISYS_Concepts_v13_ES.pdf](SIRISYS_Concepts_v13_ES.pdf) |

El código es el framework (`Sirisys_Framework_v13_5.py`), un servidor de experimentos con una vista en vivo en el navegador, un inspector de instancias guardadas, herramientas para ejecuciones medidas y cinco conjuntos de pruebas. La guía técnica describe cada archivo.

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

**El modelo es opcional, y traduce.** El campo nombra lo que produce, y una vez por respiración el I se acerca al Sombunal, con modelo o sin él. Con modelo, el modelo pone nombres legibles a los emergentes y a los conflictos, narra el campo y formula como pregunta cada acercamiento al Sombunal; lo que dice se guarda como etiquetas que ninguna ley lee, así que una vida con modelo sella el mismo ledger que sin él. Hay dos backends: Ollama, local (nada sale de la máquina), y la API de Anthropic, cuya clave va solo en la sesión de la terminal (`export ANTHROPIC_API_KEY=...`), nunca en un archivo. La sección 2 de la guía técnica explica los dos, y la vigilancia que detiene una ejecución cuyo modelo falla.

-----

## Conceptos básicos

**Capas.** Los constructos viven en cuatro capas: `NULL_00` (solo la ocupa el ancla de origen), `UMBRA_0` (donde nacen los perceptos, los acercamientos al Sombunal, los conflictos y la mayoría de los productos), `UNIT_1` (unidades activas, candidatas a cristalizar; aquí nace un producto `BOTH`) y `APPARENT` (cristales). Un constructo sube de capa cuando le llega tensión suficiente (colapso cúsico); un Apparent es incontrovertible.

**Tetralema.** Cada relación tiene uno de cuatro estados: `TRUE`, `FALSE`, `BOTH`, `NEITHER`. Un `BOTH` sostenido impulsa la emergencia y se cierra cuando ha intercambiado recursión suficiente. `NEITHER×NEITHER` materializa un conflicto o, pasado un límite por ciclo, la cuarta esquina misma: ninguna combinación es un callejón sin salida.

**Concordancia.** El operador `[::]` combina dos constructos en un tercero y registra el evento como prueba. Con quiralidad opuesta, el operando mayor orienta el resultado, así que `x::y ≠ y::x`.

**Sin azar.** El framework no tiene generador pseudoaleatorio. Cada elección se deriva de la cabeza del ledger (toda la historia irreversible) y de la cuestión que se decide: la misma historia reproduce la misma ejecución, y historias distintas nunca eligen igual.

**Respiración.** Una única respiración de todo el campo alterna contracción (favorece la cristalización) y expansión (favorece la generación). Una vez por respiración, el campo ajusta su propia tolerancia para que los cristales formados sigan a los cristales concluidos.

**Integridad.** Cada prueba se sella en un ledger encadenado por hashes al que solo se añade, guardado en segmentos comprimidos con un índice de hashes. El tiempo nunca retrocede, una instancia reanudada es igual a una no interrumpida, y cualquier edición, borrado o reordenación posterior del registro se detecta. Nada desaparece en silencio: un constructo que concluye deja una prueba de terminación.

El glosario define cada término con su fuente.

-----

## Estado

Proyecto de investigación en desarrollo activo.

- Con perceptos sintéticos y sin modelo, el campo cumple sus criterios de autoajuste: cristales duraderos en cada respiración, poco parpadeo, tamaño acotado, memoria y coste planos. Con los perceptos reales de una máquina se sostuvo durante 10 000 ciclos: la cristalización más baja de las primeras ventanas era la génesis.
- Con un modelo local (llama3.1, v13.4), el campo cumplió sus criterios, y el sentido de lo que decía el modelo no cambió la dinámica de forma medible. Desde la v13.5 el modelo solo traduce: sus nombres son etiquetas, y el acercamiento al Sombunal es una ley del campo. En un Mac, con la v13.5 y perceptos reales, el campo cumplió sus criterios durante 10 000 ciclos, y una vida con el modelo (363 llamadas), repetida sin él, selló el mismo ledger.
- Las preguntas abiertas figuran en la cabecera del framework como WALLS: sustrato (digital, no analógico), autosostenimiento, agencia, y relaciones frente a eventos. Cómo debe pesar en el campo el acercamiento al Sombunal (cadencia, estado y peso de su arista) y el papel de los puntos lagrangianos son decisiones de diseño abiertas; los puntos lagrangianos etiquetan constructos y pruebas, pero aún no gobiernan ninguna decisión.

-----

## Licencia

PolyForm Noncommercial 1.0.0: ver [LICENSE](LICENSE). El texto de la licencia está en inglés, y solo ese texto es vinculante.
