"E:\JBCS-jsvc-1.0\sbin\prunsrv.exe" //PS//JBossEAP7
reg query "HKLM\SOFTWARE\Apache Software Foundation\ProcRun 2.0\JBossEAP7" /s /reg:32
reg query "HKLM\SOFTWARE\Apache Software Foundation\ProcRun 2.0\JBossEAP7" /s /reg:64
reg query "HKLM\SYSTEM\CurrentControlSet\Services\JBossEAP7" /v Environment
