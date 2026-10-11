"""Configuración central del proyecto: Entre Ríos, Argentina."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "outputs"

# --- Período de análisis ---------------------------------------------------
ANIO_INICIO = 2016
ANIO_FIN = 2026

# --- Departamentos de Entre Ríos (lat, lon APROXIMADAS de la cabecera) ------
# Se usan para pedir el clima. Verificá/ajustá las coordenadas si querés
# mayor precisión (por ejemplo, el centroide real del departamento).
DEPARTAMENTOS = {
    "Colón": (-32.22, -58.14),
    "Concordia": (-31.39, -58.02),
    "Diamante": (-32.07, -60.64),
    "Federación": (-31.00, -57.92),
    "Federal": (-30.95, -58.78),
    "Feliciano": (-30.38, -58.75),
    "Gualeguay": (-33.14, -59.31),
    "Gualeguaychú": (-33.01, -58.52),
    "Islas del Ibicuy": (-33.72, -58.65),
    "La Paz": (-30.75, -59.64),
    "Nogoyá": (-32.39, -59.79),
    "Paraná": (-31.73, -60.52),
    "San Salvador": (-31.62, -58.50),
    "Tala": (-32.30, -59.13),
    "Uruguay": (-32.48, -58.23),
    "Victoria": (-32.62, -60.16),
    "Villaguay": (-31.86, -59.03),
}

# --- Casos de dengue (Ministerio de Salud) -----------------------------------
# Dataset "Vigilancia de Dengue y Zika" de https://datos.salud.gob.ar : hay un
# CSV por período (por ejemplo "1 a 52 - 2024"). Descargá todos los que quieras
# y guardalos en data/raw/casos/ (se leen todos los .csv de esa carpeta).
CARPETA_CASOS = RAW / "casos"

# Columnas del CSV. None = detección automática (soporta los formatos conocidos:
# anio_min/sepi_min/cantidad y año/semanas_epidemiologicas/cantidad_casos, etc.).
# Si algún archivo trae nombres distintos, escribilos acá (se aplican a todos).
COLUMNAS_CASOS = {
    "provincia": None,
    "departamento": None,
    "anio": None,
    "semana": None,
    "casos": None,        # los casos vienen agregados por grupo etario
    "evento": None,
}
EVENTO = "Dengue"            # el archivo mezcla eventos (p. ej. Zika); se filtra este
PROVINCIA_NOMBRE = "Entre Ríos"
# Si el último archivo es de un año en curso (incompleto), indicá hasta qué fecha
# hay datos, p. ej. "2026-10-05". Las semanas posteriores NO se rellenan con ceros.
CASOS_HASTA = None

# --- Modelado ---------------------------------------------------------------
HORIZONTE_SEMANAS = 4        # se predice con esta anticipación
ANIOS_TEST = 1              # últimos N años se reservan para test
BROTE_MIN_CASOS = 5          # casos semanales mínimos para considerar brote
BROTE_K_STD = 2.0            # umbral = media + K * desvío (calculado solo con train)
SEMILLA = 42
