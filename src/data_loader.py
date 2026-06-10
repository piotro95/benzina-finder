"""
Caricamento dati distributori carburante.

Fonte primaria : open data CSV del MIMIT (prezzo + anagrafica).
  Il CSV prezzi contiene la colonna `dtComu` (data comunicazione),
  indispensabile per la regola di freschezza dei 3 giorni.
Fallback        : API ospzApi/search/zone, usata solo se i CSV non
  sono raggiungibili. L'API espone comunque il campo data.
"""

from __future__ import annotations

import io
import os
import time
from datetime import datetime

import pandas as pd
import requests

# Header CSV MIMIT: la prima riga è una data di estrazione, l'header vero
# è alla seconda riga (skiprows=1). Separatore ';'.
_CSV_SKIPROWS = 1
_CSV_SEP = ";"
_TIMEOUT = 30


def _cache_path(cache_dir: str, name: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, name)


def _is_fresh(path: str, max_ore: float) -> bool:
    if not os.path.exists(path):
        return False
    eta_ore = (time.time() - os.path.getmtime(path)) / 3600.0
    return eta_ore < max_ore


def _download(url: str, dest: str) -> None:
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    with open(dest, "wb") as fh:
        fh.write(resp.content)


def carica_csv(cfg: dict) -> pd.DataFrame:
    """Scarica (o riusa da cache) i due CSV MIMIT e li unisce per idImpianto.

    Ritorna un DataFrame con colonne normalizzate:
        idImpianto, gestore, bandiera, nome, indirizzo, comune, provincia,
        lat, lon, descCarburante, prezzo, isSelf, dtComu
    """
    dati = cfg["dati"]
    cache_dir = dati["cache_dir"]
    p_prezzi = _cache_path(cache_dir, "prezzo_alle_8.csv")
    p_anag = _cache_path(cache_dir, "anagrafica_impianti_attivi.csv")

    if not _is_fresh(p_prezzi, dati["cache_max_ore"]):
        _download(dati["url_prezzi"], p_prezzi)
    if not _is_fresh(p_anag, dati["cache_max_ore"]):
        _download(dati["url_anagrafica"], p_anag)

    prezzi = pd.read_csv(
        p_prezzi, sep=_CSV_SEP, skiprows=_CSV_SKIPROWS, dtype=str,
        engine="python", on_bad_lines="skip",
    )
    anag = pd.read_csv(
        p_anag, sep=_CSV_SEP, skiprows=_CSV_SKIPROWS, dtype=str,
        engine="python", on_bad_lines="skip",
    )

    prezzi.columns = [c.strip() for c in prezzi.columns]
    anag.columns = [c.strip() for c in anag.columns]

    # Normalizza i nomi delle colonne dell'anagrafica (variano leggermente)
    rinomina_anag = {
        "idImpianto": "idImpianto",
        "Gestore": "gestore",
        "Bandiera": "bandiera",
        "Nome Impianto": "nome",
        "Indirizzo": "indirizzo",
        "Comune": "comune",
        "Provincia": "provincia",
        "Latitudine": "lat",
        "Longitudine": "lon",
    }
    anag = anag.rename(columns={k: v for k, v in rinomina_anag.items() if k in anag.columns})

    df = prezzi.merge(anag, on="idImpianto", how="inner")

    # Conversioni di tipo
    df["prezzo"] = pd.to_numeric(df["prezzo"].str.replace(",", "."), errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"].astype(str).str.replace(",", "."), errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"].astype(str).str.replace(",", "."), errors="coerce")
    df["isSelf"] = df["isSelf"].astype(str).str.strip().isin(["1", "true", "True"])
    df["dtComu"] = pd.to_datetime(df["dtComu"], format="%d/%m/%Y %H:%M:%S", errors="coerce")

    return df.dropna(subset=["prezzo", "lat", "lon", "dtComu"])


def carica_api(cfg: dict) -> pd.DataFrame:
    """Fallback: interroga l'API ospzApi/search/zone attorno alla posizione."""
    pos = cfg["posizione"]
    payload = {
        "points": [{"lat": pos["lat"], "lng": pos["lon"]}],
        "radius": cfg["ricerca"]["raggio_km"],
        "fuelType": "1-x",   # benzina
        "priceOrder": "asc",
    }
    resp = requests.post(cfg["dati"]["api_fallback"], json=payload, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    righe = []
    for imp in data.get("results", []):
        for f in imp.get("fuels", []):
            righe.append({
                "idImpianto": imp.get("id"),
                "gestore": imp.get("brand") or imp.get("name"),
                "bandiera": imp.get("brand"),
                "nome": imp.get("name"),
                "indirizzo": imp.get("address"),
                "comune": imp.get("city"),
                "provincia": None,
                "lat": imp.get("location", {}).get("lat"),
                "lon": imp.get("location", {}).get("lng"),
                "descCarburante": f.get("name"),
                "prezzo": f.get("price"),
                "isSelf": f.get("isSelf"),
                "dtComu": pd.to_datetime(f.get("insertDate"), errors="coerce"),
            })
    return pd.DataFrame(righe)


def carica_dati(cfg: dict) -> pd.DataFrame:
    """Tenta i CSV; in caso di errore di rete ricade sull'API."""
    try:
        return carica_csv(cfg)
    except Exception as exc:  # rete MIMIT non raggiungibile, ecc.
        print(f"[warn] CSV non disponibili ({exc}). Uso fallback API.")
        return carica_api(cfg)
