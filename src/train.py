"""Entrena y evalúa: baseline vs. Gradient Boosting (regresión y brote),
importancia de variables y mapa de riesgo de la última semana disponible."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (mean_absolute_error, mean_squared_error, precision_score,
                             recall_score, f1_score, roc_auc_score)
from sklearn.utils.class_weight import compute_sample_weight

from mapa import dibujar_mapa
from config import (PROCESSED, OUT, DEPARTAMENTOS, ANIOS_TEST, HORIZONTE_SEMANAS,
                    BROTE_MIN_CASOS, BROTE_K_STD, SEMILLA)

NO_FEATURES = {"departamento", "semana", "y_casos", "y_brote", "casos", "poblacion",
               "temp_media", "temp_max", "temp_min", "lluvia", "humedad",
               "casos_100k", "superficie_km2"}

def main():
    OUT.mkdir(exist_ok=True)
    df = pd.read_csv(PROCESSED / "dataset.csv", parse_dates=["semana"])
    features = [c for c in df.columns if c not in NO_FEATURES]

    # --- Split temporal (nunca aleatorio) -----------------------------------
    corte = df["semana"].max() - pd.DateOffset(years=ANIOS_TEST)
    entrenable = df.dropna(subset=features + ["y_casos"])
    train = entrenable[entrenable["semana"] <= corte - pd.Timedelta(weeks=HORIZONTE_SEMANAS)].copy()
    test = entrenable[entrenable["semana"] > corte].copy()  # hueco de H semanas evita fuga
    print(f"Train: {len(train)} filas | Test: {len(test)} filas | corte {corte.date()}")

    # --- Definición de brote (umbral calculado SOLO con train) ---------------
    est = train.groupby("departamento")["casos"].agg(["mean", "std"]).fillna(0)
    umbral = (est["mean"] + BROTE_K_STD * est["std"]).clip(lower=BROTE_MIN_CASOS)
    for d in (train, test):
        d["y_brote"] = (d["y_casos"] >= d["departamento"].map(umbral)).astype(int)
    print("Brotes en train:", int(train["y_brote"].sum()), "| en test:", int(test["y_brote"].sum()))

    Xtr, Xte = train[features], test[features]
    cat_mask = [f == "dep_id" for f in features]
    resultados = {}

    # --- Regresión: casos a H semanas -----------------------------------------
    base_pred = test["casos_lag1"].values                       # baseline: persistencia
    reg = HistGradientBoostingRegressor(loss="poisson", categorical_features=cat_mask,
                                        max_iter=300, learning_rate=0.05,
                                        random_state=SEMILLA).fit(Xtr, train["y_casos"])
    pred = np.clip(reg.predict(Xte), 0, None)
    rmse = lambda y, p: float(np.sqrt(mean_squared_error(y, p)))
    resultados["regresion"] = {
        "baseline_MAE": float(mean_absolute_error(test["y_casos"], base_pred)),
        "baseline_RMSE": rmse(test["y_casos"], base_pred),
        "modelo_MAE": float(mean_absolute_error(test["y_casos"], pred)),
        "modelo_RMSE": rmse(test["y_casos"], pred),
    }

    # --- Clasificación: ¿habrá brote en H semanas? ----------------------------
    clf = None
    if train["y_brote"].nunique() == 2 and test["y_brote"].nunique() == 2:
        clf = HistGradientBoostingClassifier(categorical_features=cat_mask, max_iter=300,
                                             learning_rate=0.05, random_state=SEMILLA)
        clf.fit(Xtr, train["y_brote"], sample_weight=compute_sample_weight("balanced", train["y_brote"]))
        proba = clf.predict_proba(Xte)[:, 1]
        etiqueta = (proba >= 0.5).astype(int)
        base_brote = (test["casos_lag1"] >= test["departamento"].map(umbral)).astype(int)
        resultados["brote"] = {
            "modelo_AUC": float(roc_auc_score(test["y_brote"], proba)),
            "modelo_precision": float(precision_score(test["y_brote"], etiqueta, zero_division=0)),
            "modelo_recall": float(recall_score(test["y_brote"], etiqueta, zero_division=0)),
            "modelo_F1": float(f1_score(test["y_brote"], etiqueta, zero_division=0)),
            "baseline_recall": float(recall_score(test["y_brote"], base_brote, zero_division=0)),
            "baseline_precision": float(precision_score(test["y_brote"], base_brote, zero_division=0)),
        }
    else:
        print("Aviso: train o test sin ambas clases de brote; se omite la clasificación.")

    (OUT / "metricas.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False))
    print(json.dumps(resultados, indent=2, ensure_ascii=False))

    # --- Importancia de variables (permutación, sobre test) -------------------
    modelo_imp = clf if clf is not None else reg
    y_imp = test["y_brote"] if clf is not None else test["y_casos"]
    imp = permutation_importance(modelo_imp, Xte, y_imp, n_repeats=5, random_state=SEMILLA)
    imp = pd.Series(imp.importances_mean, index=features).sort_values()
    imp.to_csv(OUT / "importancia_variables.csv", header=["importancia"])
    plt.figure(figsize=(7, 6)); imp.tail(15).plot.barh()
    plt.title("Variables que más influyen en la predicción"); plt.tight_layout()
    plt.savefig(OUT / "importancia_variables.png", dpi=130); plt.close()

    # --- Mapa de riesgo: última semana con datos completos de features --------
    ultima = df.dropna(subset=features)["semana"].max()
    actual = df[df["semana"] == ultima].copy()
    if clf is not None:
        actual["riesgo_brote"] = clf.predict_proba(actual[features])[:, 1]
    else:
        actual["riesgo_brote"] = np.nan
    actual["casos_previstos"] = np.clip(reg.predict(actual[features]), 0, None)
    actual["lat"] = actual["departamento"].map(lambda d: DEPARTAMENTOS[d][0])
    actual["lon"] = actual["departamento"].map(lambda d: DEPARTAMENTOS[d][1])
    cols = ["departamento", "semana", "riesgo_brote", "casos_previstos", "lat", "lon"]
    actual[cols].sort_values("riesgo_brote", ascending=False).to_csv(OUT / "riesgo_actual.csv", index=False)

    dibujar_mapa(actual, ultima, clf is not None, OUT / "mapa_riesgo.png")
    print("Salidas en", OUT)


if __name__ == "__main__":
    main()
