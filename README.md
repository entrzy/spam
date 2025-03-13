On Windows, Apache httpd uses the **WinNT MPM** rather than `prefork`, `worker`, or `event`. This means some of the Linux-style MPM directives (like `ServerLimit`, `ThreadLimit`, etc.) do not apply. Instead, WinNT MPM has a simpler configuration. Below are the key steps and settings to check in a Windows environment:

---

## 1. Confirm You’re Using the WinNT MPM

1. **Check your Apache version/build** by running something like:
   ```bash
   httpd -V
   ```
   On Windows, you should see a line mentioning `Server MPM: winnt`.

2. **Remove or ignore** any `<IfModule mpm_event_module>` / `mpm_worker_module` / `mpm_prefork_module>` blocks in your config because those are irrelevant on Windows. They will be ignored.

---

## 2. Important WinNT MPM Directives

In the **WinNT** MPM, the key directives are:

1. **ThreadsPerChild**  
   - Controls how many threads the single Apache child process will create. Each thread can handle one connection at a time. The default might be 64, which often explains why you see a maximum of ~64 busy workers.  
   - If you have higher concurrency needs, raise this (e.g., 256, 512, 1024, etc.). Be mindful of resource usage (CPU/RAM) as each thread consumes stack and memory.

2. **MaxConnectionsPerChild**  
   - Similar to `MaxConnectionsPerChild` on Unix, but on Windows it defaults to 0 (infinite). This controls how many connections a child process will handle before it’s recycled. Often leaving it at 0 (no forced recycling) is fine on Windows if you don’t have memory-leak issues.

3. **MaxRequestWorkers** (or older `MaxClients`)  
   - On Windows, `ThreadsPerChild` effectively sets your concurrency limit (the number of concurrent connections).  
   - `MaxRequestWorkers` is still recognized in modern Apache, but for the WinNT MPM it’s essentially an alias for `ThreadsPerChild` under the hood. If you configure `MaxRequestWorkers`, it sets `ThreadsPerChild` to that number.

### Example WinNT MPM Config (in `httpd.conf`)

```apache
<IfModule mpm_winnt_module>
    # Number of threads in the single child process. Increase this if you expect high concurrency.
    ThreadsPerChild        256

    # If you want indefinite run, set to 0, else pick a large number.
    MaxConnectionsPerChild 0

    # Optionally, if you prefer using MaxRequestWorkers syntax:
    # MaxRequestWorkers    256
</IfModule>
```

Then remove or comment out any event/worker/prefork blocks so they don’t conflict.

---

## 3. KeepAlive Settings

You have:

```apache
KeepAlive On
MaxKeepAliveRequests 100
KeepAliveTimeout 5
```

These are still valid on Windows. Be aware of the following:

- **KeepAliveTimeout**: If you have thousands of simultaneous connections, even 5 seconds can tie up threads. You can experiment with reducing this (e.g., `2` or `3`) if your environment (especially behind an F5 load balancer) frequently reuses connections.
- **MaxKeepAliveRequests**: 100 is typically fine. If your clients make a lot of successive requests, you could consider raising this. If your clients do a single request and disconnect, you could keep it as is or even reduce it slightly.

---

## 4. Check Tomcat and Spring Boot Connector Settings

You already have Tomcat and Spring Boot set to `maxThreads=800`. A few considerations:

1. **Connector type**: Make sure you’re using the `NIO` connector (non-blocking) in Tomcat, which is more modern and scales better than the old blocking `BIO` connector.  
2. **acceptCount**: If all threads are busy, new connections get queued up to `acceptCount`. Raise `acceptCount` if you see refusal errors (HTTP 503 or “Connection refused”).  
3. **Windows service memory**: If Tomcat runs as a Windows Service, watch that it’s sized with enough heap to handle concurrency. Similarly, keep an eye on system-wide memory usage for the combined Apache + Tomcat + Spring Boot processes.

---

## 5. Windows OS-Level Tuning

Even though Windows doesn’t rely on the same limits as Linux (like `nofile` or ephemeral port sysctls), you still want to check:

1. **Ephemeral Port Range**  
   - On Windows, you can review/tweak ephemeral ports with:
     ```bash
     netsh int ipv4 show dynamicportrange tcp
     ```
   - If you have a lot of short-lived or high-volume connections, consider increasing that range or verifying it’s not too small (the default range usually is enough for most typical scenarios).

