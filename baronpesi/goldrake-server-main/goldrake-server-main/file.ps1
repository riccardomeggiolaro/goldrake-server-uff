# Ottieni tutte le connessioni TCP in stato TIME_WAIT
$connections = netstat -ano | Select-String "TIME_WAIT"

foreach ($connection in $connections) {
    # Estrai il PID dalla connessione
    $pid = $connection -replace '.*\s+(\d+)$', '$1'
    
    # Termina il processo con quel PID
    Stop-Process -Id $pid -Force
}
