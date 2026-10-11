"""Descarga clima diario de Open-Meteo (histórico) por departamento y lo
agrega por semana. Requiere internet. Resultado: data/raw/clima_semanal.csv

- Pide solo los años con datos de casos (si ya corriste load_cases.py).
- Guarda cada departamento en data/raw/clima_cache/: si se corta (p. ej. por el
  límite de la API), al volver a correr continúa donde quedó.
- Ante un 429 espera y reintenta; si el límite es horario/diario, corta y avisa."""
import time
import pandas as pd
import requests
from config import DEPARTAMENTOS, RAW, ANIO_INICIO, ANIO_FIN
from utils import normalizar

URL = "https://archive-api.open-meteo.com/v1/archive"
CACHE = RAW / "clima_cache"
VARIABLES = [
    "temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
    "precipitation_sum", "relative_humidity_2m_mean",
]
ESPERA_ENTRE_DEPTOS = 5      # segundos
MAX_REINTENTOS = 5


def rango_fechas():
    """Desde 8 semanas antes del primer año con casos hasta hoy-7 días."""
    ini = pd.Timestamp(f"{ANIO_INICIO}-01-01")
    fin = pd.Timestamp(f"{ANIO_FIN}-12-31")
    f = RAW / "casos_semanales.csv"
    if f.exists():
        c = pd.read_csv(f, parse_dates=["semana"])
        ini = max(ini, pd.Timestamp(year=c["semana"].dt.year.min(), month=1, day=1)
                  - pd.Timedelta(weeks=9))
    fin = min(fin, pd.Timestamp.today().normalize() - pd.Timedelta(days=7))
    return ini.date(), fin.date()


def pedir(params):
    for intento in range(1, MAX_REINTENTOS + 1):
        r = requests.get(URL, params=params, timeout=120)
        if r.status_code != 429:
            r.raise_for_status()
            return r.json()
        motivo = r.text[:300]
        if "ourly" in motivo or "aily" in motivo:
            raise SystemExit("Open-Meteo: límite horario/diario alcanzado.\n"
                             f"  ({motivo})\nLo ya descargado quedó en data/raw/clima_cache/. "
                             "Volvé a correr más tarde (o mañana) y continúa desde ahí.")
        espera = 60 * intento
        print(f"  429 (límite por minuto). Espero {espera}s (intento {intento}/{MAX_REINTENTOS})...")
        time.sleep(espera)
    raise SystemExit("Open-Meteo sigue respondiendo 429. Probá de nuevo en un rato; "
                     "lo descargado está guardado en data/raw/clima_cache/.")


def descargar_departamento(nombre, lat, lon, ini, fin):
    CACHE.mkdir(parents=True, exist_ok=True)
    archivo = CACHE / f"{normalizar(nombre).replace(' ', '_')}_{ini}_{fin}.csv"
    if archivo.exists():
        print("  (en caché)")
        return pd.read_csv(archivo, parse_dates=["fecha"])
    datos = pedir({"latitude": lat, "longitude": lon, "start_date": str(ini),
                   "end_date": str(fin), "daily": ",".join(VARIABLES),
                   "timezone": "America/Argentina/Cordoba"})
    d = pd.DataFrame(datos["daily"]).rename(columns={"time": "fecha"})
    d["fecha"] = pd.to_datetime(d["fecha"])
    d.to_csv(archivo, index=False)
    time.sleep(ESPERA_ENTRE_DEPTOS)   # cortesía con la API (solo si hubo pedido real)
    return d


def a_semanal(d):
    d = d.set_index("fecha")
    sem = d.resample("W-SUN", label="left", closed="right").agg({
        "temperature_2m_mean": "mean", "temperature_2m_max": "max",
        "temperature_2m_min": "min", "precipitation_sum": "sum",
        "relative_humidity_2m_mean": "mean",
    })
    # W-SUN con label left/closed right deja la etiqueta en el domingo previo;
    # la corremos un día para que coincida con el lunes ISO.
    sem.index = sem.index + pd.Timedelta(days=1)
    sem.index.name = "semana"
    return sem.reset_index()


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    ini, fin = rango_fechas()
    print(f"Clima de {ini} a {fin} para {len(DEPARTAMENTOS)} departamentos")
    partes = []
    for i, (nombre, (lat, lon)) in enumerate(DEPARTAMENTOS.items(), 1):
        print(f"[{i}/{len(DEPARTAMENTOS)}] {nombre}")
        sem = a_semanal(descargar_departamento(nombre, lat, lon, ini, fin))
        sem["departamento"] = nombre
        partes.append(sem)
    out = pd.concat(partes, ignore_index=True).rename(columns={
        "temperature_2m_mean": "temp_media", "temperature_2m_max": "temp_max",
        "temperature_2m_min": "temp_min", "precipitation_sum": "lluvia",
        "relative_humidity_2m_mean": "humedad",
    })
    out.to_csv(RAW / "clima_semanal.csv", index=False)
    print("Guardado", RAW / "clima_semanal.csv", len(out), "filas")


if __name__ == "__main__":
    main()
