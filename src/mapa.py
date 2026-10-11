"""Mapa político coroplético de Entre Ríos: colorea cada departamento según el riesgo.

Límites departamentales: IGN, publicados por Datos Argentina (CC-BY-4.0).
La primera vez descarga el GeoJSON nacional (archivo grande), se queda solo con
Entre Ríos y lo guarda en data/raw/departamentos_entre_rios.geojson.
Si no hay internet, podés poner ahí tu propio GeoJSON (con propiedad "nombre").

Uso suelto (sin reentrenar):  python src/mapa.py
"""
import json
import numpy as np
import pandas as pd
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Patch
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from config import RAW, OUT, DEPARTAMENTOS, HORIZONTE_SEMANAS
from utils import normalizar

URL_DEPARTAMENTOS = "https://infra.datos.gob.ar/georef/departamentos.geojson"
ID_PROVINCIA = "30"      # código INDEC de Entre Ríos
ARCHIVO_GEO = RAW / "departamentos_entre_rios.geojson"

# Categorías para la probabilidad de brote
CORTES = [0, 0.25, 0.50, 0.75, 1.0001]
NOMBRES = ["Bajo (<25 %)", "Moderado (25–50 %)", "Alto (50–75 %)", "Muy alto (≥75 %)"]
COLORES = ["#ffffb2", "#fecc5c", "#fd8d3c", "#e31a1c"]


# ---------------------------------------------------------------- geometrías --
def _filtrar_provincia(datos):
    feats = [f for f in datos.get("features", [])
             if str((f.get("properties", {}).get("provincia") or {}).get("id")) == ID_PROVINCIA]
    return {"type": "FeatureCollection", "features": feats}


def _guardar(fc):
    if not fc["features"]:
        raise SystemExit("El GeoJSON no tiene departamentos de Entre Ríos (provincia.id = 30).")
    RAW.mkdir(parents=True, exist_ok=True)
    ARCHIVO_GEO.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"Guardado {ARCHIVO_GEO.name}: {len(fc['features'])} departamentos")


def descargar_geometrias():
    print("Descargando límites departamentales (IGN / Datos Argentina)... puede tardar")
    r = requests.get(URL_DEPARTAMENTOS, timeout=600)
    r.raise_for_status()
    _guardar(_filtrar_provincia(r.json()))


def cargar_geometrias():
    """{nombre normalizado: (geometry, (lon, lat) del rótulo)} o None si no se pudo."""
    if not ARCHIVO_GEO.exists():
        try:
            descargar_geometrias()
        except (requests.RequestException, ValueError) as e:
            print(f"Aviso: no pude obtener los polígonos ({e}). Uso el mapa de puntos.\n"
                  f"  Si tenés el GeoJSON, guardalo como {ARCHIVO_GEO}")
            return None
    fc = json.loads(ARCHIVO_GEO.read_text(encoding="utf-8"))
    conocidos = {normalizar(d): d for d in DEPARTAMENTOS}
    geo = {}
    for f in fc["features"]:
        p = f.get("properties", {})
        nombre = p.get("nombre") or p.get("nombre_completo") or ""
        clave = conocidos.get(normalizar(nombre).replace("departamento ", ""))
        if clave is None:
            print(f"Aviso: polígono '{nombre}' no coincide con DEPARTAMENTOS; se ignora.")
            continue
        c = p.get("centroide")
        centro = (c["lon"], c["lat"]) if c else None
        geo[clave] = (f["geometry"], centro)
    return geo


def _area(anillo):
    x, y = np.asarray(anillo, float)[:, 0], np.asarray(anillo, float)[:, 1]
    return 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])


def _path(geometry):
    """Path de matplotlib con huecos bien orientados (exterior antihorario, huecos horarios)."""
    polis = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    paths = []
    for poli in polis:
        for i, anillo in enumerate(poli):
            a = np.asarray(anillo, float)[:, :2]
            if not np.allclose(a[0], a[-1]):
                a = np.vstack([a, a[0]])
            if (_area(a) > 0) != (i == 0):      # exterior debe ser >0, huecos <0
                a = a[::-1]
            codes = np.full(len(a), Path.LINETO); codes[0] = Path.MOVETO; codes[-1] = Path.CLOSEPOLY
            paths.append(Path(a, codes))
    return Path.make_compound_path(*paths)


