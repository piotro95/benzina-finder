# =====================================================================
# run_daily.ps1 — Esecuzione automatica giornaliera (locale)
# =====================================================================
# Pensato per Task Scheduler con trigger "All'accesso" (+ qualche minuto
# di ritardo). Esegue main.py SOLO se non è già stato eseguito con
# successo oggi: così se accendi/sblocchi il PC più volte al giorno,
# l'alert parte una volta sola.
#
# Se l'esecuzione fallisce (es. MIMIT non ancora raggiungibile appena
# accesa la connessione), il marker NON viene aggiornato: al prossimo
# accesso (o al prossimo trigger ripetuto di Task Scheduler) si riprova.
#
# Le credenziali/posizione NON sono qui: vengono caricate da
# secrets.local.ps1 (gitignored, da creare una sola volta — vedi
# secrets.local.ps1.example).
# =====================================================================

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$logFile    = Join-Path $scriptDir "run_daily.log"
$markerFile = Join-Path $scriptDir ".last_run"
$today      = Get-Date -Format "yyyy-MM-dd"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
}

# --- Guard: già eseguito con successo oggi? -------------------------
if (Test-Path $markerFile) {
    $lastRun = (Get-Content $markerFile -Raw).Trim()
    if ($lastRun -eq $today) {
        Log "Già eseguito oggi ($today). Esco senza fare nulla."
        exit 0
    }
}

# --- Carica credenziali locali ---------------------------------------
$secretsFile = Join-Path $scriptDir "secrets.local.ps1"
if (-not (Test-Path $secretsFile)) {
    Log "ERRORE: secrets.local.ps1 non trovato. Vedi secrets.local.ps1.example."
    exit 1
}
. $secretsFile

if (-not $env:PYTHON_EXE -or -not (Test-Path $env:PYTHON_EXE)) {
    Log "ERRORE: PYTHON_EXE non impostato o percorso non valido ($env:PYTHON_EXE)."
    exit 1
}

# --- Esegui ------------------------------------------------------------
Log "Avvio main.py..."
& $env:PYTHON_EXE main.py --telegram --no-export *>> $logFile
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Set-Content -Path $markerFile -Value $today -Encoding utf8
    Log "Eseguito con successo. Marker aggiornato a $today."
} else {
    Log "FALLITO (exit code $exitCode). Marker non aggiornato: si riprova al prossimo accesso."
}

exit $exitCode
