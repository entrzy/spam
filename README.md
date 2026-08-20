Get-Service | Where-Object {
    $_.Name -match "LSEG|Refinitiv|Reuters|Workspace" -or
    $_.DisplayName -match "LSEG|Refinitiv|Reuters|Workspace"
} | Format-Table Status,Name,DisplayName -Auto



Get-Process | Where-Object {
    $_.ProcessName -match "LSEG|Refinitiv|Workspace|Eikon"
} | Select-Object ProcessName,Id,Path
