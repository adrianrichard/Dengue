"""Lee los CSV de vigilancia de dengue del Ministerio de Salud, filtra Entre Ríos
y el evento Dengue, y los deja como casos por departamento y semana.
Resultado: data/raw/casos_semanales.csv"""
import pandas as pd
from config import (CARPETA_CASOS, COLUMNAS_CASOS, PROVINCIA_NOMBRE, EVENTO, RAW,
                    DEPARTAMENTOS)
from utils import normalizar, lunes_de_semana


def leer_csv(ruta):
    """Lee un CSV probando codificaciones (utf-8, utf-8 con BOM, cp1252, latin-1)
    y detectando el separador (',' o ';') a partir de la cabecera."""
    ultimo = None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(ruta, encoding=enc) as fh:
                cabecera = fh.readline()
            sep = ";" if cabecera.count(";") > cabecera.count(",") else ","
            df = pd.read_csv(ruta, sep=sep, encoding=enc, low_memory=False)
            print(f"  codificación: {enc} | separador: '{sep}'")
            return df
        except UnicodeDecodeError as e:
            ultimo = e
    raise SystemExit(f"No pude leer {ruta.name} ({ultimo}). Verificá que sea un CSV.")


# Nombres conocidos (normalizados: minúsculas, sin tildes; "año" -> "ano")
CANDIDATOS = {
    "anio": ["anio_min", "anio", "ano", "ano_min"],
    "semana": ["sepi_min", "semanas_epidemiologicas", "semana_epidemiologica", "sepi", "semana"],
    "casos": ["cantidad", "cantidad_casos", "casos"],
    "evento": ["evento", "evento_nombre"],
}


def _detectar_texto(df, clave):
    """Columna cuyo nombre contiene `clave`, ignorando ids; prefiere la que tiene 'nombre'."""
    ok = []
    for c in df.columns:
        n = normalizar(c)
        tokens = n.split("_")
        if clave in n and "id" not in tokens and not n.startswith("id"):
            ok.append((0 if "nombre" in tokens or "desc" in tokens else 1, c))
    return sorted(ok)[0][1] if ok else None


def _detectar_lista(df, candidatos):
    por_norm = {normalizar(c): c for c in df.columns}
    for cand in candidatos:
        if cand in por_norm:
            return por_norm[cand]
    return None


def resolver_columnas(df):
    c = dict(COLUMNAS_CASOS)
    c["provincia"] = c["provincia"] or _detectar_texto(df, "provincia")
    c["departamento"] = c["departamento"] or _detectar_texto(df, "departamento")
    for k, cand in CANDIDATOS.items():
        c[k] = c[k] or _detectar_lista(df, cand)
    faltan = [k for k, v in c.items() if v is None or v not in df.columns]
    if faltan:
        raise SystemExit(f"No encuentro las columnas {faltan}.\n"
                         f"Columnas del archivo: {list(df.columns)}\n"
                         "Escribí los nombres en COLUMNAS_CASOS (src/config.py)")
    return c


def _a_numero(serie):
    """Convierte a número; si hay texto tipo 'SE 10' o '2024-10' extrae el primer entero."""
    n = pd.to_numeric(serie, errors="coerce")
    if n.isna().mean() > 0.5:
        n = pd.to_numeric(serie.astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    return n


def main():
    archivos = sorted(CARPETA_CASOS.glob("*.csv")) if CARPETA_CASOS.exists() else []
    if not archivos:
        raise SystemExit(f"No hay CSV en {CARPETA_CASOS}. Descargalos de datos.salud.gob.ar "
                         "(ver README) o usá --sintetico en run_all.py.")
    partes = []
    for f in archivos:
        df = leer_csv(f)
        c = resolver_columnas(df)
        print(f"{f.name}: {len(df)} filas | columnas -> {c}")
        df = df[df[c["provincia"]].map(normalizar) == normalizar(PROVINCIA_NOMBRE)]
        eventos = df[c["evento"]].astype(str).value_counts()
        print("  eventos en el archivo (Entre Ríos):", {k: int(v) for k, v in eventos.head(6).items()})
        df = df[df[c["evento"]].map(normalizar).str.contains(normalizar(EVENTO), na=False)]
        if df.empty:
            print(f"  (sin filas de {PROVINCIA_NOMBRE} / {EVENTO} en este archivo)")
            continue
        partes.append(pd.DataFrame({
            "departamento": df[c["departamento"]].values,
            "semana": lunes_de_semana(_a_numero(df[c["anio"]]).fillna(0).astype(int),
                                      _a_numero(df[c["semana"]]).fillna(0).astype(int)),
            "casos": _a_numero(df[c["casos"]]).fillna(0).values,
        }))
    if not partes:
        raise SystemExit("Ninguna fila quedó tras filtrar provincia/evento. Revisá "
                         "PROVINCIA_NOMBRE y EVENTO en src/config.py")
    df = pd.concat(partes)
    if df["semana"].isna().any():
        print(f"Aviso: {int(df['semana'].isna().sum())} filas con año/semana inválidos (se descartan).")
        df = df.dropna(subset=["semana"])
    g = df.groupby(["departamento", "semana"], as_index=False)["casos"].sum()

    mapa = {normalizar(k): k for k in DEPARTAMENTOS}
    nombre_ok = g["departamento"].map(lambda x: mapa.get(normalizar(x)))
    desconocidos = sorted(g.loc[nombre_ok.isna(), "departamento"].unique())
    if desconocidos:
        print("Aviso: departamentos no reconocidos (se descartan):", desconocidos,
              "\n  -> si son válidos, agregalos/renombralos en DEPARTAMENTOS (src/config.py)")
    g["departamento"] = nombre_ok
    g = g.dropna(subset=["departamento"])
    g.to_csv(RAW / "casos_semanales.csv", index=False)
    print(f"Guardado casos_semanales.csv: {len(g)} filas | "
          f"{g['semana'].min().date()} a {g['semana'].max().date()} | "
          f"{int(g['casos'].sum())} casos totales")


if __name__ == "__main__":
    main()
