# Návod na nahrání CraftControl na GitHub

## Krok 1: Vytvoření GitHub repozitáře

1. Otevři prohlížeč a jdi na: **https://github.com/new**
2. Vyplň následující údaje:
   - **Repository name**: `craftcontrol` (nebo jiný název dle tvého výběru)
   - **Description**: `Modern web panel for Minecraft server management with RCON and SSH integration`
   - **Visibility**: Vyber **Public** (nebo Private, pokud chceš)
   - **DŮLEŽITÉ**: ❌ NEZAŠKRTÁVEJ "Add a README file", ".gitignore", nebo "license" - už je máme!
3. Klikni na **"Create repository"**

## Krok 2: Propojení s GitHubem

Po vytvoření repozitáře ti GitHub ukáže instrukce. Použij následující příkazy:

```bash
# Přidej GitHub jako remote (nahraď 'username' svým GitHub uživatelským jménem)
git remote add origin https://github.com/username/craftcontrol.git

# Nahraj kód na GitHub
git push -u origin main
```

**NEBO pokud používáš SSH:**

```bash
git remote add origin git@github.com:username/craftcontrol.git
git push -u origin main
```

## Krok 3: Ověření

Po úspěšném nahrání:
1. Obnov stránku repozitáře na GitHubu
2. Měl bys vidět všechny soubory včetně README.md
3. README.md se automaticky zobrazí na hlavní stránce repozitáře

## Doporučené další kroky

### 1. Přidej Topics (štítky)
Na stránce repozitáře klikni na ⚙️ vedle "About" a přidej topics:
- `minecraft`
- `server-management`
- `rcon`
- `flask`
- `docker`
- `python`

### 2. Přidej Screenshots
Vytvoř složku `screenshots/` a přidej obrázky dashboardu:
```bash
mkdir screenshots
# Přidej screenshoty do této složky
git add screenshots/
git commit -m "Add screenshots"
git push
```

Pak aktualizuj README.md s odkazy na obrázky.

### 3. GitHub Releases
Vytvoř první release (v0.1.0):
1. Jdi na záložku "Releases"
2. Klikni "Create a new release"
3. Tag: `v0.1.0`
4. Title: `CraftControl v0.1.0 - Initial Release`
5. Popis: Zkopíruj hlavní funkce z README.md

## Řešení problémů

### Pokud Git žádá přihlášení:
```bash
# Nastav své GitHub údaje
git config --global user.name "Tvoje Jméno"
git config --global user.email "tvuj@email.com"
```

### Pokud push selže kvůli autentizaci:
GitHub už nepodporuje hesla. Použij:
- **Personal Access Token**: https://github.com/settings/tokens
- **SSH klíč**: https://docs.github.com/en/authentication/connecting-to-github-with-ssh

---

**Aktuální stav:**
✅ Git repozitář inicializován
✅ První commit vytvořen (c8e05d0)
✅ Branch přejmenován na 'main'
✅ Všechny soubory připraveny k nahrání
