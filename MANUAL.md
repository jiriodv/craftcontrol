# 📖 Příručka správce Minecraft Serveru v2

Tento dokument slouží jako **kompletní návod** pro zprovoznění a správu školního Minecraft serveru a ovládacího panelu.

---

## 🏗️ 1. Nastavení Serveru (Linux/Docker) - TO HLAVNÍ

Aby panel fungoval, server musí být správně nastaven. Zde je checklist:

### ✅ Checklist před startem:
1.  **RCON Port (25575):** Musí být povolen v `docker-compose.yml` (sekce ports).
2.  **Heslo RCON:** Musí být shodné v `server.properties` (nebo ENV) a v Panelu.
3.  **Název kontejneru:** Panel hledá kontejner podle jména (např. `informatika`).
4.  **Pluginy:** Pro plnou funkčnost tlačítek potřebujete:
    *   `EssentialsX` (základní příkazy)
    *   `EssentialsSpawn` (pro tlačítko 🏠 **Spawn**)
    *   `AuthMeReloaded` (pro tlačítko 🔑 **Unreg/Reset hesla**)

### 📄 Vzorový `docker-compose.yml` pro Minecraft Server
Tento soubor nahrajte na školní server (např. do `/root/Docker/MC/petka/`).

```yaml
version: "3"
services:
  mc:
    image: itzg/minecraft-server:latest
    container_name: informatika    # <--- DŮLEŽITÉ: Jméno pro ovládání panelem
    restart: unless-stopped
    ports:
      - "25565:25565" # Hra
      - "8100:8100"   # BlueMap (volitelné)
      - "25575:25575" # <--- DŮLEŽITÉ: RCON port pro panel!
    environment:
      EULA: "TRUE"
      ONLINE_MODE: "FALSE"
      MOTD: "Skolni Server"
      ENABLE_RCON: "TRUE"          # <--- Povolit RCON
      RCON_PASSWORD: "S1N0server2021" # <--- Heslo (nastavte silné a zadejte do panelu)
      RCON_PORT: 25575
      MEMORY: "6G"
      TYPE: "PAPER"
    volumes:
      - ./data:/data
```

---

## 🖥️ 2. Nastavení Ovládacího Panelu (Váš PC)

Panel se připojuje k serveru přes SSH. Nastavení najdete v souboru `docker-compose.yml` (u vás v počítači) nebo v sekci **Nastavení Aplikace** v panelu.

*   `SSH_HOST`: IP adresa serveru (např. `192.168.40.103`)
*   `SSH_USER`: `root` (nebo jiný uživatel s přístupem k dockeru)
*   `SSH_PASSWORD`: Heslo k Linuxu.
*   `MC_ID`: Název kontejneru (musí sedět s `container_name` výše, tj. `informatika`).
*   `MC_PATH`: Cesta k logu. Na školním serveru zjištěno: `/root/Docker/MC/petka/data/logs/latest.log`

---

## 🛠️ 3. Řešení problémů (FAQ)

**Kliknu na "Spawn" a hráč se objeví v moři/ve vzduchu.**
*   Chybí plugin **EssentialsSpawn**. Panel použil nouzový teleport na souřadnice 0, 100, 0.
*   *Řešení:* Nahrajte `EssentialsSpawn.jar` do složky `plugins` na serveru a restartujte ho. Pak nastavte spawn ve hře příkazem `/setspawn`.

**Kliknu na "Unreg/Reset hesla" a nic se nestane.**
*   Chybí plugin **AuthMe**. Bez něj server neumí registrace.
*   *Řešení:* Nahrajte `AuthMe.jar`.

**Tlačítka jsou šedá / neaktivní.**
*   Hráč je offline. Tlačítka jako Heal nebo Feed fungují jen na online hráče.
*   Tlačítka **Unreg** a **Ban** fungují i offline.

**Chyba "Connection Refused" v konzoli.**
*   Server neběží nebo nemá otevřený port 25575. Zkontrolujte `docker-compose.yml` na serveru.

---
*Dokument aktualizován: 29. 1. 2026*
