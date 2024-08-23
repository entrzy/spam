Get-ADGroupMember -Identity "GroupName" -Recursive | Where-Object { $_.objectClass -eq 'user' } | Get-ADUser | Select-Object Name, SamAccountName
