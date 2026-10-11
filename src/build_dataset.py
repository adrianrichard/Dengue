"""Une casos + clima, crea variables con rezagos y el objetivo.
Resultado: data/processed/dataset.csv

Regla anti-fuga: todas las variables usan SOLO información hasta la semana t.
El objetivo es el número de casos en t + HORIZONTE_SEMANAS."""
import numpy as np
import pandas as pd
import population
from config import RAW, PROCESSED, DEPARTAMENTOS, HORIZONTE_SEMANAS, CASOS_HASTA


def construir():
    clima = pd.read_csv(RAW / "clima_semanal.csv", parse_dates=["semana"])
    casos = pd.read_csv(RAW / "casos_semanales.csv", parse_dates=["semana"])

    # Solo se modelan los años que tienen datos de casos: una semana sin registro
    # DENTRO de esos años es 0 casos; fuera de ellos es "sin dato" y no se usa.
    ini = pd.Timestamp(year=casos["semana"].dt.year.min(), month=1, day=1)
    fin = pd.Timestamp(year=casos["semana"].dt.year.max(), month=12, day=31)
    if CASOS_HASTA:
        fin = min(fin, pd.Timestamp(CASOS_HASTA))
    clima = clima[(clima["semana"] >= ini - pd.Timedelta(weeks=8)) & (clima["semana"] <= fin)]
    semanas = pd.DatetimeIndex(sorted(clima["semana"].unique()))
    grilla = pd.MultiIndex.from_product([list(DEPARTAMENTOS), semanas],
                                        names=["departamento", "semana"]).to_frame(index=False)
    df = grilla.merge(clima, on=["departamento", "semana"], how="left")
    df = df.merge(casos, on=["departamento", "semana"], how="left")
    df["casos"] = df["casos"].fillna(0)
    df.loc[df["semana"] < ini, "casos"] = np.nan   # colchón de clima: sin dato de casos
    print(f"Período con casos: {ini.date()} a {fin.date()} ({semanas.size} semanas de clima)")
    df = df.sort_values(["departamento", "semana"]).reset_index(drop=True)

    g = df.groupby("departamento", group_keys=False)
    # Casos pasados
    for k in (1, 2, 3, 4):
        df[f"casos_lag{k}"] = g["casos"].shift(k)
    df["casos_media4"] = g["casos"].transform(lambda s: s.rolling(4, min_periods=1).mean())
    df["casos_media8"] = g["casos"].transform(lambda s: s.rolling(8, min_periods=1).mean())
    # Clima acumulado (el efecto sobre el mosquito aparece con retraso)
    for v in ("temp_media", "humedad"):
        for w in (2, 4, 8):
            df[f"{v}_m{w}"] = g[v].transform(lambda s: s.rolling(w, min_periods=1).mean())
    for w in (4, 8):
        df[f"lluvia_s{w}"] = g["lluvia"].transform(lambda s: s.rolling(w, min_periods=1).sum())
    df["temp_min_m4"] = g["temp_min"].transform(lambda s: s.rolling(4, min_periods=1).mean())
    # Estacionalidad
    sem = df["semana"].dt.isocalendar().week.astype(int)
    df["sen_sem"] = np.sin(2 * np.pi * sem / 52)
    df["cos_sem"] = np.cos(2 * np.pi * sem / 52)
    df["dep_id"] = df["departamento"].map({d: i for i, d in enumerate(DEPARTAMENTOS)})

    # Objetivo: casos dentro de HORIZONTE semanas
    df["y_casos"] = g["casos"].shift(-HORIZONTE_SEMANAS)

    # Demografía (opcional): ver src/population.py
    pob = population.cargar()
    if pob is not None:
        df = df.merge(pob, on="departamento", how="left")
        df["casos_100k"] = df["casos"] / df["poblacion"] * 100_000
        g = df.groupby("departamento", group_keys=False)
        df["incid_media4"] = g["casos_100k"].transform(lambda s: s.rolling(4, min_periods=1).mean())
        df["log_poblacion"] = np.log(df["poblacion"])
        if "superficie_km2" in df.columns and df["superficie_km2"].notna().all():
            df["densidad"] = df["poblacion"] / df["superficie_km2"]

    df = df[df["semana"] >= ini].reset_index(drop=True)   # el colchón solo alimentó los rezagos

    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "dataset.csv", index=False)
    print("dataset.csv:", df.shape)
    return df


if __name__ == "__main__":
    construir()
