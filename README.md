# MC Server Boss 🎮

A modern, feature-rich web panel for managing Minecraft servers with RCON and SSH integration. Built with Flask and designed for Docker deployment.

## ✨ Features

- **Real-time Server Monitoring**: CPU, RAM, disk usage, TPS, and uptime tracking
- **RCON Console**: Execute commands directly from the web interface
- **Player Management**: Track playtime, sessions, attendance history
- **Plugin-Aware Commands**: Intelligent autocomplete based on installed plugins
- **Global Control**: Bulk actions for all players (teleport, freeze, clear chat)
- **Wiki & Command Reference**: Built-in command documentation filtered by active modules
- **BlueMap Integration**: Embedded live map viewer
- **Whitelist/Blacklist Management**: Easy player access control
- **Session Tracking**: Detailed login/logout history with cumulative playtime

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- A Minecraft server with RCON enabled
- SSH access to the server (optional, for advanced features)

### Installation

#### Option 1: Using Docker Hub (Recommended - Fastest)

```bash
# Pull the pre-built image
docker pull jiriodv/mc-server-boss:latest

# Run with docker-compose
cat > docker-compose.yml << 'EOF'
services:
  mc-panel:
    image: jiriodv/mc-server-boss:latest
    container_name: mc-panel
    ports:
      - "5050:5000"
    volumes:
      - ./data:/app/data
    environment:
      - SECRET_KEY=change_this_to_random_string
      - RCON_PASSWORD=your_rcon_password
      - RCON_HOST=your_minecraft_server_ip
      - RCON_PORT=25575
    restart: unless-stopped
EOF

docker-compose up -d
```

#### Option 2: Build from source

1. **Clone the repository**
   ```bash
   git clone https://github.com/jiriodv/sprava_docker_minecraft_serveru.git
   cd sprava_docker_minecraft_serveru
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your server details
   ```

3. **Start the panel**
   ```bash
   docker-compose up -d
   ```

4. **Access the panel**
   - Open http://localhost:5050
   - Default credentials: `admin` / `admin` (change immediately!)

## ⚙️ Configuration

### Environment Variables

Create a `.env` file or configure directly in `docker-compose.yml`:

```env
# RCON Configuration
RCON_PASSWORD=your_rcon_password
RCON_HOST=192.168.1.100  # Direct connection
RCON_PORT=25575

# SSH Tunnel (optional, for remote servers)
SSH_HOST=your.server.ip
SSH_USER=root
SSH_PASSWORD=your_ssh_password
REMOTE_RCON_HOST=127.0.0.1

# Server Paths (for SSH features)
MC_LOG_PATH=/path/to/minecraft/logs/latest.log
MC_SERVER_PATH=/path/to/minecraft/data

# Docker Integration (for power controls)
MC_CONTAINER_NAME=minecraft_server

# Flask Configuration
SECRET_KEY=change_this_to_random_string
MOCK_MODE=False  # Set to True for testing without a real server

# BlueMap (optional)
BLUEMAP_URL=http://your.server.ip:8100
```

### RCON Setup

Enable RCON in your Minecraft `server.properties`:
```properties
enable-rcon=true
rcon.port=25575
rcon.password=your_secure_password
```

## 📦 Docker Deployment

### Using Docker Compose (Recommended)

```yaml
services:
  mc-panel:
    build: .
    ports:
      - "5050:5000"
    volumes:
      - ./data:/app/data  # Persistent database
    environment:
      - RCON_PASSWORD=your_password
      - RCON_HOST=192.168.1.100
      # ... other variables
    restart: unless-stopped
```

### Standalone Docker

```bash
docker build -t mc-server-boss .
docker run -d \
  -p 5050:5000 \
  -v $(pwd)/data:/app/data \
  -e RCON_PASSWORD=your_password \
  -e RCON_HOST=192.168.1.100 \
  --name mc-panel \
  mc-server-boss
```

## 🔧 Plugin Configuration

The panel automatically adapts to your installed plugins. Configure active modules in the **Konfigurace** section:

- **EssentialsX**: `/spawn`, `/tp`, `/heal`, `/feed`, etc.
- **WorldEdit**: `//wand`, `//set`, `//copy`, `//paste`
- **BlueMap**: Map rendering controls
- **AuthMe**: User management commands

Commands and Wiki entries are filtered based on enabled modules.

## 🛡️ Security

1. **Change default credentials** immediately after first login
2. **Use strong passwords** for RCON and SSH
3. **Enable HTTPS** in production (use reverse proxy like Nginx)
4. **Restrict access** via firewall rules
5. **Keep SECRET_KEY** secure and random

## 📊 Features Overview

### Dashboard
- Real-time server statistics
- Quick command execution
- Player count and list
- System resource monitoring

### Players Section
- Online/offline status
- Total playtime tracking
- Session history
- Individual player actions (teleport, kick, etc.)

### Console
- Full RCON command interface
- Live log streaming (via SSH)
- Command history
- Autocomplete suggestions

### Wiki
- Searchable command reference
- Organized by plugin/module
- Favorite commands
- Usage examples

## 🐛 Troubleshooting

### RCON Connection Failed
- Verify RCON is enabled in `server.properties`
- Check firewall rules (port 25575)
- Ensure correct password and host

### SSH Tunnel Issues
- Verify SSH credentials
- Check SSH port (default 22)
- Ensure SSH server allows password authentication

### Database Errors
- Ensure `./data` directory has write permissions
- Check Docker volume mounts

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built with Flask, HTMX, and Chart.js
- Inspired by modern server management tools
- Community feedback and contributions

## 📧 Support

- Issues: [GitHub Issues](https://github.com/jiriodv/sprava_docker_minecraft_serveru/issues)
- Discussions: [GitHub Discussions](https://github.com/jiriodv/sprava_docker_minecraft_serveru/discussions)

---

**Made with ❤️ for the Minecraft community**
