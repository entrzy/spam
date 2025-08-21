$skipping = $false
Get-Content "trace.log" -Wait | ForEach-Object {
  # START bloków do pominięcia
  if (-not $skipping -and ($_ -match "(?i)Message\s+contents:|multipart/related|Content-Transfer-Encod\w*\s*:\s*binary")) {
    $skipping = $true; return
  }

  if ($skipping) {
    # KONIEC bloku – dopasuj typowy nagłówek kolejnego wpisu (data + czas)
    if ($_ -match "^\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}:\d{3}") { $skipping = $false } else { return }
  }

  $_
} | Out-File "ws_trace.log" -Append -Encoding utf8
