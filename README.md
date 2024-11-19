stream {
    server {
        listen 8080; # Port nasłuchiwania proxy

        # Przekazywanie ruchu do serwera docelowego
        proxy_pass 10.208.6.196:443;

        # Logi (opcjonalne)
        access_log /var/log/nginx/forward_proxy_access.log;
        error_log /var/log/nginx/forward_proxy_error.log;
    }
}
