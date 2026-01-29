# Vytvoření a publikace Docker Image na Docker Hub

## Příprava

### 1. Vytvoř Docker Hub účet
- Jdi na https://hub.docker.com/
- Zaregistruj se (pokud ještě nemáš účet)
- Zapamatuj si své uživatelské jméno (např. `jirkaodv`)

### 2. Přihlaš se do Docker Hub z terminálu
```bash
docker login
# Zadej své Docker Hub uživatelské jméno a heslo
```

## Vytvoření a nahrání image

### Krok 1: Build image s tagem
```bash
cd /Users/jirka/Documents/Antigravity/Aplikace/mc_server

# Build s tagem pro Docker Hub
# Formát: dockerhub_username/repository_name:tag
docker build -t jirkaodv/mc-server-boss:latest .
docker build -t jirkaodv/mc-server-boss:1.0.0 .
```

### Krok 2: Testuj image lokálně
```bash
# Spusť kontejner z image
docker run -d \
  -p 5050:5000 \
  -e RCON_PASSWORD=test123 \
  -e RCON_HOST=192.168.1.100 \
  --name mc-panel-test \
  jirkaodv/mc-server-boss:latest

# Zkontroluj, že běží
docker logs mc-panel-test

# Zastav a smaž test
docker stop mc-panel-test
docker rm mc-panel-test
```

### Krok 3: Push na Docker Hub
```bash
# Nahraj obě verze (latest a 1.0.0)
docker push jirkaodv/mc-server-boss:latest
docker push jirkaodv/mc-server-boss:1.0.0
```

## Aktualizace README.md pro Docker Hub

Po nahrání uprav README.md, aby lidé věděli, jak použít image:

```markdown
## 🚀 Quick Start with Docker Hub

### Using pre-built image (Recommended)

```bash
# Pull the image
docker pull jirkaodv/mc-server-boss:latest

# Run the container
docker run -d \
  -p 5050:5000 \
  -v ./data:/app/data \
  -e SECRET_KEY=your_secret_key \
  -e RCON_PASSWORD=your_rcon_password \
  -e RCON_HOST=your_minecraft_server_ip \
  --name mc-panel \
  jirkaodv/mc-server-boss:latest
```

### Using docker-compose with pre-built image

```yaml
services:
  mc-panel:
    image: jirkaodv/mc-server-boss:latest  # Místo build: .
    container_name: mc-panel
    ports:
      - "5050:5000"
    volumes:
      - ./data:/app/data
    environment:
      - SECRET_KEY=your_secret_key
      - RCON_PASSWORD=your_rcon_password
      - RCON_HOST=minecraft_server
    restart: unless-stopped
```
```

## GitHub Actions pro automatické buildy

Vytvoř `.github/workflows/docker-publish.yml`:

```yaml
name: Docker Build and Push

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: docker.io
  IMAGE_NAME: jirkaodv/mc-server-boss

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log into Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Nastavení GitHub Secrets

1. Jdi na GitHub repozitář → Settings → Secrets and variables → Actions
2. Přidej secrets:
   - `DOCKER_USERNAME`: tvoje Docker Hub uživatelské jméno
   - `DOCKER_PASSWORD`: tvoje Docker Hub heslo (nebo Access Token)

## Aktualizace INSTALL_SERVER.md

Uprav instalační návod, aby používal image z Docker Hub:

```yaml
services:
  mc-panel:
    image: jirkaodv/mc-server-boss:latest  # Místo build: ./mc-panel
    container_name: mc-panel
    restart: unless-stopped
    ports:
      - "5050:5000"
    volumes:
      - ./mc-panel/data:/app/data
    environment:
      - SECRET_KEY=vygeneruj_nahodny_retezec
      - RCON_PASSWORD=Juraj12552
      - RCON_HOST=minecraft_server
      - RCON_PORT=25575
      - MC_CONTAINER_NAME=minecraft_server
    networks:
      - mc-network
    depends_on:
      - mc
```

**Výhody:**
- ✅ Uživatelé nemusí buildovat (rychlejší instalace)
- ✅ Menší velikost stažení (sdílené vrstvy)
- ✅ Automatické buildy při každém push na GitHub

## Verzování

Při každé nové verzi:

```bash
# Vytvoř tag
git tag -a v1.0.1 -m "Release version 1.0.1"
git push origin v1.0.1

# Build a push nové verze
docker build -t jirkaodv/mc-server-boss:1.0.1 .
docker build -t jirkaodv/mc-server-boss:latest .
docker push jirkaodv/mc-server-boss:1.0.1
docker push jirkaodv/mc-server-boss:latest
```

S GitHub Actions se to stane automaticky při push tagu!

## Výsledek

Po nahrání budou uživatelé moci:

```bash
# Jednoduchý pull a spuštění
docker pull jirkaodv/mc-server-boss:latest
docker run -d -p 5050:5000 jirkaodv/mc-server-boss:latest
```

Místo:
```bash
# Složitější build ze zdrojáků
git clone https://github.com/...
cd mc-server-boss
docker build -t mc-panel .
```
