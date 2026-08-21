#requires -Version 5.1
<#
.SYNOPSIS
  IBM SPSS Modeler Server 18.3 - Connection Reset Diagnostic Monitor

.DESCRIPTION
  Designed for Modeler Server on Windows with:
    - Initial listener port: 28059
    - Configured Modeler session/worker port range: 50001-64000
    - Windows high/dynamic port range: 49152-65535

  The two ranges are tracked separately because TCPView can show both
  Modeler session ports and Windows ephemeral/client-side high ports.

  The script automatically identifies the PID listening on 28059 and tracks:
    - Host CPU / memory
    - Modeler listener process CPU%, memory, threads, handles
    - All TCP endpoints owned by that PID
    - Port 28059 state counts
    - Configured Modeler port-range 50001-64000 state counts
    - Windows high/dynamic port-range 49152-65535 state counts
    - System-wide TCP state counts
    - New/vanished LISTEN ports in 50001-64000
    - New/vanished PIDs owning sockets in 50001-64000
    - TIME_WAIT / CLOSE_WAIT / SYN_RECEIVED spikes
    - Listener PID changes/restarts

  Outputs:
    - Main rolling CSV (hourly)
    - Event/anomaly log
    - Detailed TCP snapshots around anomalies
    - Optional Windows event export

  Run elevated for best visibility.

.NOTES
  Pure PowerShell, read-only monitoring. No Sysinternals, dumps, or config changes.
#>

[CmdletBinding()]
param(
    [int]$InitialPort = 28059,
    [int]$SessionPortStart = 50001,
    [int]$SessionPortEnd = 64000,

    # Windows dynamic/high-port range visible in TCPView.
    # Default Windows ephemeral range typically begins at 49152.
    [int]$HighPortStart = 49152,
    [int]$HighPortEnd = 65535,

    [int]$IntervalSeconds = 3,
    [int]$DurationHours = 24,

    [string]$OutputDirectory = "C:\SPSS_Modeler_Diag",

    # Export Application/System Warning+Error events every N minutes. 0 disables.
    [int]$EventExportEveryMinutes = 10,
    [int]$EventLookbackMinutes = 15,

    # Thresholds for anomaly detection.
    [int]$CloseWaitWarn = 10,
    [int]$TimeWaitDeltaWarn = 50,
    [int]$EstablishedDeltaWarn = 30,
    [int]$ListenDeltaWarn = 10,
    [int]$SynReceivedWarn = 10,
    [int]$SessionPortPidDeltaWarn = 5,

    # Prevent repeated snapshot storms.
    [int]$AnomalyCooldownSeconds = 20
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-Directory {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -Path $Path -ItemType Directory -Force | Out-Null
    }
}

function Write-DiagLog {
    param(
        [Parameter(Mandatory)][string]$Message,
        [ValidateSet("INFO","WARN","ERROR")][string]$Level = "INFO"
    )
    $line = "{0}`t{1}`t{2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"), $Level, $Message
    Add-Content -LiteralPath $script:DiagLog -Value $line -Encoding UTF8
}

function Get-HourlyPath {
    param([string]$Prefix, [string]$Directory, [datetime]$Now)
    Join-Path $Directory ("{0}_{1}.csv" -f $Prefix, $Now.ToString("yyyyMMdd_HH"))
}

function Get-ModelerListener {
    param([int]$Port)

    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $listener) {
        return $null
    }

    $p = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    if (-not $p) {
        return $null
    }

    [pscustomobject]@{
        PID = $p.Id
        Process = $p
        LocalAddress = $listener.LocalAddress
        LocalPort = $listener.LocalPort
    }
}

