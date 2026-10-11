"""Datos SINTÉTICOS para probar el pipeline sin internet. NO son reales:
no sirven para conclusiones epidemiológicas."""
import numpy as np
import pandas as pd
from config import DEPARTAMENTOS, RAW, ANIO_INICIO, ANIO_FIN, SEMILLA


def generar():
    rng = np.random.default_rng(SEMILLA)
    semanas = pd.date_range(f"{ANIO_INICIO}-01-04", f"{ANIO_FIN}-12-27", freq="W-MON")
    fuerza = {a: rng.choice([0.2, 0.5, 3.0], p=[0.4, 0.3, 0.3])
              for a in range(ANIO_INICIO, ANIO_FIN + 1)}
    fuerza[ANIO_FIN - 1] = 3.0   # garantiza una temporada fuerte dentro del test
    fuerza[ANIO_INICIO + 2] = 3.0
    clima, casos = [], []
    for dep, (lat, _) in DEPARTAMENTOS.items():
        n = len(semanas)
        doy = semanas.dayofyear.values
        temp = 19 + 8 * np.sin(2 * np.pi * (doy - 80) / 365) + rng.normal(0, 1.5, n) + (lat + 32) * 0.3
        lluvia = np.clip(rng.gamma(1.2, 18, n) * (1 + 0.5 * np.sin(2 * np.pi * (doy - 30) / 365)), 0, None)
        hum = np.clip(70 + 0.15 * (lluvia - 20) + rng.normal(0, 5, n), 30, 100)
        clima.append(pd.DataFrame({
            "semana": semanas, "departamento": dep, "temp_media": temp,
            "temp_max": temp + 6, "temp_min": temp - 6, "lluvia": lluvia, "humedad": hum}))
        s = pd.Series(temp).rolling(6, min_periods=1).mean().shift(4).fillna(15).values
        r = pd.Series(lluvia).rolling(6, min_periods=1).sum().shift(4).fillna(0).values
        f = np.array([fuerza[a] for a in semanas.year.values])
        lam = np.clip((s - 21) / 3, 0, None) ** 2 * (0.2 + r / 300) * f * (0.4 + rng.random())
        casos.append(pd.DataFrame({"semana": semanas, "departamento": dep,
                                   "casos": rng.poisson(lam)}))
    RAW.mkdir(parents=True, exist_ok=True)
    pd.concat(clima).to_csv(RAW / "clima_semanal.csv", index=False)
    pd.concat(casos).to_csv(RAW / "casos_semanales.csv", index=False)
    print("Datos sintéticos generados en data/raw/")


if __name__ == "__main__":
    generar()
