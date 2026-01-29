# Návod k nastavení: Minecraft Školní Panel 👨‍🏫🚀

Tento panel slouží k dálkové správě Minecraft (Paper/Spigot) serveru. Umožňuje spravovat hráče, pluginy a sledovat výkon serveru v reálném čase.

---

## 🧩 Doporučené Pluginy
Pro plnou funkčnost všech tlačítek v panelu **důrazně doporučujeme** nainstalovat tyto pluginy:

1.  **EssentialsX** (Nejdůležitější!)
    *   *K čemu:* Zajišťuje příkazy `/spawn`, `/heal`, `/feed`, `/mute`, `/whois` a teleportaci.
    *   *Bez něj:* Většina rychlých akcí v panelu nebude fungovat nebo bude vyžadovat složité koordináty.
2.  **AuthMe Reloaded**
    *   *K čemu:* Správa registrací žáků. Panel umožňuje resetovat hesla přes tlačítko "Unreg".
3.  **BlueMap** nebo **Dynmap**
    *   *K čemu:* Zobrazení 3D/2D mapy světa v prohlížeči. Panel má funkci pro vynucení aktualizace mapy u hráče.
4.  **WorldEdit**
    *   *K čemu:* Rychlé stavění a úpravy mapy. Panel má tlačítko "Wand" pro získání sekyrky.
5.  **LuckPerms** (Volitelné)
    *   *K čemu:* Správa práv (aby žáci nemohli používat admin příkazy).

---

## ⚙️ Konfigurace Serveru

### 1. Povolení RCON (Příkazy)
V souboru `server.properties` na vašem Minecraft serveru nastavte:
```properties
enable-rcon=true
rcon.password=VaseTajneHeslo
rcon.port=25575
```

### 2. SSH Přístup (Logy a Výkon)
Ujistěte se, že server (Linux/Proxmox) má povolen SSH přístup pro uživatele (např. `root`), aby panel mohl číst soubor `latest.log` a sledovat zátěž CPU/RAM.

---

## 🛠️ Spuštění Panelu (Lokálně)

1.  **Upravte `docker-compose.yml`**:
    *   Zadejte IP adresu serveru (`SSH_HOST`).
    *   Zadejte SSH údaje (`SSH_USER`, `SSH_PASSWORD`).
    *   Zadejte RCON heslo (`RCON_PASSWORD`).
    *   Nastavte cesty k logům (`MC_LOG_PATH`).
    *   (Volitelné) URL pro mapu (`BLUEMAP_URL`).

2.  **Spusťte Panel**:
    ```bash
    docker compose up -d
    ```

3.  **Otevřete v prohlížeči**:
    *   Adresa: `http://localhost:5050`
    *   Výchozí login: `admin` / `admin123` (lze změnit v `app.py`)

---

## 💡 Tipy pro učitele
*   **🔍 INFO tlačítko**: Používejte pro kontrolu IP adres, verzí a rychlou úpravu Fly/God/XP úrovně.
*   **⚡ Classroom Control**: Na hlavní stránce najdete tlačítka pro hromadné zmražení celé třídy nebo přitáhnutí všech na spawn.
*   **⚙️ Konfigurace**: V sekci Konfigurace můžete měnit obtížnost nebo PvP bez nutnosti lézt do souborů na serveru.
*   **🧹 Clear Inv**: Používejte s rozvahou – smaže hráči úplně všechno v inventáři bez možnosti návratu!