def _centro(path):
    v = path.vertices
    return (v[:, 0].min() + v[:, 0].max()) / 2, (v[:, 1].min() + v[:, 1].max()) / 2


# --------------------------------------------------------------------- mapas --
def _categoria(p):
    return int(np.digitize(p, CORTES[1:-1]))


def dibujar_mapa(actual, ultima, por_proba, archivo):
    """actual: DataFrame con departamento, riesgo_brote, casos_previstos (+ lat/lon)."""
    geo = cargar_geometrias()
    if geo is None:
        return _mapa_puntos(actual, ultima, por_proba, archivo)

    col = "riesgo_brote" if por_proba else "casos_previstos"
    valores = actual.set_index("departamento")[col]
    fig, ax = plt.subplots(figsize=(7, 8))
    norm = Normalize(vmin=0, vmax=max(float(valores.max()), 1e-9))
    cmap = plt.get_cmap("YlOrRd")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_axis_off()
    for dep, (geom, centro) in geo.items():
        if dep not in valores.index:
            continue
        v = float(valores[dep])
        color = COLORES[_categoria(v)] if por_proba else cmap(norm(v))
        path = _path(geom)
        ax.add_patch(PathPatch(path, facecolor=color, edgecolor="#333333", linewidth=0.8))
        x, y = centro if centro else _centro(path)
        texto = f"{dep}\n{v:.0000%}" if por_proba else f"{dep}\n{v:.1f}"
        ax.text(x, y, texto, ha="center", va="center", fontsize=7, color="black",
                path_effects=[pe.withStroke(linewidth=2, foreground="white")])

    faltan = sorted(set(valores.index) - set(geo))
    if faltan:
        print("Aviso: departamentos sin polígono:", faltan)

    ax.autoscale_view()
    ax.set_xlim(-61.0, -57.5); ax.set_ylim(-34.1, -30.0)
    ax.set_aspect(1 / np.cos(np.radians(32)))     # evita deformar el mapa
    if por_proba:
        ax.legend(handles=[Patch(facecolor=c, edgecolor="#333", label=n)
                           for c, n in zip(COLORES, NOMBRES)],
                  title="Riesgo de brote", loc="lower left", fontsize=8)
        sub = "Probabilidad estimada de que los casos superen el umbral de brote"
    else:
        fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=0.7, label="Casos previstos")
        sub = "Casos semanales previstos"
    ax.set_title(f"Entre Ríos – riesgo de dengue a {HORIZONTE_SEMANAS} semanas\n"
                 f"(desde la semana del {ultima:%d/%m/%Y})\n{sub}", fontsize=10)
    fig.text(0.01, 0.01, "Límites: IGN / Datos Argentina (CC-BY-4.0)", fontsize=6, color="gray")
    fig.tight_layout()
    fig.savefig(archivo, dpi=150)
    plt.close(fig)
    print("Mapa guardado:", archivo)


def _mapa_puntos(actual, ultima, por_proba, archivo):
    """Alternativa sin polígonos: un círculo por departamento."""
    color = actual["riesgo_brote"] if por_proba else actual["casos_previstos"]
    plt.figure(figsize=(6, 7))
    sc = plt.scatter(actual["lon"], actual["lat"], c=color, cmap="YlOrRd", s=450,
                     edgecolor="k", vmin=0, vmax=1 if por_proba else None)
    for _, r in actual.iterrows():
        plt.annotate(r["departamento"], (r["lon"], r["lat"]), fontsize=7, ha="center", va="center")
    plt.colorbar(sc, label="Probabilidad de brote" if por_proba else "Casos previstos")
    plt.title(f"Riesgo a {HORIZONTE_SEMANAS} semanas desde {ultima.date()}")
    plt.savefig(archivo, dpi=130); plt.close()


if __name__ == "__main__":
    df = pd.read_csv(OUT / "riesgo_actual.csv", parse_dates=["semana"])
    dibujar_mapa(df, df["semana"].max(), df["riesgo_brote"].notna().all(), OUT / "mapa_riesgo.png")
