"""Carga y valida la población por departamento (INDEC, Censo 2022).

Archivo: data/raw/poblacion_departamentos.csv
  columnas obligatorias: departamento, poblacion
  columna opcional:      superficie_km2   (permite calcular densidad)
Fuente sugerida: https://censo.gob.ar/index.php/datos_definitivos_entre_rios/
"""
import pandas as pd
from config import RAW, DEPARTAMENTOS
from utils import normalizar

ARCHIVO = RAW / "poblacion_departamentos.csv"
TOTAL_PROVINCIAL_2022 = 1_425_578   # total definitivo informado por la DGEC de Entre Ríos
TOLERANCIA = 0.01                   # 1 % de diferencia aceptada en el chequeo


def crear_plantilla():
    RAW.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"departamento": list(DEPARTAMENTOS), "poblacion": "", "superficie_km2": ""}
                 ).to_csv(ARCHIVO, index=False)
    print(f"Plantilla creada: {ARCHIVO} (completá poblacion y, opcional, superficie_km2)")


def cargar():
    """Devuelve un DataFrame validado o None si no está disponible/completo."""
    if not ARCHIVO.exists():
        print("Población: no hay archivo; se omiten variables demográficas.")
        return None
    p = pd.read_csv(ARCHIVO)
    if not {"departamento", "poblacion"} <= set(p.columns):
        raise SystemExit("poblacion_departamentos.csv necesita columnas departamento,poblacion")
    mapa = {normalizar(k): k for k in DEPARTAMENTOS}
    p["departamento"] = p["departamento"].map(lambda x: mapa.get(normalizar(x)))
    p["poblacion"] = pd.to_numeric(p["poblacion"], errors="coerce")
    if "superficie_km2" in p.columns:
        p["superficie_km2"] = pd.to_numeric(p["superficie_km2"], errors="coerce")
    p = p.dropna(subset=["departamento"])
    if p["poblacion"].isna().any() or p["departamento"].nunique() < len(DEPARTAMENTOS):
        print("Población: archivo incompleto (hay departamentos sin dato); se omite.")
        return None
    total = p["poblacion"].sum()
    dif = abs(total - TOTAL_PROVINCIAL_2022) / TOTAL_PROVINCIAL_2022
    if dif > TOLERANCIA:
        print(f"AVISO: la suma de población ({total:,.0f}) difiere {dif:.1%} del total "
              f"provincial de referencia ({TOTAL_PROVINCIAL_2022:,}). Revisá los valores.")
    return p


if __name__ == "__main__":
    crear_plantilla()
