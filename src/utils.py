import unicodedata
import pandas as pd


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres de departamentos."""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return t.lower().strip()


def lunes_de_semana(anio, semana):
    """Fecha del lunes de la semana ISO (aproxima la semana epidemiológica).
    Una semana 53 inexistente en ISO se lleva a la 52."""
    anio = list(anio); semana = [min(int(s), 53) for s in semana]
    f = pd.to_datetime([f"{int(a)}-W{s:02d}-1" for a, s in zip(anio, semana)],
                       format="%G-W%V-%u", errors="coerce")
    malas = f.isna() & pd.Series([s == 53 for s in semana]).values
    if malas.any():
        f2 = pd.to_datetime([f"{int(a)}-W52-1" for a in anio], format="%G-W%V-%u", errors="coerce")
        f = pd.DatetimeIndex(pd.Series(f).where(~malas, pd.Series(f2)))
    return f
