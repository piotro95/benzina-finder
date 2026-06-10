"""
Invio del report su Telegram.

Richiede due variabili d'ambiente (in CI: GitHub Secrets):
    TG_TOKEN    token del bot (da @BotFather)
    TG_CHAT_ID  id della chat dove inviare il messaggio

Il messaggio è formattato in HTML. Nessun dato viene scritto su disco:
il report vive solo nel messaggio inviato.
"""

from __future__ import annotations

import html
import os

import pandas as pd
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT = 20


def _componi_messaggio(df: pd.DataFrame, cfg: dict) -> str:
    pos = cfg["posizione"]
    ric = cfg["ricerca"]
    testa = (
        f"⛽ <b>Benzina self più conveniente</b>\n"
        f"📍 {html.escape(str(pos['nome']))} · raggio {ric['raggio_km']} km · "
        f"α={cfg['score']['alpha']}\n"
        f"🕒 prezzi entro {ric['max_giorni_freschezza']} gg\n"
    )
    if df.empty:
        return testa + "\n⚠️ Nessun distributore soddisfa i criteri."

    righe = []
    for _, r in df.iterrows():
        nome = html.escape(str(r.get("nome") or r.get("gestore") or "—"))
        indir = html.escape(str(r.get("indirizzo") or "—"))
        righe.append(
            f"<b>{int(r['ranking'])}. {nome}</b>\n"
            f"   {r['prezzo']:.3f} €/l · {r['distanza_km']:.2f} km\n"
            f"   <i>{indir}</i>"
        )
    return testa + "\n" + "\n\n".join(righe)


def invia_telegram(df: pd.DataFrame, cfg: dict) -> bool:
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("[warn] TG_TOKEN/TG_CHAT_ID non impostati: invio saltato.")
        return False

    payload = {
        "chat_id": chat_id,
        "text": _componi_messaggio(df, cfg),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(_API.format(token=token), json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[errore] Invio Telegram fallito: {exc}")
        return False
