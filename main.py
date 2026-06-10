#!/usr/bin/env python3
"""
benzina-finder — punto di ingresso.

Trova i distributori di benzina self più convenienti entro un raggio dalla
posizione di partenza, combinando prezzo e distanza con uno score pesato.

Uso base (legge tutto da config.yaml):
    python main.py

Override da riga di comando (utili per cambiare giornata/posizione al volo):
    python main.py --lat 41.90 --lon 12.49 --raggio 5 --alpha 0.6
    python main.py --no-export
"""

from __future__ import annotations

import argparse
import os
import sys

import yaml

from src.data_loader import carica_dati
from src.finder import trova_distributori
from src.report import esporta_csv, stampa_report
from src.telegram import invia_telegram


def carica_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    # Sovrascrittura opzionale da config.local.yaml (gitignored, uso locale)
    if os.path.exists("config.local.yaml"):
        with open("config.local.yaml", "r", encoding="utf-8") as fh:
            local = yaml.safe_load(fh) or {}
        cfg = _merge(cfg, local)
    # L'ambiente ha la precedenza (usato dai GitHub Secrets in CI)
    if os.getenv("START_LAT"):
        cfg["posizione"]["lat"] = float(os.environ["START_LAT"])
    if os.getenv("START_LON"):
        cfg["posizione"]["lon"] = float(os.environ["START_LON"])
    if os.getenv("START_NOME"):
        cfg["posizione"]["nome"] = os.environ["START_NOME"]
    return cfg


def _merge(base: dict, over: dict) -> dict:
    """Merge ricorsivo superficiale di due dict di config."""
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def applica_override(cfg: dict, args: argparse.Namespace) -> dict:
    if args.lat is not None:
        cfg["posizione"]["lat"] = args.lat
        cfg["posizione"]["nome"] = args.nome or "Posizione personalizzata"
    if args.lon is not None:
        cfg["posizione"]["lon"] = args.lon
    if args.raggio is not None:
        cfg["ricerca"]["raggio_km"] = args.raggio
    if args.alpha is not None:
        cfg["score"]["alpha"] = args.alpha
    if args.giorni is not None:
        cfg["ricerca"]["max_giorni_freschezza"] = args.giorni
    if args.top is not None:
        cfg["ricerca"]["top_n"] = args.top
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser(description="Trova benzina self più conveniente.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--lat", type=float, help="Latitudine partenza (override)")
    ap.add_argument("--lon", type=float, help="Longitudine partenza (override)")
    ap.add_argument("--nome", type=str, help="Etichetta posizione (override)")
    ap.add_argument("--raggio", type=float, help="Raggio km (override)")
    ap.add_argument("--alpha", type=float, help="Peso prezzo 0..1 (override)")
    ap.add_argument("--giorni", type=int, help="Max giorni freschezza (override)")
    ap.add_argument("--top", type=int, help="Numero risultati (override)")
    ap.add_argument("--no-export", action="store_true", help="Non esportare CSV")
    ap.add_argument("--telegram", action="store_true",
                    help="Invia il report su Telegram (richiede TG_TOKEN e TG_CHAT_ID)")
    args = ap.parse_args()

    cfg = applica_override(carica_config(args.config), args)

    # Guard: senza una posizione valida non procedere (placeholder = 0,0)
    if abs(cfg["posizione"]["lat"]) < 0.001 and abs(cfg["posizione"]["lon"]) < 0.001:
        print("[errore] Posizione non impostata. Definisci START_LAT/START_LON "
              "(env o GitHub Secret), oppure config.local.yaml, oppure --lat/--lon.")
        return 2

    print("[info] Carico dati MIMIT (CSV con fallback API)...")
    df = carica_dati(cfg)
    print(f"[info] {len(df)} record carburante caricati.")

    risultati = trova_distributori(df, cfg)
    stampa_report(risultati, cfg)

    if not args.no_export:
        path = esporta_csv(risultati, cfg)
        if path:
            print(f"[info] Report salvato in: {path}")

    if args.telegram:
        ok = invia_telegram(risultati, cfg)
        print(f"[info] Invio Telegram: {'ok' if ok else 'fallito'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
