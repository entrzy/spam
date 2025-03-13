Below are some key recommendations and considerations to get more out of your Apache httpd layer, prevent it from capping at ~64 busy workers, and align it with Tomcat/Spring Boot’s higher thread capacity. The highlights:

1. **Confirm Which MPM You’re Actually Using**  
   - By default, many Linux distributions ship with the `prefork` MPM. If you’re seeing a hard cap around 64 busy workers, it’s often because `prefork` MPM or the `worker`/`event` MPM is locked at low defaults.  
   - Run:  
     ```bash
     httpd -V  (or)  apachectl -V
     ```  
     Look for lines like `Server MPM: event` or `Server MPM: worker` or `Server MPM: prefork`.
   - Make sure you actually load the desired MPM (often `event` is best nowadays for keepalives).

2. **Move MPM Settings Out of the `<VirtualHost>`**  
   - Typically, `ServerLimit`, `MaxRequestWorkers`, `ThreadLimit`, etc. belong in the **main** server config (e.g., `httpd.conf` or `mpm_event.conf`) rather than inside each `<VirtualHost>`.  
   - Putting them inside a `<VirtualHost>` can cause confusion or be ignored depending on how your Apache is built/packaged.

3. **Use (and Tune) the Event MPM**  
   - The `event` MPM provides better concurrency with keep-alive connections than `prefork` or even `worker`.  
   - Example recommended settings for `event` MPM (place in `httpd.conf` or included MPM config file, **not** inside `<VirtualHost>`):
     ```apache
     <IfModule mpm_event_module>
       # Overall limit on processes
       ServerLimit          16

       # Initial processes to start
       StartServers         4

       # Max threads each child process can create
       ThreadLimit          64

       # Threads each child process will create
       ThreadsPerChild      64

       # This is your concurrency ceiling: ServerLimit * ThreadsPerChild
       MaxRequestWorkers    1024

       # If you want more concurrency, raise ServerLimit * ThreadsPerChild and match them to MaxRequestWorkers
       # For example, 16 processes * 64 threads = 1024 concurrency

       MaxConnectionsPerChild  0
       # 0 or a large number prevents automatic child recycling too often
     </IfModule>
     ```
   - **Important**: If you want, say, 1600 or 2000+ concurrency, increase `ServerLimit`, `ThreadsPerChild`, and `MaxRequestWorkers` accordingly. But do so only if your hardware (CPU/RAM) supports that many simultaneous connections.  

4. **Verify `MaxRequestWorkers` (formerly `MaxClients`)**  
   - In your current snippet, you set `MaxRequestWorkers 1600` for all MPM blocks. But if you’re *actually* loading the `prefork` MPM, then the `worker` and `event` sections are ignored. On top of that, `prefork` has a default `ServerLimit` of 256 (or sometimes 256 child processes). If you don’t explicitly raise `ServerLimit` in `prefork`, you’ll get stuck near 256 processes – but each process can only handle **one** request at a time. That can manifest as ~64 busy requests if the OS or build-time limits are not aligned.  
   - So ensuring the MPM block actually in use has matching `ServerLimit` (for `prefork`) or `ThreadLimit` + `ServerLimit` (for `worker`/`event`) is critical.

5. **KeepAlive Tuning**  
   - You currently have:
     ```apache
     KeepAlive On
     MaxKeepAliveRequests 100
     KeepAliveTimeout 5
     ```
   - For many high-traffic services behind a load balancer (like F5), a shorter keep-alive timeout (e.g., `2` or even `1`) may help free workers faster if the load balancer itself reuses connections aggressively.  
   - On the other hand, if your load patterns have lots of immediate subsequent requests from the same client connections, a moderate keep-alive timeout can help.  
   - Observe your environment and test different values: `KeepAliveTimeout 1`–`5` is typical.

6. **Check OS (Linux) Limits**  
   - Make sure your Linux server can handle higher file descriptors (FDs) and ephemeral ports if you plan to scale concurrency into the hundreds or thousands. For example:
     - In `/etc/security/limits.conf`, ensure `nofile` is large enough (e.g., `65535` or more).
     - Check `net.ipv4.ip_local_port_range` to ensure you have enough ephemeral ports open for thousands of connections.
   - Also verify you have enough CPU/cores, especially if you move to a multi-threaded MPM with large concurrency.

7. **Confirm Tomcat/Spring Boot Connector Settings**  
   - Tomcat and Spring Boot each have `maxThreads=800`. Also check their `acceptCount` (the queue size for incoming connections) so that if 800 threads are busy, new connections do not get dropped or block too aggressively.  
   - Ensure you’re using non-blocking I/O (NIO or NIO2) if possible, especially if you anticipate large scale concurrency.

8. **Monitor Access and Error Logs**  
   - Check for messages like:  
     > `[mpm_event:error] AH00485: scoreboard is full, not at MaxRequestWorkers`  
     or  
     > `[mpm_prefork:error] AH00161: server reached MaxRequestWorkers`  
   - These indicate you’ve hit concurrency limits and are dropping or queueing connections. If you see those, you *must* raise the concurrency limits (and ensure the hardware can handle it).

9. **Validate From the F5 Perspective**  
   - F5’s stats showing ~250 connections per node might be the inbound side. Meanwhile, your `server-status` shows it’s pegged at 64 in a busy/processing state. This strongly suggests your Apache limit is too low.  
   - Once you lift the Apache MPM concurrency (and confirm the correct MPM is loaded), you should see higher concurrency in `server-status`—and that should match more closely with the load balancer’s stats (assuming the app can handle it).

10. **Example Final Structure**  
   Here’s a more typical structure (again, MPM config **outside** the `<VirtualHost>`), plus any VirtualHost–specific directives inside the `<VirtualHost>`:

   ```apache
   # httpd.conf (or /etc/httpd/conf.modules.d/mpm_event.conf, etc.)
   <IfModule mpm_event_module>
       ServerLimit             16
       StartServers            4
       MinSpareThreads         25
       MaxSpareThreads         75
       ThreadLimit             64
       ThreadsPerChild         64
       MaxRequestWorkers       1024
       MaxConnectionsPerChild  0
   </IfModule>

   # Then in your site .conf:
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

       # GZIP compression etc.
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

---

### Final Checklist

1. **Pick `event` MPM** (best for keepalives and concurrency) and confirm it’s actually loaded (via `httpd -V`).
2. **Set matching `ServerLimit`, `ThreadLimit`, and `MaxRequestWorkers`** so that you can reach the concurrency you need (and watch memory usage).
3. **Put MPM directives in the main server config** (not inside `<VirtualHost>`).
4. **Tune KeepAlive** (shorter timeouts if you have thousands of clients, especially behind an F5).
5. **Check OS-level resource limits** (files, ports).
6. **Ensure Tomcat / Spring Boot** is also configured for the same or higher concurrency (e.g., `maxThreads` and `acceptCount`).
7. **Load-test** after changes to verify you no longer stall at 64 busy workers and to confirm end-to-end performance.  

Following these guidelines should let you go well beyond 64 active connections, make full use of Tomcat’s 800-thread capacity, and deliver the highest throughput your hardware can support without slowness.
