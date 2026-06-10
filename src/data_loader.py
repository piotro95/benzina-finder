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


def _leggi_csv_mimit(path: str) -> pd.DataFrame:
    """Legge un CSV MIMIT gestendo la riga di intestazione variabile.

    I file MIMIT hanno una prima riga di avviso (es. 'Estrazione del ...;;')
    e l'header vero alla riga successiva. A volte però l'header è già in
    prima riga. Rileviamo la riga giusta cercando 'idImpianto'.
    """
    # Leggi le prime righe grezze per trovare dov'è l'header
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        prime = [next(fh, "") for _ in range(5)]
    skip = 0
    for i, riga in enumerate(prime):
        if "idImpianto" in riga:
            skip = i
            break
    df = pd.read_csv(
        path, sep=_CSV_SEP, skiprows=skip, dtype=str,
        engine="python", on_bad_lines="skip", encoding="utf-8-sig",
    )
    # Normalizza: togli spazi e BOM dai nomi colonna
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    return df


def _col(df: pd.DataFrame, *nomi: str) -> str | None:
    """Trova il nome reale di una colonna fra varianti (case-insensitive)."""
    lower = {c.lower(): c for c in df.columns}
    for n in nomi:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def carica_csv(cfg: dict) -> pd.DataFrame:
    """Scarica (o riusa da cache) i due CSV MIMIT e li unisce per idImpianto."""
    dati = cfg["dati"]
    cache_dir = dati["cache_dir"]
    p_prezzi = _cache_path(cache_dir, "prezzo_alle_8.csv")
    p_anag = _cache_path(cache_dir, "anagrafica_impianti_attivi.csv")

    if not _is_fresh(p_prezzi, dati["cache_max_ore"]):
        _download(dati["url_prezzi"], p_prezzi)
    if not _is_fresh(p_anag, dati["cache_max_ore"]):
        _download(dati["url_anagrafica"], p_anag)

    prezzi = _leggi_csv_mimit(p_prezzi)
    anag = _leggi_csv_mimit(p_anag)

    # Individua le colonne reali (robusto a maiuscole/spazi)
    id_p = _col(prezzi, "idImpianto")
    id_a = _col(anag, "idImpianto")
    if id_p is None or id_a is None:
        raise KeyError(
            f"Colonna idImpianto non trovata. "
            f"Prezzi={list(prezzi.columns)} Anag={list(anag.columns)}"
        )

    # Rinomina su nomi standard
    prezzi = prezzi.rename(columns={
        id_p: "idImpianto",
        _col(prezzi, "descCarburante", "carburante"): "descCarburante",
        _col(prezzi, "prezzo"): "prezzo",
        _col(prezzi, "isSelf"): "isSelf",
        _col(prezzi, "dtComu"): "dtComu",
    })
    anag = anag.rename(columns={
        id_a: "idImpianto",
        _col(anag, "Gestore"): "gestore",
        _col(anag, "Bandiera"): "bandiera",
        _col(anag, "Nome Impianto", "Nome"): "nome",
        _col(anag, "Indirizzo"): "indirizzo",
        _col(anag, "Comune"): "comune",
        _col(anag, "Provincia"): "provincia",
        _col(anag, "Latitudine"): "lat",
        _col(anag, "Longitudine"): "lon",
    })

    df = prezzi.merge(anag, on="idImpianto", how="inner")

    # Conversioni di tipo
    df["prezzo"] = pd.to_numeric(
        df["prezzo"].astype(str).str.replace(",", "."), errors="coerce")
    df["lat"] = pd.to_numeric(
        df["lat"].astype(str).str.replace(",", "."), errors="coerce")
    df["lon"] = pd.to_numeric(
        df["lon"].astype(str).str.replace(",", "."), errors="coerce")
    df["isSelf"] = df["isSelf"].astype(str).str.strip().isin(["1", "true", "True"])
    df["dtComu"] = pd.to_datetime(
        df["dtComu"], format="%d/%m/%Y %H:%M:%S", errors="coerce")

    out = df.dropna(subset=["prezzo", "lat", "lon", "dtComu"])
    print(f"[info] CSV MIMIT: {len(prezzi)} prezzi, {len(anag)} impianti, "
          f"{len(out)} record validi dopo merge.")
    return out


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