2. **TCP Tuning** (optional, advanced)  
   - For extremely high throughput setups, you can check registry settings around TCP window scaling, but in most modern Windows versions these are already fairly optimized out of the box.

3. **Antivirus / Firewall**  
   - On busy servers, real-time antivirus scanning or strict firewall overhead can affect performance. Ensure that your Apache and Tomcat directories are excluded from excessive real-time scans if that’s safe within your environment.

---

## 6. Confirm Behavior in `server-status`

1. **Enable `mod_status`** (the `server-status` page) to watch busy threads:
   ```apache
   <Location /server-status>
       SetHandler server-status
       Require ip 127.0.0.1
       # or whatever IP range you use
   </Location>
   ```
2. **Look at “Busy Workers”** and “Idle Workers.”  
   - If you see it stuck at 64 busy threads and no idle threads, that means you must raise `ThreadsPerChild` above 64.  
   - After you raise it (and restart Apache), you should see the new higher concurrency limit (e.g., 256).  

---

## 7. Putting It All Together

1. **In your main `httpd.conf` (or equivalent)**, place the **WinNT MPM** directives. For example:

   ```apache
   <IfModule mpm_winnt_module>
       ThreadsPerChild         256
       MaxConnectionsPerChild  0
   </IfModule>
   ```

2. **Remove** the `<IfModule mpm_prefork_module>`, `<IfModule mpm_worker_module>`, and `<IfModule mpm_event_module>` sections entirely, since they’re not used on Windows.

3. **In your `<VirtualHost>`** keep just the relevant directives (proxy configs, keepalive, etc.):

   ```apache
   <VirtualHost *:8080>
       ServerName npwpcc2fea1

       ProxyPreserveHost On
       RequestHeader set X-Forwarded-Proto "https"
       Header always set X-Forwarded-Proto "https"

       ProxyPassMatch ^/(api|userinfo|csrf-token)(.*) http://npwpcc2fea1:9080/$1$2
       ProxyPassReverse ^/(api|userinfo|csrf-token)(.*) http://npwpcc2fea1:9080/$1$2

       ProxyPass        / http://npwpcc2fea1:8087/
       ProxyPassReverse / http://npwpcc2fea1:8087/

       KeepAlive On
       MaxKeepAliveRequests 100
       KeepAliveTimeout 5

       # Compression etc.
       <IfModule filter_module>
           FilterDeclare COMPRESS
           FilterProvider COMPRESS DEFLATE resp=Content-Type $text/html
           FilterProvider COMPRESS DEFLATE resp=Content-Type $text/plain
           FilterProvider COMPRESS DEFLATE resp=Content-Type $text/xml
           FilterProvider COMPRESS DEFLATE resp=Content-Type $text/css
           FilterProvider COMPRESS DEFLATE resp=Content-Type $text/javascript
           FilterProvider COMPRESS DEFLATE resp=Content-Type $application/javascript
           FilterProvider COMPRESS DEFLATE resp=Content-Type $application/json
           FilterProvider COMPRESS DEFLATE resp=Content-Type $application/xml
           FilterChain COMPRESS
           DeflateCompressionLevel 6
           DeflateMinLength 1024
       </IfModule>
   </VirtualHost>
   ```

4. **Restart** Apache. Then check `server-status` to confirm your new concurrency limit is recognized.

5. **Load-test** (e.g., using JMeter, Locust, or any HTTP load tool) to ensure that you can sustain a higher volume of concurrent requests without hitting the 64-busy-thread limit.

---

### In Summary

- On Windows, Apache httpd uses `mpm_winnt_module`.  
- **Increase `ThreadsPerChild`** to go beyond the default of 64 (e.g., 256, 512, or more) to match your Tomcat/Spring Boot capacity.  
- Keep an eye on CPU and RAM usage when raising concurrency.  
- Continue to tune keep-alive and watch logs/status as you scale.  

Following these steps ensures Apache httpd on Windows can handle far more than 64 concurrent connections, aligning better with your Tomcat and Spring Boot settings (each at 800 threads) and giving you a consistent, high-performance setup.
