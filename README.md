# benzina-finder

Trova i distributori di **benzina self** più convenienti entro un raggio da una
posizione di partenza, combinando **prezzo** e **distanza** tramite uno **score
pesato configurabile**. Basato sugli open data del MIMIT (Osservaprezzi
Carburanti), con fallback sull'API `ospzApi/search/zone`.

## Caratteristiche

- **Fonte primaria**: CSV open data MIMIT (`prezzo_alle_8.csv` + `anagrafica_impianti_attivi.csv`), con cache locale.
- **Fallback automatico**: API Osservaprezzi se i CSV non sono raggiungibili.
- **Regola di freschezza**: scarta i prezzi comunicati (`dtComu`) da più di N giorni (default 3).
- **Solo self-service** (configurabile).
- **Score pesato**: `score = α · prezzo_norm + (1 − α) · distanza_norm`
  - `α = 1.0` → conta solo il prezzo
  - `α = 0.0` → conta solo la distanza
  - `α = 0.7` → compromesso orientato al prezzo (default)
- **Posizione di partenza configurabile** da `config.yaml` o da riga di comando.
- **Report**: tabella a console con *impianto, indirizzo, €/litro, distanza* + export CSV.

## Installazione

```bash
git clone https://github.com/<tuo-username>/benzina-finder.git
cd benzina-finder
python -m venv .venv && source .venv/bin/activate   # opzionale
pip install -r requirements.txt
```

## Uso

```bash
# Usa tutti i parametri da config.yaml
python main.py

# Cambia posizione/raggio/peso al volo (senza toccare il config)
python main.py --lat 41.9028 --lon 12.4964 --nome "Centro Roma" --raggio 5 --alpha 0.6

# Solo a video, senza esportare CSV
python main.py --no-export
```

| Flag        | Effetto                                  |
| ----------- | ---------------------------------------- |
| `--lat/--lon` | Override posizione di partenza         |
| `--nome`    | Etichetta posizione nel report           |
| `--raggio`  | Raggio di ricerca in km                  |
| `--alpha`   | Peso prezzo vs distanza (0..1)           |
| `--giorni`  | Massimo giorni di freschezza prezzo      |
| `--top`     | Numero di distributori nel report        |

## Configurazione

Tutti i default sono in [`config.yaml`](config.yaml): posizione, raggio,
carburante, solo-self, soglia di freschezza, `alpha`, URL sorgenti e cache.

## Struttura

```
benzina-finder/
├── config.yaml          # parametri (posizione, raggio, alpha, soglie)
├── main.py              # entrypoint + override CLI
├── requirements.txt
├── src/
│   ├── data_loader.py   # download CSV MIMIT + fallback API
│   ├── finder.py        # haversine, filtri, score pesato
│   └── report.py        # tabella console + export CSV
├── data_cache/          # CSV scaricati (gitignored)
└── output/              # report CSV generati (gitignored)
```

## Note sui dati

I gestori italiani sono obbligati per legge a comunicare i prezzi al MIMIT.
I CSV sono pubblicati ogni mattina con i prezzi in vigore alle 8 del giorno
precedente. La colonna `dtComu` è la data di comunicazione del prezzo, usata
per la regola di freschezza.

## Privacy (repo pubblica)

Questa repo è pensata per stare pubblica senza esporre dati personali:

- **La posizione reale NON è nel codice.** `config.yaml` contiene solo
  placeholder (`0.0`). Le coordinate vere si forniscono via:
  - `START_LAT` / `START_LON` / `START_NOME` (env o **GitHub Secrets**), oppure
  - `config.local.yaml` (gitignored) per l'uso da PC, oppure
  - flag `--lat --lon`.
  L'ambiente ha la precedenza sul file. Se la posizione non è impostata, il
  programma si rifiuta di partire.
- **Il report non viene mai committato.** In CI gira con `--no-export`: il
  risultato vive solo nel messaggio Telegram, il runner viene distrutto a fine
  job. Nessun CSV finisce nella repo.

## Alert automatico su Telegram (GitHub Actions)

Il workflow [`.github/workflows/alert.yml`](.github/workflows/alert.yml) esegue
lo script ogni mattina e invia il report su Telegram. È anche lanciabile a mano
dalla tab **Actions → Run workflow**.

**Costo:** su repo pubblica i runner standard sono gratuiti e illimitati, quindi
nessun costo e nessun account a pagamento.

### Setup (una tantum)

1. Crea un bot con [@BotFather](https://t.me/BotFather), ottieni il **token**.
2. Recupera il tuo **chat id** (es. scrivendo al bot e leggendo
   `https://api.telegram.org/bot<token>/getUpdates`).
3. Nella repo: **Settings → Secrets and variables → Actions → New repository secret**,
   crea questi secret:

   | Secret       | Valore                              |
   | ------------ | ----------------------------------- |
   | `START_LAT`  | latitudine partenza (es. `41.8536`) |
   | `START_LON`  | longitudine partenza (es. `12.5858`)|
   | `START_NOME` | etichetta (es. `Casa`)              |
   | `TG_TOKEN`   | token del bot Telegram              |
   | `TG_CHAT_ID` | id chat Telegram                    |

4. L'orario è in **UTC** nel cron (`30 6 * * *` = 08:30 ora legale italiana).
   Regolalo nel file se vuoi un orario civile fisso.

## Licenza

MIT
