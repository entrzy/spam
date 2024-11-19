# Forward Proxy Configuration
server {
    listen 8080;

    # Serwer proxy
    location / {
        # Definiujemy adres docelowego serwera
        proxy_pass https://10.208.6.196:443;

        # Ustawienia proxy
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouty
        proxy_connect_timeout 5s;
        proxy_read_timeout 10s;
        proxy_send_timeout 10s;

        # SSL/TLS - wyłączenie weryfikacji certyfikatu (opcjonalne, jeśli serwer docelowy ma self-signed cert)
        proxy_ssl_verify off;
    }
}
