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
   | `START_LAT`  | latitudine partenza (es. `41.8902`) |
   | `START_LON`  | longitudine partenza (es. `12.4922`)|
   | `START_NOME` | etichetta (es. `Casa`)              |
   | `TG_TOKEN`   | token del bot Telegram              |
   | `TG_CHAT_ID` | id chat Telegram                    |

4. L'orario è in **UTC** nel cron (`30 6 * * *` = 08:30 ora legale italiana).
   Regolalo nel file se vuoi un orario civile fisso.

## Automazione locale (Windows Task Scheduler) — consigliata

GitHub Actions con cron + runner self-hosted soffre di un bug noto di
GitHub: i job schedulati possono restare "in coda" indefinitamente anche
con il runner online, e vengono eseguiti solo dopo un trigger manuale.
Per un alert quotidiano affidabile, la soluzione è eseguire lo script
**localmente**, tramite Task Scheduler di Windows. GitHub Actions resta
disponibile per i lanci manuali (`workflow_dispatch`).

### Setup (una tantum)

1. **Clona la repo** nella cartella dei tuoi progetti, es.:
   ```powershell
   cd "C:\Users\PietroRomei\OneDrive - Key to Energy srl\Documenti\Progetti_Py"
   git clone https://github.com/piotro95/benzina-finder.git
   cd benzina-finder
   ```

2. **Crea le credenziali locali** (mai versionate):
   ```powershell
   Copy-Item secrets.local.ps1.example secrets.local.ps1
   notepad secrets.local.ps1
   ```
   Inserisci: percorso `PYTHON_EXE`, `START_LAT`/`START_LON`/`START_NOME`,
   `TG_TOKEN`, `TG_CHAT_ID` (gli stessi valori usati nei GitHub Secrets).

3. **Test manuale** prima di schedulare:
   ```powershell
   .\run_daily.ps1
   ```
   Controlla `run_daily.log` e verifica l'arrivo del messaggio Telegram.
   Rilancialo una seconda volta: deve uscire subito con "Già eseguito oggi".

4. **Crea l'attività in Task Scheduler** (Utilità di pianificazione —
   non richiede privilegi di amministratore per un'attività utente):
   - **Crea attività di base** → Nome: `Benzina Finder Daily`
   - **Trigger**: *All'accesso* → in "Impostazioni avanzate" spunta
     **"Ritarda attività per:"** e imposta `5 minuti`
   - **Azione**: *Avvia un programma*
     - Programma: `powershell.exe`
     - Argomenti:
       ```
       -NoProfile -ExecutionPolicy Bypass -File "C:\Users\PietroRomei\OneDrive - Key to Energy srl\Documenti\Progetti_Py\benzina-finder\run_daily.ps1"
       ```
   - (Opzionale, per resilienza) Nella scheda **Impostazioni** dell'attività,
     spunta *"Se l'attività non riesce, riavvia ogni:"* `30 minuti`,
     *"Tentativi massimi:"* `3` — utile se al login la rete non è
     ancora pronta.

Da quel momento: ad ogni accesso al PC, dopo 5 minuti lo script controlla
se ha già girato oggi; se no, esegue e invia il report su Telegram.

## Licenza

MIT
