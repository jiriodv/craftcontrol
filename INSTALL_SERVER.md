# Kompletní návod: Instalace CraftControl na Linux server

## Krok 1: Příprava souborů

```bash
# Přejdi do složky s Minecraft serverem
cd /home/Docker/MC

# Naklonuj repozitář (pokud jsi to ještě neudělal)
git clone https://github.com/jiriodv/sprava_docker_minecraft_serveru.git mc-panel

# Vytvoř složku pro databázi
mkdir -p mc-panel/data
```

## Krok 2: Kompletní docker-compose.yml

Otevři editor:
```bash
nano /home/Docker/MC/docker-compose.yml
```

Vlož tento KOMPLETNÍ obsah (smaž vše staré a vlož toto):

```yaml
services:
  mc:
    image: itzg/minecraft-server:latest
    container_name: minecraft_server
    restart: unless-stopped
    ports:
      - "25565:25565"
      - "25575:25575"
      - "8100:8100"
      - "8804:8804"
      - "4445:4445/udp"
    environment:
      EULA: "TRUE"
      ONLINE_MODE: "FALSE"
      MOTD: "Smrzice"
      ENABLE_RCON: "TRUE"
      RCON_PASSWORD: "Juraj12552"
      MEMORY: "6G"
      TYPE: "PAPER"
      PVP: "FALSE"
    volumes:
      - ./data:/data
    networks:
      - mc-network

  mc-panel:
    build: ./mc-panel
    container_name: mc-panel
    restart: unless-stopped
    ports:
      - "5050:5000"
    volumes:
      - ./mc-panel/data:/app/data
    environment:
      - SECRET_KEY=vygeneruj_si_nahodny_retezec_aspon_32_znaku_zde
      - RCON_PASSWORD=Juraj12552
      - RCON_HOST=minecraft_server
      - RCON_PORT=25575
      - MC_CONTAINER_NAME=minecraft_server
    networks:
      - mc-network
    depends_on:
      - mc

networks:
  mc-network:
    driver: bridge
```

**Ulož soubor:**
- Stiskni `Ctrl + O` (uložit)
- Stiskni `Enter` (potvrdit)
- Stiskni `Ctrl + X` (zavřít)

## Krok 3: Spuštění

```bash
# Zastav vše (pokud něco běží)
docker-compose down

# Spusť oba kontejnery
docker-compose up -d

# Sleduj logy panelu
docker-compose logs -f mc-panel
```

**Počkej 10-20 sekund**, až se panel spustí. Uvidíš:
```
* Running on http://0.0.0.0:5000
```

Stiskni `Ctrl + C` pro ukončení sledování logů.

## Krok 4: Přístup k panelu

1. Otevři prohlížeč
2. Jdi na: **http://192.168.0.121:5050**
3. Přihlaš se:
   - **Uživatel:** `admin`
   - **Heslo:** `admin`

## Krok 5: První nastavení

Po přihlášení:

1. **Změň heslo:**
   - Jdi do nastavení (ikona ozubeného kola)
   - Změň heslo z `admin` na něco bezpečného

2. **Zkontroluj RCON:**
   - Jdi do sekce "Console"
   - Zkus zadat příkaz `/list`
   - Pokud funguje, vidíš seznam hráčů

## Řešení problémů

### Panel se nespustí
```bash
# Zkontroluj logy
docker-compose logs mc-panel

# Zkontroluj, že běží
docker ps
```

### RCON nefunguje (Connection refused)
```bash
# Zkontroluj, že MC server běží
docker exec minecraft_server rcon-cli list

# Pokud nefunguje, restartuj panel
docker-compose restart mc-panel
```

### Port 5050 není dostupný
```bash
# Zkontroluj firewall
ufw allow 5050/tcp
ufw reload
```

## Užitečné příkazy

```bash
# Restart panelu
docker-compose restart mc-panel

# Zastavení všeho
docker-compose down

# Spuštění všeho
docker-compose up -d

# Sledování logů
docker-compose logs -f mc-panel

# Sledování logů MC serveru
docker-compose logs -f mc

# Aktualizace panelu (po git pull)
docker-compose up -d --build mc-panel
```

## Hotovo! 🎉

Panel by měl běžet na: **http://192.168.0.121:5050**

Pokud máš problémy, pošli mi výstup z:
```bash
docker-compose logs mc-panel
```
