"""
Logica di filtro e scoring dei distributori.

Pipeline:
  1. filtro carburante + self
  2. distanza haversine dalla posizione di partenza
  3. filtro raggio
  4. filtro freschezza (dtComu entro N giorni)
  5. score pesato configurabile: alpha * prezzo_norm + (1-alpha) * dist_norm
"""

from __future__ import annotations

from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

import pandas as pd

_R_TERRA_KM = 6371.0088


def _haversine(lat1, lon1, lat2, lon2):
    """Distanza in km tra due punti (vettoriale su Series pandas)."""
    lat1, lon1, lat2, lon2 = map(radians_series, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (dlat / 2).apply(sin) ** 2 + lat1.apply(cos) * lat2.apply(cos) * (dlon / 2).apply(sin) ** 2
    return 2 * _R_TERRA_KM * a.apply(lambda x: asin(sqrt(x)))


def radians_series(s):
    """radians() applicato a una Series o a uno scalare."""
    if isinstance(s, pd.Series):
        return s.apply(radians)
    return pd.Series([radians(s)])


def _normalizza(serie: pd.Series) -> pd.Series:
    """Normalizzazione min-max. Se tutti i valori sono uguali ritorna 0."""
    lo, hi = serie.min(), serie.max()
    if hi == lo:
        return pd.Series(0.0, index=serie.index)
    return (serie - lo) / (hi - lo)


def trova_distributori(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Applica filtri e scoring, ritorna il top-N ordinato per score."""
    pos = cfg["posizione"]
    ric = cfg["ricerca"]
    alpha = float(cfg["score"]["alpha"])

    df = df.copy()

    # 1. filtro carburante (match case-insensitive sul nome)
    mask_carb = df["descCarburante"].astype(str).str.contains(
        ric["carburante"], case=False, na=False
    )
    df = df[mask_carb]

    # 2. filtro self
    if ric["solo_self"]:
        df = df[df["isSelf"] == True]  # noqa: E712

    # 3. distanza + filtro raggio
    df["distanza_km"] = _haversine(
        pd.Series([pos["lat"]] * len(df), index=df.index),
        pd.Series([pos["lon"]] * len(df), index=df.index),
        df["lat"], df["lon"],
    )
    df = df[df["distanza_km"] <= ric["raggio_km"]]

    # 4. freschezza: scarta prezzi più vecchi di N giorni
    limite = datetime.now() - timedelta(days=int(ric["max_giorni_freschezza"]))
    df = df[df["dtComu"] >= limite]

    if df.empty:
        return df

    # In caso di doppioni (stesso impianto, più record self) tieni il prezzo più basso
    df = df.sort_values("prezzo").drop_duplicates(subset=["idImpianto"], keep="first")

    # 5. score pesato
    df["prezzo_norm"] = _normalizza(df["prezzo"])
    df["dist_norm"] = _normalizza(df["distanza_km"])
    df["score"] = alpha * df["prezzo_norm"] + (1 - alpha) * df["dist_norm"]

    df = df.sort_values("score").head(int(ric["top_n"])).reset_index(drop=True)
    df.insert(0, "ranking", df.index + 1)
    return df
