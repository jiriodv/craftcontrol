# Instalace CraftControl na Linux Server

## Rychlá instalace (Doporučeno)

### 1. Naklonuj repozitář
```bash
cd /opt  # nebo jiná složka dle tvého výběru
git clone https://github.com/jiriodv/sprava_docker_minecraft_serveru.git
cd sprava_docker_minecraft_serveru
```

### 2. Vytvoř konfiguraci
```bash
# Zkopíruj vzorovou konfiguraci
cp .env.example .env

# Uprav konfiguraci (použij nano, vim, nebo jiný editor)
nano .env
```

**Minimální konfigurace v `.env`:**
```env
SECRET_KEY=vygeneruj_nahodny_retezec_zde
RCON_PASSWORD=tvoje_rcon_heslo

# Pokud je Minecraft na stejném serveru:
RCON_HOST=127.0.0.1
RCON_PORT=25575

# Pokud je Minecraft v Docker kontejneru na stejném serveru:
MC_CONTAINER_NAME=nazev_mc_kontejneru
MC_LOG_PATH=/cesta/k/minecraft/logs/latest.log
MC_SERVER_PATH=/cesta/k/minecraft/data

# SSH není potřeba, pokud běží vše na stejném serveru
```

### 3. Spusť panel
```bash
# Vytvoř složku pro databázi
mkdir -p data

# Spusť Docker Compose
docker-compose up -d

# Zkontroluj, že běží
docker-compose ps
docker-compose logs -f
```

### 4. Přístup k panelu
- URL: `http://ip_serveru:5050`
- Výchozí přihlášení: `admin` / `admin`
- **DŮLEŽITÉ**: Změň heslo hned po prvním přihlášení!

---

## Pokročilá konfigurace

### Použití s Nginx (Reverse Proxy + HTTPS)

#### 1. Nainstaluj Nginx a Certbot
```bash
apt update
apt install nginx certbot python3-certbot-nginx -y
```

#### 2. Vytvoř Nginx konfiguraci
```bash
nano /etc/nginx/sites-available/mc-panel
```

**Obsah souboru:**
```nginx
server {
    listen 80;
    server_name mc.tvoje-domena.cz;  # Změň na svou doménu

    location / {
        proxy_pass http://localhost:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (pro live logy)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 3. Aktivuj konfiguraci
```bash
ln -s /etc/nginx/sites-available/mc-panel /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

#### 4. Získej SSL certifikát
```bash
certbot --nginx -d mc.tvoje-domena.cz
```

### Automatický restart při restartu serveru

Docker Compose už má `restart: unless-stopped`, takže panel se automaticky spustí při restartu serveru.

---

## Konfigurace pro různé scénáře

### Scénář 1: Minecraft a Panel na stejném serveru (Docker)
```env
RCON_HOST=127.0.0.1
RCON_PORT=25575
MC_CONTAINER_NAME=minecraft_server
MC_LOG_PATH=/var/lib/docker/volumes/mc_data/_data/logs/latest.log
MC_SERVER_PATH=/var/lib/docker/volumes/mc_data/_data
```

### Scénář 2: Minecraft na jiném serveru (SSH tunel)
```env
SSH_HOST=192.168.1.100
SSH_USER=root
SSH_PASSWORD=heslo_nebo_pouzij_ssh_klic
REMOTE_RCON_HOST=127.0.0.1
MC_LOG_PATH=/root/minecraft/logs/latest.log
MC_SERVER_PATH=/root/minecraft/data
```

### Scénář 3: Pouze RCON (bez SSH funkcí)
```env
RCON_HOST=192.168.1.100
RCON_PORT=25575
RCON_PASSWORD=tvoje_heslo
# SSH proměnné vynech
```

---

## Údržba

### Aktualizace na novou verzi
```bash
cd /opt/sprava_docker_minecraft_serveru
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

### Záloha databáze
```bash
# Databáze je v ./data/mc_panel.db
cp data/mc_panel.db data/mc_panel.db.backup.$(date +%Y%m%d)
```

### Prohlížení logů
```bash
docker-compose logs -f        # Všechny logy
docker-compose logs -f web    # Pouze panel
```

### Restart panelu
```bash
docker-compose restart
```

### Zastavení panelu
```bash
docker-compose down
```

---

## Řešení problémů

### Panel se nespustí
```bash
# Zkontroluj logy
docker-compose logs

# Zkontroluj, že port 5050 není obsazený
netstat -tulpn | grep 5050
```

### RCON nefunguje
```bash
# Zkontroluj, že RCON je povolený v server.properties
grep rcon /cesta/k/minecraft/server.properties

# Zkontroluj firewall
ufw status
```

### SSH tunel nefunguje
```bash
# Zkontroluj SSH připojení manuálně
ssh user@server_ip

# Zkontroluj cesty k logům
ls -la /cesta/k/minecraft/logs/latest.log
```

---

## Bezpečnostní doporučení

1. **Změň výchozí heslo** hned po instalaci
2. **Použij silné heslo** pro RCON
3. **Nastav firewall**:
   ```bash
   ufw allow 5050/tcp  # Nebo pouze z konkrétních IP
   ufw enable
   ```
4. **Použij HTTPS** (Nginx + Certbot)
5. **Pravidelně aktualizuj**:
   ```bash
   git pull
   docker-compose pull
   docker-compose up -d
   ```

---

## Příklad kompletní instalace

```bash
# 1. Příprava
cd /opt
git clone https://github.com/jiriodv/sprava_docker_minecraft_serveru.git
cd sprava_docker_minecraft_serveru

# 2. Konfigurace
cp .env.example .env
nano .env  # Uprav podle svých potřeb

# 3. Spuštění
mkdir -p data
docker-compose up -d

# 4. Ověření
docker-compose ps
curl http://localhost:5050

# 5. Firewall (volitelné)
ufw allow 5050/tcp

# 6. Přístup
echo "Panel běží na: http://$(hostname -I | awk '{print $1}'):5050"
```

---

**Hotovo! Panel by měl běžet na `http://ip_serveru:5050`** 🎉
