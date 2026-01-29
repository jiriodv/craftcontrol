# GitHub Secrets - Nastavení pro automatické Docker buildy

## Co je potřeba udělat

Pro automatické buildy při každém push na GitHub potřebuješ nastavit Docker Hub přihlašovací údaje jako GitHub Secrets.

## Postup

### 1. Jdi na GitHub repozitář
https://github.com/jiriodv/sprava_docker_minecraft_serveru

### 2. Otevři Settings
- Klikni na **Settings** (nahoře vpravo)

### 3. Přejdi na Secrets
- V levém menu klikni na **Secrets and variables** → **Actions**

### 4. Přidej první secret
- Klikni na **New repository secret**
- **Name**: `DOCKER_USERNAME`
- **Secret**: `jiriodv`
- Klikni **Add secret**

### 5. Přidej druhý secret
- Klikni na **New repository secret** znovu
- **Name**: `DOCKER_PASSWORD`
- **Secret**: `@Jiricek@12552@`
- Klikni **Add secret**

## Hotovo! ✅

Od teď při každém push na `main` branch se automaticky:
1. Vytvoří nový Docker image
2. Nahraje se na Docker Hub jako `jiriodv/craftcontrol:latest`

## Testování

Po nastavení secrets zkus:

```bash
# Udělej malou změnu
echo "# Test" >> README.md
git add README.md
git commit -m "Test GitHub Actions"
git push
```

Pak jdi na GitHub → **Actions** tab a uvidíš běžící workflow!

---

**Poznámka:** Doporučuji později změnit heslo na Docker Hub Access Token (bezpečnější):
1. Jdi na https://hub.docker.com/settings/security
2. Vytvoř nový Access Token
3. Použij token místo hesla v `DOCKER_PASSWORD` secret
