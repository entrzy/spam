Get-Content "C:\IBM\WAS9\profiles\AppSrv01\logs\server1\trace.log" -Tail 0 -Wait `
| Select-String -Pattern 'WASAxis2Transport|HttpInputStreamCollector' `
| Out-File -Append "C:\waslogs\ws_trace.log" -Encoding utf8


Get-Content "C:\IBM\WAS9\profiles\AppSrv01\logs\server1\trace.log" -Tail 0 -Wait `
| Select-String -Pattern 'com\.ibm\.ws\.sib\.|com\.ibm\.ws\.jms\.' `
| Out-File -Append "C:\waslogs\mq_trace.log" -Encoding utf8

com.ibm.ws.websvcs.transport.http.WASAxis2Transport=all
com.ibm.ws.websvcs.transport.http.HttpInputStreamCollector=all


com.ibm.ws.sib.processor.impl.DestinationManager=all
com.ibm.ws.jms.*=info
com.ibm.ws.sib.msgstore.MessageStore=all
com.ibm.ws.sib.trm.*=all