function Get-ProcessCpuPercent {
    param(
        [int]$Pid,
        [hashtable]$Previous,
        [datetime]$Now
    )

    try {
        $p = Get-Process -Id $Pid -ErrorAction Stop
        $cpuSeconds = [double]($p.CPU)
        $pct = $null

        if ($Previous.ContainsKey($Pid)) {
            $prev = $Previous[$Pid]
            $elapsed = ($Now - $prev.Time).TotalSeconds
            $delta = $cpuSeconds - $prev.CpuSeconds

            if ($elapsed -gt 0) {
                $pct = ($delta / $elapsed / [Environment]::ProcessorCount) * 100
                if ($pct -lt 0) { $pct = 0 }
            }
        }

        $Previous[$Pid] = @{
            Time = $Now
            CpuSeconds = $cpuSeconds
        }

        [pscustomobject]@{
            Process = $p
            CpuPercent = $pct
            CpuTotalSeconds = $cpuSeconds
        }
    }
    catch {
        $null
    }
}

function Get-SystemMetrics {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $cpu = Get-CimInstance Win32_Processor
        $cpuPct = ($cpu | Measure-Object -Property LoadPercentage -Average).Average

        $totalMb = [math]::Round($os.TotalVisibleMemorySize / 1024, 2)
        $freeMb = [math]::Round($os.FreePhysicalMemory / 1024, 2)
        $usedMb = [math]::Round($totalMb - $freeMb, 2)
        $usedPct = if ($totalMb -gt 0) { [math]::Round(($usedMb / $totalMb) * 100, 2) } else { $null }

        [pscustomobject]@{
            CpuPercent = $cpuPct
            RamTotalMB = $totalMb
            RamFreeMB = $freeMb
            RamUsedMB = $usedMb
            RamUsedPercent = $usedPct
        }
    }
    catch {
        Write-DiagLog "Get-SystemMetrics failed: $($_.Exception.Message)" "WARN"
        [pscustomobject]@{
            CpuPercent = $null
            RamTotalMB = $null
            RamFreeMB = $null
            RamUsedMB = $null
            RamUsedPercent = $null
        }
    }
}

function Count-State {
    param([array]$Connections, [string]$State)
    @($Connections | Where-Object State -eq $State).Count
}

function Get-TcpSnapshot {
    param(
        [int]$InitialPort,
        [int]$SessionPortStart,
        [int]$SessionPortEnd,
        [int]$HighPortStart,
        [int]$HighPortEnd,
        [int]$ListenerPid
    )

    $all = @(Get-NetTCPConnection -ErrorAction SilentlyContinue)

    $init = @($all | Where-Object { $_.LocalPort -eq $InitialPort })

    $session = @($all | Where-Object {
        $_.LocalPort -ge $SessionPortStart -and $_.LocalPort -le $SessionPortEnd
    })

    $high = @($all | Where-Object {
        $_.LocalPort -ge $HighPortStart -and $_.LocalPort -le $HighPortEnd
    })

    $ownedByListener = if ($ListenerPid -gt 0) {
        @($all | Where-Object { $_.OwningProcess -eq $ListenerPid })
    } else {
        @()
    }

    $sessionListenPorts = @($session |
        Where-Object State -eq "Listen" |
        Select-Object -ExpandProperty LocalPort -Unique |
        Sort-Object)

    $sessionPids = @($session |
        Where-Object { $_.OwningProcess -gt 0 } |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Sort-Object)

    [pscustomobject]@{
        All = $all
        Initial = $init
        Session = $session
        OwnedByListener = $ownedByListener

        InitialTotal = $init.Count
        InitialEstablished = Count-State $init "Established"
        InitialListen = Count-State $init "Listen"
        InitialTimeWait = Count-State $init "TimeWait"
        InitialCloseWait = Count-State $init "CloseWait"
        InitialSynReceived = Count-State $init "SynReceived"

        SessionTotal = $session.Count
        SessionEstablished = Count-State $session "Established"
        SessionListen = Count-State $session "Listen"
        SessionTimeWait = Count-State $session "TimeWait"
        SessionCloseWait = Count-State $session "CloseWait"
        SessionSynReceived = Count-State $session "SynReceived"
        SessionFinWait1 = Count-State $session "FinWait1"
        SessionFinWait2 = Count-State $session "FinWait2"
        SessionListeningPorts = $sessionListenPorts
        SessionPids = $sessionPids

        High = $high
        HighTotal = $high.Count
        HighEstablished = Count-State $high "Established"
        HighListen = Count-State $high "Listen"
        HighTimeWait = Count-State $high "TimeWait"
        HighCloseWait = Count-State $high "CloseWait"
        HighSynSent = Count-State $high "SynSent"
        HighSynReceived = Count-State $high "SynReceived"
        HighFinWait1 = Count-State $high "FinWait1"
        HighFinWait2 = Count-State $high "FinWait2"

        ListenerOwnedTotal = $ownedByListener.Count
        ListenerOwnedEstablished = Count-State $ownedByListener "Established"
        ListenerOwnedListen = Count-State $ownedByListener "Listen"
        ListenerOwnedTimeWait = Count-State $ownedByListener "TimeWait"
        ListenerOwnedCloseWait = Count-State $ownedByListener "CloseWait"
        ListenerOwnedSynReceived = Count-State $ownedByListener "SynReceived"

        SystemTotal = $all.Count
        SystemEstablished = Count-State $all "Established"
        SystemListen = Count-State $all "Listen"
        SystemTimeWait = Count-State $all "TimeWait"
        SystemCloseWait = Count-State $all "CloseWait"
        SystemSynReceived = Count-State $all "SynReceived"
    }
}

