Get-ADGroupMember -Identity "GroupName" -Recursive | Where-Object { $_.objectClass -eq 'user' } | Get-ADUser | Select-Object Name, SamAccountName




Based on the analysis of the logs, I found entries related to communication on port 58989 and replication operations. Here are the key points:

Replication on port 58989: The logs indicate active replication communication between the servers using this port. The entries describe the process of receiving and processing messages between the servers, suggesting that replication is functioning.

No errors found: I did not find any entries indicating errors or warnings related to the replication process. The logs mention the successful processing of messages like "ChangeTimeHeartbeatMsg," which indicates that synchronization is proceeding correctly.

Replication entries: Both logs contain similar entries related to different domains (e.g., "cn=schema" and "cn=admin data"), indicating that replication is occurring across various parts of the system.

Based on this information, it appears that replication between the OpenDJ instances is working as expected. If you need further analysis on specific issues, I can search the logs for more details or specific events.
