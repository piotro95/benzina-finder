"""Generazione report: tabella a console + export CSV."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

_COLONNE_REPORT = {
    "ranking": "#",
    "nome": "Impianto",
    "gestore": "Gestore",
    "indirizzo": "Indirizzo",
    "prezzo": "€/litro",
    "distanza_km": "Distanza (km)",
    "score": "Score",
    "dtComu": "Ultimo agg.",
}


def _formatta(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # Impianto: usa nome se presente, altrimenti gestore
    out["nome"] = out["nome"].fillna("").replace("", pd.NA).fillna(out["gestore"])
    cols = [c for c in _COLONNE_REPORT if c in out.columns]
    out = out[cols].rename(columns=_COLONNE_REPORT)
    if "€/litro" in out:
        out["€/litro"] = out["€/litro"].map(lambda x: f"{x:.3f}")
    if "Distanza (km)" in out:
        out["Distanza (km)"] = out["Distanza (km)"].map(lambda x: f"{x:.2f}")
    if "Score" in out:
        out["Score"] = out["Score"].map(lambda x: f"{x:.3f}")
    if "Ultimo agg." in out:
        out["Ultimo agg."] = pd.to_datetime(out["Ultimo agg."]).dt.strftime("%d/%m/%Y %H:%M")
    return out


def stampa_report(df: pd.DataFrame, cfg: dict) -> None:
    pos = cfg["posizione"]
    ric = cfg["ricerca"]
    print()
    print("=" * 78)
    print(f"  Distributori {ric['carburante']} self più convenienti")
    print(f"  Partenza : {pos['nome']}  ({pos['lat']:.4f}, {pos['lon']:.4f})")
    print(f"  Raggio   : {ric['raggio_km']} km   |   alpha (peso prezzo) = {cfg['score']['alpha']}")
    print(f"  Freschezza prezzi : entro {ric['max_giorni_freschezza']} giorni")
    print("=" * 78)
    if df.empty:
        print("  Nessun distributore soddisfa i criteri (controlla raggio/freschezza).")
        return
    print(_formatta(df).to_string(index=False))
    print("=" * 78)


def esporta_csv(df: pd.DataFrame, cfg: dict, cartella: str = "output") -> str | None:
    if df.empty:
        return None
    os.makedirs(cartella, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = os.path.join(cartella, f"distributori_{ts}.csv")
    _formatta(df).to_csv(path, index=False, sep=";")
    return path