function Export-DetailedTcpSnapshot {
    param(
        [datetime]$Now,
        [array]$Connections,
        [string]$Reason
    )

    $stamp = $Now.ToString("yyyyMMdd_HHmmss_fff")
    $safeReason = ($Reason -replace '[^a-zA-Z0-9_-]', '_')
    if ($safeReason.Length -gt 80) { $safeReason = $safeReason.Substring(0,80) }

    $path = Join-Path $script:SnapshotDir ("TCP_Snapshot_{0}_{1}.csv" -f $stamp, $safeReason)

    $rows = foreach ($c in $Connections) {
        [pscustomobject]@{
            Timestamp = $Now.ToString("yyyy-MM-dd HH:mm:ss.fff")
            LocalAddress = $c.LocalAddress
            LocalPort = $c.LocalPort
            RemoteAddress = $c.RemoteAddress
            RemotePort = $c.RemotePort
            State = $c.State
            OwningProcess = $c.OwningProcess
            AppliedSetting = $c.AppliedSetting
            OffloadState = $c.OffloadState
        }
    }

    $rows | Export-Csv -LiteralPath $path -NoTypeInformation -Encoding UTF8
    Write-DiagLog "Detailed TCP snapshot: $path" "INFO"
}

function Export-RecentEvents {
    param([datetime]$Now, [int]$LookbackMinutes)

    $start = $Now.AddMinutes(-$LookbackMinutes)
    $stamp = $Now.ToString("yyyyMMdd_HHmmss")

    foreach ($logName in @("Application","System")) {
        try {
            $events = Get-WinEvent -FilterHashtable @{
                LogName = $logName
                StartTime = $start
                Level = 1,2,3
            } -ErrorAction SilentlyContinue |
                Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message

            if ($events) {
                $path = Join-Path $script:EventsDir ("{0}_{1}.csv" -f $logName,$stamp)
                $events | Export-Csv -LiteralPath $path -NoTypeInformation -Encoding UTF8
            }
        }
        catch {
            Write-DiagLog "Event export failed for $logName: $($_.Exception.Message)" "WARN"
        }
    }
}


# -----------------------------
# Init
# -----------------------------

Ensure-Directory $OutputDirectory
$script:CsvDir = Join-Path $OutputDirectory "csv"
$script:SnapshotDir = Join-Path $OutputDirectory "snapshots"
$script:EventsDir = Join-Path $OutputDirectory "events"

foreach ($d in @($script:CsvDir,$script:SnapshotDir,$script:EventsDir)) {
    Ensure-Directory $d
}

$script:DiagLog = Join-Path $OutputDirectory "diagnostic.log"

$startTime = Get-Date
$endTime = $startTime.AddHours($DurationHours)

$previousCpu = @{}
$previous = $null
$previousListenerPid = $null
$lastAnomalyTime = [datetime]::MinValue
$lastEventExport = [datetime]::MinValue

