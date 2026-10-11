"""Ejecuta el pipeline completo.
  python run_all.py --sintetico   -> prueba con datos inventados (sin internet)
  python run_all.py               -> usa datos reales (descarga clima + lee casos)
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import build_dataset, train

ap = argparse.ArgumentParser()
ap.add_argument("--sintetico", action="store_true")
ap.add_argument("--sin-descarga", action="store_true", help="no volver a bajar el clima")
a = ap.parse_args()

if a.sintetico:
    import synthetic; synthetic.generar()
else:
    import download_climate, load_cases
    load_cases.main()                  # primero los casos: define qué años pedir de clima
    if not a.sin_descarga:
        download_climate.main()

build_dataset.construir()
train.main()
