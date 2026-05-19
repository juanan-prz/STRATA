# STRATA

**S**IRISYS · **T**etralemma · **R**ecursive · **A**rchitecture · **T**opology · **A**nalysis

Real-time implementation and exploration of the SIRISYS recursive ontological system — a field of constructs that evolves cycle by cycle through concordancy operations, cussive collapse, and stratified emergence across four ontological layers.

The repository includes:

- **Engine** (`Sirisys_Framework_v12_1.py`): implementation of the construct field with tetralemma, layer-aware pruning, and stepped thresholds for layer promotions.
- **Live server** (`Sirisys_Server.py`): exposes the engine over WebSocket, allowing real-time visualization of the field evolution from the browser.
- **Live visualizer** (`Sirisys_Live_Visualizer.html`): force-directed topology with shapes differentiated by ontological category, toggleable filters, dual pool telemetry, cussive collapse animation, and full structural breakdown.
- **Static visualizer** (`Sirisys_Static_Visualizer_v6.html`): post-hoc inspection of saved states, with radial concentric layout by layer and proof overlay.

-----

## Setup

### Requirements

- Python 3.10 or higher
- macOS, Linux, or Windows with WSL

### Installation

```bash
pip3 install -r requirements.txt
```

If you want to run with the Anthropic API active so the system can use Claude to name emergents:

```bash
pip3 install anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

-----

## Quick start

From the repository folder:

```bash
python3 Sirisys_Server.py
```

Open `http://localhost:8000` in Safari or Chrome.

Click **Play** in the top control bar. SIRISYS will start running cycles and you will see the field evolve in real time.

When you’re done, `Ctrl+C` in the terminal to stop the server. The final state is saved to `sirisys_v12_state.json`, which you can open afterwards with the static visualizer for detailed inspection.

For a full guide to the interface and the concepts, see `Sirisys_Live_Guia.md` (currently in Spanish, English translation pending).

-----

## System architecture

```
Your computer
├── Terminal: python3 Sirisys_Server.py
│   ├── SIRISYS engine (in worker thread)
│   ├── FastAPI + uvicorn (on localhost:8000)
│   └── WebSocket (on /ws)
└── Browser: http://localhost:8000
    └── Sirisys_Live_Visualizer.html
        └── WebSocket client → receives snapshots in real time
```

When the server stops, it persists the final state to `sirisys_v12_state.json`. This file can be loaded into `Sirisys_Static_Visualizer_v6.html` for post-hoc analysis.

-----

## Fundamental concepts

SIRISYS operates on four ontological layers:

- **NULL_00**: anchored void
- **UMBRA_0**: pre-emergent
- **UNIT_1**: operative emergent
- **APPARENT**: crystallized, structurally irreversible

Relations between constructs can be in one of four tetra states: `TRUE`, `FALSE`, `BOTH`, `NEITHER`. Sustained contradictions (`BOTH`) are the engine of the system — they generate emergents that can be promoted between layers via cussive collapse.

-----

## Repository files

|File                               |Description                               |
|-----------------------------------|------------------------------------------|
|`Sirisys_Framework_v12_1.py`       |SIRISYS engine                            |
|`Sirisys_Server.py`                |FastAPI/WebSocket server                  |
|`Sirisys_Live_Visualizer.html`     |Live visualizer                           |
|`Sirisys_Static_Visualizer_v6.html`|Static visualizer (post-hoc)              |
|`Sirisys_Live_Guia.md`             |Complete user guide (Spanish)             |
|`requirements.txt`                 |Python dependencies                       |
|`LICENSE`                          |PolyForm Noncommercial 1.0.0 license terms|

-----

## License

This project is licensed under the **PolyForm Noncommercial License 1.0.0**.

You may use, modify, and distribute the software for any **noncommercial purpose**, including academic research, personal study, educational use, and public-interest research, provided that proper attribution is maintained.

Commercial use is not permitted under this license. For commercial licensing inquiries, please contact the author.

See the `LICENSE` file for the complete terms.

-----

## Project status

This is a research project under active development. Engine modifications (structural telemetry, prune_floor for APPARENT layer, stepped thresholds for cussive collapse) are documented in the code comments and the guide.