Write-DiagLog ("START host={0}; initialPort={1}; modelerSessionRange={2}-{3}; highPortRange={4}-{5}; interval={6}s; duration={7}h" -f `
    $env:COMPUTERNAME,$InitialPort,$SessionPortStart,$SessionPortEnd,$HighPortStart,$HighPortEnd,$IntervalSeconds,$DurationHours)

Write-Host "SPSS Modeler Connection Reset Diagnostic started."
Write-Host "Output: $OutputDirectory"
Write-Host "Initial listener: $InitialPort"
Write-Host "Modeler session ports: $SessionPortStart-$SessionPortEnd"
Write-Host "Windows high/dynamic ports: $HighPortStart-$HighPortEnd"
Write-Host "Press Ctrl+C to stop."

while ((Get-Date) -lt $endTime) {

    $loopStart = Get-Date

    try {
        $listener = Get-ModelerListener -Port $InitialPort
        $listenerPid = if ($listener) { $listener.PID } else { 0 }

        if ($previousListenerPid -ne $null -and $listenerPid -ne $previousListenerPid) {
            Write-DiagLog "Listener PID changed: $previousListenerPid -> $listenerPid" "WARN"
        }
        $previousListenerPid = $listenerPid

        $procInfo = if ($listenerPid -gt 0) {
            Get-ProcessCpuPercent -Pid $listenerPid -Previous $previousCpu -Now $loopStart
        } else {
            $null
        }

        $system = Get-SystemMetrics
        $tcp = Get-TcpSnapshot -InitialPort $InitialPort `
                               -SessionPortStart $SessionPortStart `
                               -SessionPortEnd $SessionPortEnd `
                               -HighPortStart $HighPortStart `
                               -HighPortEnd $HighPortEnd `
                               -ListenerPid $listenerPid

        $newListenPorts = @()
        $goneListenPorts = @()
        $newSessionPids = @()
        $goneSessionPids = @()

        $deltaSessionEstablished = 0
        $deltaSessionTimeWait = 0
        $deltaSessionCloseWait = 0
        $deltaSessionListen = 0
        $deltaSystemTimeWait = 0

        if ($previous) {
            $newListenPorts = @($tcp.SessionListeningPorts | Where-Object { $_ -notin $previous.SessionListeningPorts })
            $goneListenPorts = @($previous.SessionListeningPorts | Where-Object { $_ -notin $tcp.SessionListeningPorts })

            $newSessionPids = @($tcp.SessionPids | Where-Object { $_ -notin $previous.SessionPids })
            $goneSessionPids = @($previous.SessionPids | Where-Object { $_ -notin $tcp.SessionPids })

            $deltaSessionEstablished = $tcp.SessionEstablished - $previous.SessionEstablished
            $deltaSessionTimeWait = $tcp.SessionTimeWait - $previous.SessionTimeWait
            $deltaSessionCloseWait = $tcp.SessionCloseWait - $previous.SessionCloseWait
            $deltaSessionListen = $tcp.SessionListen - $previous.SessionListen
            $deltaSystemTimeWait = $tcp.SystemTimeWait - $previous.SystemTimeWait
        }

        $p = if ($procInfo) { $procInfo.Process } else { $null }

        $row = [pscustomobject]@{
            Timestamp = $loopStart.ToString("yyyy-MM-dd HH:mm:ss.fff")
            Host = $env:COMPUTERNAME

            ListenerFound = [bool]$listener
            ListenerPID = $listenerPid
            ListenerProcessName = if ($p) { $p.ProcessName } else { "" }

            Host_CPU_Percent = $system.CpuPercent
            Host_RAM_Total_MB = $system.RamTotalMB
            Host_RAM_Free_MB = $system.RamFreeMB
            Host_RAM_Used_MB = $system.RamUsedMB
            Host_RAM_Used_Percent = $system.RamUsedPercent

            Listener_CPU_Percent = if ($procInfo -and $null -ne $procInfo.CpuPercent) { [math]::Round($procInfo.CpuPercent,2) } else { $null }
            Listener_CPU_Total_s = if ($procInfo) { [math]::Round($procInfo.CpuTotalSeconds,2) } else { $null }
            Listener_WorkingSet_MB = if ($p) { [math]::Round($p.WorkingSet64/1MB,2) } else { $null }
            Listener_PrivateMemory_MB = if ($p) { [math]::Round($p.PrivateMemorySize64/1MB,2) } else { $null }
            Listener_Threads = if ($p) { $p.Threads.Count } else { $null }
            Listener_Handles = if ($p) { $p.HandleCount } else { $null }

            Initial_Total = $tcp.InitialTotal
            Initial_Established = $tcp.InitialEstablished
            Initial_Listen = $tcp.InitialListen
            Initial_TimeWait = $tcp.InitialTimeWait
            Initial_CloseWait = $tcp.InitialCloseWait
            Initial_SynReceived = $tcp.InitialSynReceived

            Session_Total = $tcp.SessionTotal
            Session_Established = $tcp.SessionEstablished
            Session_Listen = $tcp.SessionListen
            Session_TimeWait = $tcp.SessionTimeWait
            Session_CloseWait = $tcp.SessionCloseWait
            Session_SynReceived = $tcp.SessionSynReceived
            Session_FinWait1 = $tcp.SessionFinWait1
            Session_FinWait2 = $tcp.SessionFinWait2

            Session_ListenPort_Count = $tcp.SessionListeningPorts.Count
            Session_PID_Count = $tcp.SessionPids.Count

            HighPort_Total = $tcp.HighTotal
            HighPort_Established = $tcp.HighEstablished
            HighPort_Listen = $tcp.HighListen
            HighPort_TimeWait = $tcp.HighTimeWait
            HighPort_CloseWait = $tcp.HighCloseWait
            HighPort_SynSent = $tcp.HighSynSent
            HighPort_SynReceived = $tcp.HighSynReceived
            HighPort_FinWait1 = $tcp.HighFinWait1
            HighPort_FinWait2 = $tcp.HighFinWait2

            ListenerOwned_Total = $tcp.ListenerOwnedTotal
            ListenerOwned_Established = $tcp.ListenerOwnedEstablished
            ListenerOwned_Listen = $tcp.ListenerOwnedListen
            ListenerOwned_TimeWait = $tcp.ListenerOwnedTimeWait
            ListenerOwned_CloseWait = $tcp.ListenerOwnedCloseWait
            ListenerOwned_SynReceived = $tcp.ListenerOwnedSynReceived

            System_TCP_Total = $tcp.SystemTotal
            System_Established = $tcp.SystemEstablished
            System_Listen = $tcp.SystemListen
            System_TimeWait = $tcp.SystemTimeWait
            System_CloseWait = $tcp.SystemCloseWait
            System_SynReceived = $tcp.SystemSynReceived

            Delta_Session_Established = $deltaSessionEstablished
            Delta_Session_TimeWait = $deltaSessionTimeWait
            Delta_Session_CloseWait = $deltaSessionCloseWait
            Delta_Session_Listen = $deltaSessionListen
            Delta_System_TimeWait = $deltaSystemTimeWait

            New_Listen_Ports = ($newListenPorts -join ";")
            Gone_Listen_Ports = ($goneListenPorts -join ";")
            New_Session_PIDs = ($newSessionPids -join ";")
            Gone_Session_PIDs = ($goneSessionPids -join ";")
        }

        $csvPath = Get-HourlyPath -Prefix "SPSS_Modeler_ResetDiag" -Directory $script:CsvDir -Now $loopStart

        if (Test-Path -LiteralPath $csvPath) {
            $row | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Append -Encoding UTF8
        } else {
            $row | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8
            Write-DiagLog "Created CSV: $csvPath"
        }

        # -----------------------------
        # Anomaly detection
        # -----------------------------
        $reasons = @()

        if (-not $listener) {
            $reasons += "NO_LISTENER_28059"
        }

        if ($tcp.SessionCloseWait -ge $CloseWaitWarn) {
            $reasons += "SESSION_CLOSE_WAIT=$($tcp.SessionCloseWait)"
        }

        if ($deltaSessionTimeWait -ge $TimeWaitDeltaWarn) {
            $reasons += "SESSION_TIME_WAIT_DELTA=+$deltaSessionTimeWait"
        }

        if ($deltaSessionEstablished -ge $EstablishedDeltaWarn) {
            $reasons += "SESSION_ESTABLISHED_DELTA=+$deltaSessionEstablished"
        }

        if ([math]::Abs($deltaSessionListen) -ge $ListenDeltaWarn) {
            $reasons += "SESSION_LISTEN_DELTA=$deltaSessionListen"
        }

        if ($tcp.SessionSynReceived -ge $SynReceivedWarn) {
            $reasons += "SESSION_SYN_RECEIVED=$($tcp.SessionSynReceived)"
        }

        if ($newSessionPids.Count -ge $SessionPortPidDeltaWarn) {
            $reasons += "NEW_SESSION_PIDS=$($newSessionPids.Count)"
        }

        if ($goneSessionPids.Count -ge $SessionPortPidDeltaWarn) {
            $reasons += "GONE_SESSION_PIDS=$($goneSessionPids.Count)"
        }

        if ($newListenPorts.Count -gt 0) {
            Write-DiagLog ("New session LISTEN ports: " + ($newListenPorts -join ",")) "INFO"
        }

        if ($goneListenPorts.Count -gt 0) {
            Write-DiagLog ("Gone session LISTEN ports: " + ($goneListenPorts -join ",")) "INFO"
        }

        if ($newSessionPids.Count -gt 0) {
            Write-DiagLog ("New session PIDs: " + ($newSessionPids -join ",")) "INFO"
        }

        if ($goneSessionPids.Count -gt 0) {
            Write-DiagLog ("Gone session PIDs: " + ($goneSessionPids -join ",")) "INFO"
        }

        if ($reasons.Count -gt 0 -and ($loopStart - $lastAnomalyTime).TotalSeconds -ge $AnomalyCooldownSeconds) {
            $reasonText = ($reasons -join " | ")
            Write-DiagLog "ANOMALY: $reasonText" "WARN"

            # Snapshot only relevant connections:
            # initial port + session range + sockets owned by listener PID
            $relevant = @($tcp.All | Where-Object {
                $_.LocalPort -eq $InitialPort -or
                ($_.LocalPort -ge $HighPortStart -and $_.LocalPort -le $HighPortEnd) -or
                ($listenerPid -gt 0 -and $_.OwningProcess -eq $listenerPid)
            })

            Export-DetailedTcpSnapshot -Now $loopStart -Connections $relevant -Reason $reasonText

            $lastAnomalyTime = $loopStart
        }

        # Periodic Event Viewer export
        if ($EventExportEveryMinutes -gt 0 -and
            ($loopStart - $lastEventExport).TotalMinutes -ge $EventExportEveryMinutes) {

            Export-RecentEvents -Now $loopStart -LookbackMinutes $EventLookbackMinutes
            $lastEventExport = $loopStart
        }


        $previous = [pscustomobject]@{
            SessionListeningPorts = @($tcp.SessionListeningPorts)
            SessionPids = @($tcp.SessionPids)
            SessionEstablished = $tcp.SessionEstablished
            SessionTimeWait = $tcp.SessionTimeWait
            SessionCloseWait = $tcp.SessionCloseWait
            SessionListen = $tcp.SessionListen
            SystemTimeWait = $tcp.SystemTimeWait
        }
    }
    catch {
        Write-DiagLog "Main loop error: $($_.Exception.Message)" "ERROR"
    }

    $elapsedMs = ((Get-Date) - $loopStart).TotalMilliseconds
    $sleepMs = ($IntervalSeconds * 1000) - [int]$elapsedMs
    if ($sleepMs -gt 0) {
        Start-Sleep -Milliseconds $sleepMs
    }
}

Write-DiagLog "STOP completed normally."
Write-Host "Monitoring completed."
Write-Host "Output: $OutputDirectory"
