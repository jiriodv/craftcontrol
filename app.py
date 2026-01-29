
import os
import re
import json
import random
import time
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g, redirect, url_for, flash, session, make_response
import struct
import socket
import atexit
import sys
import threading
import time
from sshtunnel import SSHTunnelForwarder
import paramiko
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    user_row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user_row:
        return User(user_row['id'], user_row['username'])
    return None

def clean_mc_string(text):
    if not text: return ""
    # Odstraní § následované libovolným znakem (barvy/formátování)
    # Nahrazujeme mezerou, aby se neslepila slova (např. Reason§rName -> Reason Name)
    return re.sub(r'§.', ' ', text).strip()

def format_playtime(seconds):
    """Převede vteřiny na lidsky čitelný formát (např. 2h 45m)."""
    if not seconds: return "0m"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    elif m > 0:
        return f"{m}m"
    else:
        return "< 1m"

# ... (skip config lines if not modifying them, but tool requires contiguous block?)
# I will use multi_replace or separate calls if far apart.
# clean_mc_string is at line 21. parse_banlist is at 363. Separate calls.


# Konfigurace
RCON_HOST = os.environ.get('RCON_HOST', 'localhost')
RCON_PORT = int(os.environ.get('RCON_PORT', 25575))
RCON_PASSWORD = os.environ.get('RCON_PASSWORD', 'minecraft')
MOCK_MODE = os.environ.get('MOCK_MODE', 'False').lower() == 'true'
BLUEMAP_URL = os.environ.get('BLUEMAP_URL', '')

# Database path - persistent storage
DATA_DIR = '/app/data'
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'mc_panel.db')


# SSH Konfigurace
SSH_HOST = os.environ.get('SSH_HOST')
SSH_PORT = int(os.environ.get('SSH_PORT', 22))
SSH_USER = os.environ.get('SSH_USER')
SSH_PASSWORD = os.environ.get('SSH_PASSWORD')
SSH_TUNNEL = None

# Falešná data pro testování
MOCK_PLAYERS = [
    {'name': 'Steve', 'uuid': 'mock-uuid-1', 'health': 20},
    {'name': 'Alex', 'uuid': 'mock-uuid-2', 'health': 15},
    {'name': 'Student_Pepa', 'uuid': 'mock-uuid-3', 'health': 5},
]
MOCK_LOGS = []

# --- DATABASE ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                name TEXT PRIMARY KEY,
                first_seen TEXT,
                last_seen TEXT,
                group_name TEXT DEFAULT 'Nezařazeno',
                is_online BOOLEAN DEFAULT 0,
                total_playtime INTEGER DEFAULT 0
            )
        ''')
        
        # Migrace: Přidat total_playtime pokud chybí
        try:
            cursor.execute("ALTER TABLE players ADD COLUMN total_playtime INTEGER DEFAULT 0")
        except:
            pass # Sloupec už pravděpodobně existuje
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                id TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 0
            )
        ''')
        
        # Initialize default modules if table is empty
        module_count = cursor.execute('SELECT COUNT(*) FROM modules').fetchone()[0]
        if module_count == 0:
            default_modules = [
                ('worldedit', 1),
                ('bluemap', 1),
                ('essentialsx', 1),
                ('authme', 1)
            ]
            cursor.executemany('INSERT INTO modules (id, enabled) VALUES (?, ?)', default_modules)
        
        # Zajištění správných modulů (smazat staré, nahrát nové)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorite_commands (
                command_id TEXT PRIMARY KEY
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT,
                login_time TEXT,
                logout_time TEXT,
                duration INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Check for system config
        if cursor.execute("SELECT COUNT(*) FROM system_config").fetchone()[0] == 0:
            defaults = [
                ('ssh_host', os.environ.get('SSH_HOST', '')),
                ('ssh_port', os.environ.get('SSH_PORT', '22')),
                ('ssh_user', os.environ.get('SSH_USER', '')),
                ('ssh_password', os.environ.get('SSH_PASSWORD', '')),
                ('rcon_host', os.environ.get('RCON_HOST', 'localhost')),
                ('rcon_port', os.environ.get('RCON_PORT', '25575')),
                ('rcon_password', os.environ.get('RCON_PASSWORD', '')),
                ('bluemap_url', os.environ.get('BLUEMAP_URL', ''))
            ]
            cursor.executemany("INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)", defaults)
        
        # Create default admin user if not exists
        admin_exists = cursor.execute('SELECT 1 FROM users WHERE username = ?', ('admin',)).fetchone()
        if not admin_exists:
            admin_hash = generate_password_hash('admin123')
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', ('admin', admin_hash))
        
        db.commit()

# --- SSH & SYSTEM STATS ---
def get_connection_config():
    """Načte konfiguraci z DB."""
    try:
        db = get_db()
        rows = db.execute("SELECT key, value FROM system_config").fetchall()
        return {row['key']: row['value'] for row in rows}
    except:
        return {}

def get_ssh_client():
    conf = get_connection_config()
    host = conf.get('ssh_host') or os.environ.get('SSH_HOST')
    user = conf.get('ssh_user') or os.environ.get('SSH_USER')
    password = conf.get('ssh_password') or os.environ.get('SSH_PASSWORD')
    port = int(conf.get('ssh_port') or os.environ.get('SSH_PORT', 22))

    if not host or not user: return None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password, timeout=5)
        return client
    except Exception as e:
        print(f"SSH Connection Error: {e}")
        return None

# --- THREAD-SAFE SIMPLE RCON ---
class SimpleRCON:
    def __init__(self, host, password, port=25575):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
        self.request_id = random.randint(0, 2147483647)

    def __enter__(self):
        self.connect()
        self.authenticate()
        return self

    def __exit__(self, type, value, traceback):
        self.disconnect()

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5)
        self.socket.connect((self.host, self.port))

    def disconnect(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def _send(self, out_type, out_data):
        if self.socket is None: raise Exception("Not connected")
        
        # Packet: Size(4), ID(4), Type(4), Body(str+null), Null(1)
        # Type: 3=Login, 2=Command
        out_payload = struct.pack('<ii', self.request_id, out_type) + out_data.encode('utf8') + b'\x00\x00'
        out_length = struct.pack('<i', len(out_payload))
        self.socket.send(out_length + out_payload)

    def _read(self, expected_type):
        # Read length
        in_len_data = b''
        while len(in_len_data) < 4:
            chunk = self.socket.recv(4 - len(in_len_data))
            if not chunk: raise Exception("Connection closed")
            in_len_data += chunk
            
        in_len = struct.unpack('<i', in_len_data)[0]
        
        # Read payload
        in_payload = b''
        while len(in_payload) < in_len:
            chunk = self.socket.recv(in_len - len(in_payload))
            if not chunk: raise Exception("Connection closed")
            in_payload += chunk
            
        # Parse: ID(4), Type(4), Body...
        in_id = struct.unpack('<i', in_payload[0:4])[0]
        in_type = struct.unpack('<i', in_payload[4:8])[0] # Notchecking type strictly
        
        # Body is rest excluding last 2 null bytes
        if len(in_payload) > 10:
            body = in_payload[8:-2]
            return body.decode('utf8', errors='ignore')
        return ""

    def authenticate(self):
        self._send(3, self.password)
        resp = self._read(2) 

    def command(self, cmd):
        if not self.socket:
            self.connect()
            self.authenticate()
        try:
            self._send(2, cmd)
            return self._read(0)
        except Exception as e:
            # Reconnect on failure (broken pipe, timeout)
            print(f"RCON Connection lost ({e}), reconnecting...")
            self.disconnect()
            self.connect()
            self.authenticate()
            self._send(2, cmd)
            return self._read(0)

# Globální RCON klient (aby se nepřipojoval pořád dokola -> log spam)
GLOBAL_RCON = None
RCON_LOCK = threading.Lock()

def get_global_rcon():
    global GLOBAL_RCON
    conf = get_connection_config()
    
    # Pokud nemame instanci, vytvorime ji
    if GLOBAL_RCON is None:
        port = int(conf.get('rcon_port') or RCON_PORT)
        host = conf.get('rcon_host') or RCON_HOST
        password = conf.get('rcon_password') or RCON_PASSWORD

        # Pokud bezime pres tunel, musime pouzit jeho port
        if SSH_TUNNEL and SSH_TUNNEL.is_active:
             host = '127.0.0.1'
             port = SSH_TUNNEL.local_bind_port
        
        GLOBAL_RCON = SimpleRCON(host, password, port=port)
    
    return GLOBAL_RCON

def start_ssh_tunnel():
    global SSH_TUNNEL
    conf = get_connection_config()
    ssh_host = conf.get('ssh_host') or SSH_HOST
    ssh_user = conf.get('ssh_user') or SSH_USER
    ssh_password = conf.get('ssh_password') or SSH_PASSWORD
    ssh_port = int(conf.get('ssh_port') or SSH_PORT)
    rcon_port = int(conf.get('rcon_port') or RCON_PORT)

    if not ssh_host or not ssh_user: return
    
    # Pokud uz bezi, nic nedelat
    if SSH_TUNNEL and SSH_TUNNEL.is_active: return

    try:
        remote_rcon_host = os.environ.get('REMOTE_RCON_HOST', '127.0.0.1')
        print(f"Starting SSH Tunnel to {ssh_user}@{ssh_host} -> {remote_rcon_host}:{rcon_port}...")
        
        SSH_TUNNEL = SSHTunnelForwarder(
            (ssh_host, ssh_port),
            ssh_username=ssh_user,
            ssh_password=ssh_password,
            remote_bind_address=(remote_rcon_host, rcon_port),
            set_keepalive=10.0
        )
        SSH_TUNNEL.start()
        print(f"SSH Tunnel ESTABLISHED! Local port: {SSH_TUNNEL.local_bind_port}")
        
    except Exception as e:
        print(f"FATAL ERROR starting SSH Tunnel: {e}", file=sys.stderr)

def stop_ssh_tunnel():
    global SSH_TUNNEL
    if SSH_TUNNEL:
        SSH_TUNNEL.stop()
        print("SSH Tunnel closed.")

atexit.register(stop_ssh_tunnel)

def get_hw_stats():
    if MOCK_MODE:
        return {
            'ram_pct': 45.0, 
            'ram_detail': "4/16 GB", 
            'disk': "18%", 
            'uptime': "3 days", 
            'cpu_pct': 12.5
        }
    
    stats = {
        'ram_pct': 0, 
        'ram_detail': 'N/A', 
        'ram_total_gb': 0,  # NEW: Total RAM in GB
        'disk': 'N/A', 
        'uptime': 'N/A', 
        'cpu_pct': 0,
        'cpu_cores': 0,
        'hostname': 'N/A',
        'ip': 'N/A'
    }
    
    client = get_ssh_client()
    if client:
        try:
            # RAM Detail: "Used/Total MB" a procenta pro graf
            stdin, stdout, stderr = client.exec_command("free -m | awk 'NR==2{print $3,$2}'")
            ram_raw = stdout.read().decode().strip().split()
            if len(ram_raw) == 2:
                used, total = int(ram_raw[0]), int(ram_raw[1])
                stats['ram_detail'] = f"{used}/{total} MB"
                stats['ram_pct'] = round((used * 100) / total, 1)
                stats['ram_total_gb'] = round(total / 1024, 1)  # Convert MB to GB

            stdin, stdout, stderr = client.exec_command("df -h / | tail -1 | awk '{print $5,$4}'")
            disk_output = stdout.read().decode().strip().split()
            if len(disk_output) == 2:
                stats['disk'] = disk_output[0]  # Percentage (e.g., "18%")
                stats['disk_free'] = disk_output[1]  # Free space (e.g., "45G")
            else:
                stats['disk'] = 'N/A'
                stats['disk_free'] = 'N/A'
            
            stdin, stdout, stderr = client.exec_command("uptime -p")
            stats['uptime'] = stdout.read().decode().strip().replace("up ", "")

            stdin, stdout, stderr = client.exec_command("hostname")
            stats['hostname'] = stdout.read().decode().strip()

            stdin, stdout, stderr = client.exec_command("hostname -I | awk '{print $1}'")
            stats['ip'] = stdout.read().decode().strip()
            
            # MC Process Uptime (Java) - zkusíme najít čas běhu kontejneru nebo java procesu
            container_name = os.environ.get('MC_CONTAINER_NAME', 'informatika')
            # Zkusíme docker inspect pro přesný čas startu kontejneru
            stdin, stdout, stderr = client.exec_command(f"docker inspect -f '{{{{.State.StartedAt}}}}' {container_name}")
            docker_start = stdout.read().decode().strip()
            
            if docker_start and not docker_start.startswith("Error"):
                try:
                    # Docker vrací ISO formát: 2024-01-29T10:00:00.123456789Z
                    # Ořízneme nanosekundy pro jednodušší parsování
                    clean_start = docker_start.split('.')[0]
                    start_dt = datetime.strptime(clean_start, '%Y-%m-%dT%H:%M:%S')
                    diff = datetime.utcnow() - start_dt
                    
                    # Formátování (např. "2h 15m" nebo "3 days")
                    days = diff.days
                    hours, remainder = divmod(diff.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if days > 0:
                        stats['mc_uptime'] = f"{days}d {hours}h"
                    elif hours > 0:
                        stats['mc_uptime'] = f"{hours}h {minutes}m"
                    else:
                        stats['mc_uptime'] = f"{minutes}m"
                except Exception as e:
                    print(f"Docker uptime parse error: {e}")
                    stats['mc_uptime'] = "N/A"
            else:
                # Fallback na ps (pokud není docker nebo selže)
                stdin, stdout, stderr = client.exec_command("ps -eo etime,comm | grep -i java | head -1 | awk '{print $1}'")
                mc_uptime_raw = stdout.read().decode().strip()
                
                # Formátování ps výstupu (např. 01:23:45 nebo 45:12 nebo 1-02:03:04)
                if mc_uptime_raw:
                    parts = mc_uptime_raw.split(':')
                    if len(parts) == 2: # mm:ss
                        m, s = int(parts[0]), int(parts[1])
                        stats['mc_uptime'] = f"{m}m" if m > 0 else f"{s}s"
                    elif len(parts) == 3: # hh:mm:ss
                        h, m = int(parts[0]), int(parts[1])
                        if '-' in str(h): # d-hh
                            d_h = str(h).split('-')
                            stats['mc_uptime'] = f"{d_h[0]}d {d_h[1]}h"
                        else:
                            stats['mc_uptime'] = f"{h}h {m}m"
                    else:
                        stats['mc_uptime'] = mc_uptime_raw
                else:
                    stats['mc_uptime'] = "Offline"
            
            # CPU Usage - using mpstat for more accurate readings
            # Try mpstat first (more accurate), fallback to top
            stdin, stdout, stderr = client.exec_command("mpstat 1 1 | awk '/Average/ {print 100 - $NF}'")
            cpu_raw = stdout.read().decode().strip().replace(',', '.')
            
            # If mpstat fails, try top as fallback
            if not cpu_raw or cpu_raw == "100":
                stdin, stdout, stderr = client.exec_command("top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8}'")
                cpu_raw = stdout.read().decode().strip().replace(',', '.')
            
            try:
                stats['cpu_pct'] = round(float(cpu_raw), 1)  # Round to 1 decimal
            except:
                stats['cpu_pct'] = 0
            
            # CPU Core Count
            stdin, stdout, stderr = client.exec_command("nproc")
            cpu_cores_raw = stdout.read().decode().strip()
            try:
                stats['cpu_cores'] = int(cpu_cores_raw)
            except:
                stats['cpu_cores'] = 0
                
        except Exception as e:
            print(f"HW Stats Error: {e}")
        finally:
            client.close()
    return stats

# --- RCON HELPER ---
def get_rcon_response(command):
    global MOCK_PLAYERS, MOCK_LOGS
    
    if MOCK_MODE:
        MOCK_LOGS.append(f"> {command}")
        response = "Unknown command"
        if command == "list":
            names = [p['name'] for p in MOCK_PLAYERS]
            response = f"There are {len(names)} of 20 players online: {', '.join(names)}"
        elif command.startswith("kick "):
            target = command.split(' ')[1]
            MOCK_PLAYERS = [p for p in MOCK_PLAYERS if p['name'] != target]
            response = f"Kicked {target}"
        elif command.startswith("ban "):
             target = command.split(' ')[1]
             MOCK_PLAYERS = [p for p in MOCK_PLAYERS if p['name'] != target]
             response = f"Banned {target}"
        elif command == "tps": response = "TPS: 20.0"
        elif command == "pl": response = "Plugins: CoreProtect, Essentials"
        else: response = "Command executed (Mock)"
        MOCK_LOGS.append(response)
        return response

    try:
        # POUŽITÍ GLOBÁLNÍHO RCONU S LOCKEM
        # Zkontrolujeme, zda se nezměnil stav tunelu (např. spadl a nahodil se na jiném portu?)
        # Pro jednoduchost předpokládáme, že pokud tunel běží, používáme jeho port.
        
        with RCON_LOCK:
            rcon = get_global_rcon()
            return rcon.command(command)

    except Exception as e:
        # Pokud dojde k chybě, možná je třeba resetovat globální instanci příště
        global GLOBAL_RCON
        GLOBAL_RCON = None # Force recreation next time
        import traceback
        import sys
        # traceback.print_exc(file=sys.stderr) # Uncomment for debug
        print(f"RCON Error: {e}", file=sys.stderr)
        return f"Error: {e}"

def parse_players(list_output):
    """Robustně parsuje hráče z příkazu 'list'."""
    if not list_output: return []
    
    # Vyčištění od MC formátování (§a, §l atd.) - nahradit mezerou
    output = clean_mc_string(list_output)
    
    # Strategie: Najít všechna slova, která NEJSOU následována dvojtečkou (Group names)
    # a která NEJSOU v blacklistu běžných slov.
    
    SKIP_WORDS = {
        'there', 'are', 'of', 'max', 'maximum', 'players', 'online', 'server', 
        'total', 'list', 'connected', 'and', 'or', 'in', 'out', 'from'
    }
    
    # Regex: slovo 3-16 znaků.
    # Lookahead (?!\s*:) zajistí, že za slovem není dvojtečka (nepovinné mezery mezitím)
    potential_matches = re.findall(r'\b([a-zA-Z0-9_]{3,16})\b(?!\s*:)', output)
    
    valid_names = []
    for name in potential_matches:
        if name.lower() not in SKIP_WORDS:
            valid_names.append(name)
            
    print(f"DEBUG: Parsed players from '{output[:50]}...': {valid_names}")
    return sorted(list(set(valid_names)))


def parse_banlist(banlist_output):
    """Ultra-robustní parsování banlistu s podporou pro více jmen na řádku."""
    if not banlist_output: return []
    
    # Vyčištění od barev a rozdělení na řádky
    output = clean_mc_string(banlist_output)
    
    found_names = set()
    
    # 1. Zkusíme parsrovat Essentials formát: "Player was banned by Admin: Reason"
    # Díky úpravě clean_mc_string jsou slova oddělena mezerami, i když tam byly barvy.
    # Pattern: slovo následované " was banned by"
    # \b(\w+) was banned by
    # Zvýšen limit na 50 znaků, protože jména mohou být slepená s předchozím slovem (např. serveruJirka)
    essentials_matches = re.findall(r'\b([a-zA-Z0-9_]{3,50})\s+was banned by', output)
    if essentials_matches:
        for name in essentials_matches:
            # Fix pro slepená jména (specifický problém "Pravidla serveruNAME")
            # Pokud jméno začíná na "serveru" a následuje Velké Písmeno, ořízneme "serveru".
            if name.startswith('serveru') and len(name) > 7 and name[7].isupper():
                name = name[7:]
                
            # Validace délky MC jména (3-16 znaků)
            if 3 <= len(name) <= 16:
                found_names.add(name)
            
    # 2. Pokud nic nenajdeme, zkusíme Vanilla formát: "There are X banned players: name1, name2"
    elif ':' in output and "banned players" in output:
        names_part = output.split(':')[-1].strip()
        names = [n.strip() for n in names_part.split(',')]
        for name in names:
            if re.match(r'^[a-zA-Z0-9_]{3,16}$', name):
                found_names.add(name)
    
    # Fallback: Stará agresivní metoda (jen pokud předchozí nic nenašly)
    if not found_names:
        lines = [line.strip() for line in output.split('\n') if line.strip()]
        mc_name_re = re.compile(r'\b([a-zA-Z0-9_]{3,16})\b')
        blacklisted_words = {
            'online', 'banned', 'players', 'there', 'reason', 'rules', 'server', 
            'player', 'list', 'names', 'none', 'error', 'was', 'were', 'has', 'have',
            'are', 'is', 'total', 'and', 'with', 'for', 'by', 'console'
        }
        for line in lines:
            matches = mc_name_re.findall(line)
            for m in matches:
                if m.lower() not in blacklisted_words:
                    found_names.add(m)
                    
    return sorted(list(found_names))


    
    for line in lines:
        if "no banned players" in line.lower(): continue
        
        # Extrahujeme VŠECHNA potenciální jména z řádku
        candidates = mc_name_re.findall(line)
        for name in candidates:
            if name.lower() not in blacklisted_words:
                found_names.add(name)

    return sorted(list(found_names))








def sync_players_to_db(online_names):
    """Synchronizuje seznam online hráčů s databází."""
    db = get_db()
    cursor = db.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Resetovat status online pro všechny
    cursor.execute("UPDATE players SET is_online = 0")
    
    # 2. Update/Insert pro online hráče
    for name in online_names:
        cursor.execute("SELECT name FROM players WHERE name = ?", (name,))
        if cursor.fetchone():
            cursor.execute("UPDATE players SET is_online = 1, last_seen = ? WHERE name = ?", (now, name))
        else:
            cursor.execute("INSERT INTO players (name, first_seen, last_seen, is_online) VALUES (?, ?, ?, 1)", (name, now, now))
    
    db.commit()

# --- ROUTES ---

def get_grouped_commands(active_mods):
    """Pomocná funkce pro seskupení příkazů a přidání infa o oblíbených."""
    db = get_db()
    favs = [r['command_id'] for r in db.execute("SELECT command_id FROM favorite_commands").fetchall()]
    
    commands_data = []
    try:
        with open('commands.json', 'r', encoding='utf-8') as f:
            all_commands = json.load(f).get('commands', [])
            # Filtrovat podle modulů
            filtered = [c for c in all_commands if c.get('module') in active_mods]
            
            # Seskupit podle module
            groups = {}
            for c in filtered:
                m = c.get('module', 'base')
                if m not in groups: groups[m] = []
                # Přidat info o favoritovi
                c['is_favorite'] = c.get('id') in favs
                groups[m].append(c)
            
            # Přidat speciální grupu pro oblíbené (pokud nějaké jsou)
            all_favs = [c for c in filtered if c.get('id') in favs]
            
            return {
                "groups": groups,
                "favorites": all_favs
            }
    except Exception as e:
        print(f"Wiki error: {e}")
        return {"groups": {}, "favorites": []}

# --- AUTHENTICATION ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db()
        user_row = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user_row and check_password_hash(user_row['password_hash'], password):
            user = User(user_row['id'], user_row['username'])
            login_user(user, remember=request.form.get('remember') == 'on')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Neplatné přihlašovací údaje', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- DASHBOARD ROUTES ---
@login_required
@app.route('/')
@login_required
def dashboard():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM modules WHERE enabled = 1")
    active_mods = [r['id'] for r in cursor.fetchall()]
    active_mods.append('base')

    data = get_grouped_commands(active_mods)
    return render_template('dashboard.html', 
                           grouped_commands=data['groups'], 
                           favorites=data['favorites'],
                           mock_mode=MOCK_MODE)


@login_required
@app.route('/api/wiki')
def api_wiki():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM modules WHERE enabled = 1")
    active_mods = [r['id'] for r in cursor.fetchall()]
    active_mods.append('base')

    data = get_grouped_commands(active_mods)
    return render_template('partials/wiki_table.html', 
                           grouped_commands=data['groups'], 
                           favorites=data['favorites'])

@login_required
@app.route('/api/commands/favorite/toggle', methods=['POST'])
def toggle_favorite():
    cmd_id = request.form.get('id')
    db = get_db()
    # Check if exists
    row = db.execute("SELECT command_id FROM favorite_commands WHERE command_id = ?", (cmd_id,)).fetchone()
    if row:
        db.execute("DELETE FROM favorite_commands WHERE command_id = ?", (cmd_id,))
    else:
        db.execute("INSERT INTO favorite_commands (command_id) VALUES (?)", (cmd_id,))
    db.commit()
    return jsonify({"status": "success"})

@login_required
@app.route('/players/list')
@login_required
def players_list():
    """Vrátí fragment a zároveň provede synchronizaci DB."""
    response = get_rcon_response("list")
    online_names = []
    if response:
        online_names = parse_players(response)
    
    # Sync to DB (zajistí, že online hráči jsou v DB a mají is_online=1, ostatní 0)
    sync_players_to_db(online_names)
    
    # Načíst VŠECHNY hráče z DB (historie)
    db = get_db()
    players_data = [] 
    
    # Seřadit: Online první, pak podle posledního vidění
    all_players_rows = db.execute("SELECT name, group_name, is_online, last_seen, total_playtime FROM players ORDER BY is_online DESC, last_seen DESC").fetchall()
    
    for row in all_players_rows:
        is_online = bool(row['is_online'])
        playtime = row['total_playtime'] or 0
        
        # Live calculation: Pokud je online, přičíst čas od posledního přihlášení
        if is_online:
            active_session = db.execute('SELECT login_time FROM attendance WHERE player_name = ? AND logout_time IS NULL ORDER BY login_time DESC LIMIT 1', (row['name'],)).fetchone()
            if active_session:
                try:
                    login_dt = datetime.strptime(active_session['login_time'], '%Y-%m-%d %H:%M:%S')
                    duration = int((datetime.now() - login_dt).total_seconds())
                    playtime += duration
                except: pass

        players_data.append({
            'name': row['name'],
            'avatar_url': f"https://cravatar.eu/helmavatar/{row['name']}/64.png",
            'group': row['group_name'] if row['group_name'] else 'Nezařazeno',
            'is_online': is_online,
            'last_seen': row['last_seen'],
            'playtime_raw': playtime,
            'playtime_formatted': format_playtime(playtime)
        })
        
    # Načíst aktivní moduly
    cursor = db.cursor()
    cursor.execute("SELECT id FROM modules WHERE enabled = 1")
    active_mods = [r['id'] for r in cursor.fetchall()]

    # Přidat hlavičku se seznamem online hráčů pro našeptávač (Versio 6.3)
    resp = make_response(render_template('partials/player_list.html', players=players_data, active_modules=active_mods))
    resp.headers['X-Online-Players'] = ",".join(online_names)
    return resp

@login_required
@app.route('/api/stats')
def api_stats():
    hw = get_hw_stats()
    tps_resp = get_rcon_response("tps")
    
    # Vyčištění TPS od barevných kódů a zkrácení
    clean_tps = clean_mc_string(tps_resp)
    tps = clean_tps if clean_tps and "Error" not in clean_tps else "N/A"
    
    # Online Players Info
    list_resp = get_rcon_response("list")
    players = []
    # Only parse players if response is valid (doesn't contain "Error")
    if list_resp and not list_resp.startswith("Error"):
        players = parse_players(list_resp)
    
    # Prepare active modules list for frontend
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM modules WHERE enabled = 1")
    active_mods = [r['id'] for r in cursor.fetchall()]
    active_mods.append('base')

    mc_uptime_raw = hw.get('mc_uptime')
    is_up = mc_uptime_raw not in [None, 'N/A', 'Offline']
    
    return jsonify({
        'ram_pct': f"{hw['ram_pct']}%",
        'ram_detail': hw['ram_detail'],
        'ram_total_gb': hw.get('ram_total_gb', 0),
        'cpu_pct': f"{hw['cpu_pct']}%",
        'cpu_cores': hw.get('cpu_cores', 0),
        'disk': hw['disk'],
        'disk_free': hw.get('disk_free', 'N/A'),
        'uptime': hw['uptime'], 
        'mc_uptime_label': "Minecraft server běží" if is_up else "",
        'mc_uptime_value': mc_uptime_raw if is_up else (mc_uptime_raw or 'N/A'),
        'mc_uptime_full': f"Minecraft server běží {mc_uptime_raw}" if is_up else (mc_uptime_raw or 'N/A'),
        'tps': tps,
        'hostname': hw.get('hostname', 'N/A'),
        'ip': hw.get('ip', 'N/A'),
        'players_count': len(players),
        'players_list': players,
        'bluemap_url': BLUEMAP_URL,
        'active_modules': active_mods
    })

# --- ATTENDANCE & MONITORING ---

@app.route('/api/attendance', methods=['GET'])
@login_required
def get_attendance():
    db = get_db()
    rows = db.execute('SELECT * FROM attendance ORDER BY login_time DESC LIMIT 100').fetchall()
    return jsonify([dict(row) for row in rows])

@login_required
@app.route('/api/player/detail/<name>')
def get_player_detail(name):
    """Vrátí kompletní historii a statistiky pro konkrétního hráče."""
    db = get_db()
    
    # Základní info
    player = db.execute('SELECT * FROM players WHERE name = ?', (name,)).fetchone()
    if not player:
        return jsonify({"status": "error", "message": "Hráč nenalezen"}), 404
    
    # Historie docházky
    sessions = db.execute('''
        SELECT login_time, logout_time, duration 
        FROM attendance 
        WHERE player_name = ? 
        ORDER BY login_time DESC 
        LIMIT 50
    ''', (name,)).fetchall()
    
    # Live calculation pro detail
    total_playtime = player['total_playtime'] or 0
    is_online = bool(player['is_online'])
    if is_online:
        active_session = db.execute('SELECT login_time FROM attendance WHERE player_name = ? AND logout_time IS NULL ORDER BY login_time DESC LIMIT 1', (name,)).fetchone()
        if active_session:
            try:
                login_dt = datetime.strptime(active_session['login_time'], '%Y-%m-%d %H:%M:%S')
                duration = int((datetime.now() - login_dt).total_seconds())
                total_playtime += duration
            except: pass

    return jsonify({
        "status": "success",
        "name": player['name'],
        "group": player['group_name'],
        "total_playtime_raw": total_playtime,
        "total_playtime_formatted": format_playtime(total_playtime),
        "first_seen": player['first_seen'],
        "last_seen": player['last_seen'],
        "sessions": [dict(s) for s in sessions]
    })

def background_attendance_tracker():
    """Běží na pozadí a sleduje, kdo je online, pro účely docházky."""
    while True:
        try:
            with app.app_context():
                players_raw = get_rcon_response("list")
                # Vyhneme se parsingu v mocku nebo při chybě
                if players_raw and not players_raw.startswith("Error"):
                    online_names = parse_players(players_raw)
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    db = sqlite3.connect(DB_PATH) # Přímé spojení ve vlákně
                    db.row_factory = sqlite3.Row
                    cursor = db.cursor()
                    
                    # 1. Kdopak se nám nově přihlásil?
                    for name in online_names:
                        active = cursor.execute('SELECT id FROM attendance WHERE player_name = ? AND logout_time IS NULL', (name,)).fetchone()
                        if not active:
                            cursor.execute('INSERT INTO attendance (player_name, login_time) VALUES (?, ?)', (name, now))
                            db.commit()
                    
                    # 2. Kdopak se nám odhlásil?
                    active_sessions = cursor.execute('SELECT id, player_name, login_time FROM attendance WHERE logout_time IS NULL').fetchall()
                    for session in active_sessions:
                        if session['player_name'] not in online_names:
                            login_dt = datetime.strptime(session['login_time'], '%Y-%m-%d %H:%M:%S')
                            logout_dt = datetime.now()
                            duration = int((logout_dt - login_dt).total_seconds())
                            
                            cursor.execute('UPDATE attendance SET logout_time = ?, duration = ? WHERE id = ?', 
                                       (now, duration, session['id']))
                            
                            # 3. Přičíst čas k celkovému času hráče (Playtime Insights)
                            cursor.execute('UPDATE players SET total_playtime = total_playtime + ? WHERE name = ?',
                                       (duration, session['player_name']))
                            db.commit()
                    db.close()
                        
        except Exception as e:
            print(f"[ATTENDANCE-ERROR] {e}")
            
        time.sleep(60) # Kontrola každou minutu

# Spustit tracker v samostatném vlákně
threading.Thread(target=background_attendance_tracker, daemon=True).start()

# --- SYSTEM CONFIG API ---
@app.route('/api/config/system', methods=['GET', 'POST'])
@login_required
def system_config_api():
    if request.method == 'GET':
        return jsonify(get_connection_config())
    
    if request.method == 'POST':
        data = request.json
        db = get_db()
        
        # Validace a uložení
        keys = ['ssh_host', 'ssh_port', 'ssh_user', 'ssh_password', 'rcon_host', 'rcon_port', 'rcon_password', 'bluemap_url']
        for key in keys:
            if key in data:
                db.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, data[key]))
        
        db.commit()
        db.close()
        
        # Restart connections with new config
        global GLOBAL_RCON
        if GLOBAL_RCON:
            try: GLOBAL_RCON.disconnect()
            except: pass
            GLOBAL_RCON = None
            
        stop_ssh_tunnel()
        # Start se provede automaticky při příštím requestu nebo manuálně
        
        return jsonify({"status": "success", "message": "Nastavení systému uloženo. Připojení bude obnoveno."})

# --- SERVER PROPERTIES EDITOR ---

SERVER_PROPS_HELP = {
    "pvp": "Povoluje nebo zakazuje útočení a boj mezi hráči navzájem.",
    "difficulty": "Nastavuje náročnost přežití (peaceful, easy, normal, hard).",
    "gamemode": "Výchozí herní režim pro nové i stávající hráče (survival, creative, adventure).",
    "max-players": "Maximální počet hráčů, kteří se mohou současně připojit na server.",
    "view-distance": "Vzdálenost (v chuncích), na kterou server posílá data o světě hráčům.",
    "allow-flight": "Povoluje hráčům používat létání, pokud mají k dispozici příslušné mody nebo schopnosti.",
    "white-list": "Povoluje vstup na server pouze hráčům, kteří jsou uvedeni na seznamu (whitelistu).",
    "motd": "Zpráva, která se zobrazí pod názvem serveru v herním seznamu serverů.",
    "online-mode": "Zapíná ověřování pravosti účtů u Mojangu (nutné pro povolený 'warez').",
    "level-seed": "Kód použitý pro náhodné generování světa. Platí pouze při startu nového světa.",
    "spawn-protection": "Velikost chráněné zóny kolem spawnu, kde nemohou běžní hráči ničit bloky.",
    "enable-command-block": "Zapíná nebo vypíná funkčnost příkazových bloků (Command Blocks).",
    "force-gamemode": "Vynutí výchozí herní režim při každém připojení hráče na server.",
    "generate-structures": "Zda se mají v nově generovaném světě tvořit vesnice, chrámy a další stavby.",
    "level-name": "Název složky, ve které je uložen aktuální svět serveru.",
    "simulation-distance": "Vzdálenost od hráče, ve které probíhá simulace světa (růst rostlin, pohyb entit).",
    "enforce-whitelist": "Vynutí okamžité vyhození hráčů, kteří po zapnutí whitelistu nejsou na seznamu.",
    "allow-nether": "Povoluje hráčům vstup do dimenze Peklo (The Nether).",
    "spawn-monsters": "Zda se mají v noci a v temnotě automaticky objevovat příšery.",
    "spawn-animals": "Zda se mají v přírodě automaticky objevovat mírumilovná zvířata.",
    "function-permission-level": "Nastavuje úroveň oprávnění pro spouštění funkcí z datových balíčků.",
    "level-type": "Určuje typ generovaného světa (default, flat, large_biomes, amplified).",
    "server-ip": "IP adresa, na které server naslouchá. Obvykle nechte prázdné.",
    "server-port": "Port, na kterém server běží. Výchozí je 25565.",
    "enable-query": "Umožňuje externím nástrojům získávat informace o serveru.",
    "enable-rcon": "Umožňuje vzdálený přístup ke konzoli serveru přes protokol RCON.",
    "rcon.password": "Heslo pro vzdálený přístup ke konzoli (RCON).",
    "rcon.port": "Port pro vzdálený přístup ke konzoli (RCON).",
    "op-permission-level": "Nastavuje úroveň práv pro operátory serveru (1-4).",
    "resource-pack": "Adresa URL na balíček textur, který se má hráčům nabídnout ke stažení.",
    "resource-pack-sha1": "Kontrolní součet (SHA-1) pro ověření integrity balíčku textur.",
    "player-idle-timeout": "Čas v minutách, po kterém bude neaktivní hráč automaticky odpojen.",
    "hardcore": "Pokud je true, hráč po smrti automaticky dostane ban a nemůže se vrátit.",
    "broadcast-console-to-ops": "Odesílá výpis konzole všem operátorům, kteří jsou online.",
    "enable-status": "Zda se má server zobrazovat jako 'online' v seznamu serverů.",
    "network-compression-threshold": "Práh pro kompresi síťových paketů. Méně = vyšší zátěž CPU.",
    "snooper-enabled": "Zasílá anonymní data o používání serveru Mojangu.",
    "use-native-transport": "Optimalizace síťového přenosu pro Linux (epoll/kqueue).",
    "entity-broadcast-range-percentage": "Jak daleko od hráče se mají zobrazovat ostatní entity (zvířata, hráči).",
    "hide-online-players": "Skryje seznam online hráčů v okně dotazu serveru.",
    "log-ips": "Ukládá IP adresy hráčů do logu serveru.",
    "prevent-proxy-connections": "Pokusí se zablokovat hráče připojující se přes VPN nebo Proxy.",
    "rate-limit": "Maximální počet paketů za sekundu, které může hráč odeslat.",
    "sync-chunk-writes": "Synchronní zápis chunků na disk. Zvyšuje bezpečnost dat, může snížit výkon.",
    "text-filtering-config": "Konfigurace pro filtrování textu (u některých poskytovatelů).",
    "spawn-npcs": "Zda se mají v nově generovaných světech objevovat vesničané.",
    "max-tick-time": "Maximální povolená doba trvání jednoho tiku (v ms), než se server sám vypne.",
    "max-build-height": "Maximální výška (počet bloků), ve které lze stavět.",
    "max-world-size": "Polygonový poloměr herního světa (v blocích).",
    "require-resource-pack": "Vynutí stažení balíčku textur; bez něj se hráč nepřipojí.",
    "accepts-transfers": "Zda server přijímá přenosy hráčů z jiných herních instancí.",
    "broadcast-rcon-to-ops": "Zda se mají RCON příkazy a jejich výstupy vypisovat online operátorům.",
    "enable-jmx-monitoring": "Povoluje monitorování JVM pomocí JMX (pro pokročilé ladění výkonu).",
    "previews-chat": "Zda se mají v chatu zobrazovat náhledy zpráv před odesláním (zabezpečený chat).",
    "initial-enabled-packs": "Seznam datových balíčků, které mají být aktivní hned od začátku.",
    "initial-disabled-packs": "Seznam datových balíčků, které mají být zakázané hned od začátku.",
    "enable-code-of-conduct": "Zda se má na serveru vynucovat dodržování pravidel chování (Code of Conduct).",
    "enforce-secure-profile": "Vyžaduje, aby hráči měli kryptograficky podepsaný profil od Mojangu (brání padělání chatu).",
    "generator-settings": "Detailní JSON nastavení pro generátor světa (např. u typu Flat).",
    "management-server-allowed-origins": "Seznam povolených domén, které mohou přistupovat k management API serveru.",
    "management-server-enabled": "Zapíná nebo vypíná vestavěný management server pro vzdálenou správu.",
    "management-server-port": "Port, na kterém naslouchá vestavěný management server.",
    "region-file-compression": "Typ komprese pro soubory regionů (zlib, gzip, none).",
    "pause-when-empty-interval": "Interval (v milisekundách), po kterém se server 'uspí', pokud na něm nikdo není.",
    "player-list-name-view-distance": "Vzdálenost, na kterou se v seznamu hráčů (TAB) zobrazují jména v jiných barvách (u teamů).",
    "log-ips": "Zda se mají ukládat IP adresy všech připojujících se hráčů do logu."
}

@app.route('/api/config/server_properties', methods=['GET'])
@login_required
def get_server_properties():
    try:
        path = os.environ.get('MC_SERVER_PATH', '.') + '/server.properties'
        content = ""
        
        if SSH_HOST and not MOCK_MODE:
            client = get_ssh_client()
            if not client: return jsonify({"status": "error", "message": "SSH connect failed"}), 500
            stdin, stdout, stderr = client.exec_command(f"cat {path}")
            content = stdout.read().decode()
            client.close()
        else:
            # Mock nebo Local
            if os.path.exists(path):
                with open(path, 'r') as f: content = f.read()
            else:
                content = "pvp=true\ndifficulty=normal\ngamemode=survival\nmax-players=20"
        
        props = []
        found_keys = set()
        
        for line in content.splitlines():
            if line.startswith('#') or '=' not in line: continue
            key, val = line.split('=', 1)
            key = key.strip()
            found_keys.add(key)
            props.append({
                "key": key,
                "value": val.strip(),
                "help": SERVER_PROPS_HELP.get(key, "")
            })
            
        # Inject critical RCON/Net settings if missing
        required_keys = {
            "enable-rcon": "false",
            "rcon.password": "",
            "rcon.port": "25575",
            "broadcast-rcon-to-ops": "true",
            "server-port": "25565",
            "server-ip": ""
        }
        
        for rk, default_val in required_keys.items():
            if rk not in found_keys:
                props.append({
                    "key": rk,
                    "value": default_val,
                    "help": SERVER_PROPS_HELP.get(rk, "") + " (Přidáno aplikací)"
                })
                
        return jsonify(props)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/config/server_properties/save', methods=['POST'])
@login_required
def save_server_properties():
    data = request.json
    if not data: return jsonify({"status": "error", "message": "No data"}), 400
    
    try:
        path = os.environ.get('MC_SERVER_PATH', '.') + '/server.properties'
        
        # 1. Načíst stávající obsah
        orig_lines = []
        if SSH_HOST and not MOCK_MODE:
            client = get_ssh_client()
            stdin, stdout, stderr = client.exec_command(f"cat {path}")
            orig_lines = stdout.read().decode().splitlines()
        else:
            if os.path.exists(path):
                with open(path, 'r') as f: orig_lines = f.read().splitlines()
            else:
                orig_lines = ["pvp=true", "difficulty=normal", "gamemode=survival", "max-players=20"]
            
        # 2. Upravit hodnoty
        new_lines = []
        for line in orig_lines:
            found = False
            for entry in data:
                if line.startswith(f"{entry['key']}="):
                    new_lines.append(f"{entry['key']}={entry['value']}")
                    found = True
                    break
            if not found:
                new_lines.append(line.strip())
        
        # 3. Uložit zpět
        final_content = "\n".join(new_lines)
        if SSH_HOST and not MOCK_MODE:
            client.exec_command(f"printf '%s' \"{final_content}\" > {path}")
            client.close()
        else:
            with open(path, 'w') as f: f.write(final_content)
            
        return jsonify({"status": "success", "message": "Nastavení uloženo. Pro projevení změn restartujte MC server."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@login_required
@app.route('/api/config/example_docker_compose')
def view_sample_config():
    """Vrátí obsah vzorového docker-compose.yml"""
    try:
        path = os.path.join(os.path.dirname(__file__), 'server-docker-compose.example.yml')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"status": "success", "content": content})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Nelze načíst vzorový soubor: {str(e)}"}), 500

@login_required
@app.route('/api/console', methods=['POST'])
def console_command():
    cmd = request.form.get('command')
    if not cmd: return "Empty", 400
    resp = get_rcon_response(cmd)
    return f'<div class="log-entry"><span class="log-cmd">> {cmd}</span><br><span class="log-resp">{resp}</span></div>'

@app.route('/api/action', methods=['POST'])
@login_required
def player_action():
    data = request.form
    player = data.get('player')
    action = data.get('action')
    extra = data.get('extra')
    print(f"[DEBUG-ACTION] Received form data: {dict(data)}")
    print(f"[DEBUG-ACTION] Action: {action}, Player: {player}, Extra: {extra}")
    
    if not player or not action:
        print("[DEBUG-ACTION] ERROR: Missing player or action")
        return jsonify({"status": "error", "message": "Chybí jméno hráče nebo akce"}), 400

    # Core actions
    elif action == 'heal':
        r1 = get_rcon_response(f"effect give {player} minecraft:instant_health")
        r2 = get_rcon_response(f"feed {player}")
        print(f"[DEBUG-ACTION] Heal results: {r1}, {r2}")
    elif action == 'feed':
        r = get_rcon_response(f"feed {player}")
        if "Unknown" in r or "incomplete" in r.lower():
            # Fallback na vanilla saturation
            r = get_rcon_response(f"effect give {player} minecraft:saturation 1 255")
        print(f"[DEBUG-ACTION] Feed result: {r}")
    elif action == 'teleport_here':
        r = get_rcon_response(f"execute in minecraft:overworld run tp {player} 0 100 0") # Pull to center/spawn if @p fails
        print(f"[DEBUG-ACTION] TP result: {r}")
    elif action == 'spawn':
        # Skusíme několik variant, protože různé verze/pluginy reagují různě
        r = get_rcon_response(f"spawn {player}")
        print(f"[DEBUG-ACTION] Spawn attempt 1 (direct): {r}")
        
        if "Unknown" in r or "incomplete" in r.lower():
            r = get_rcon_response(f"essentials:spawn {player}")
            print(f"[DEBUG-ACTION] Spawn attempt 2 (ns): {r}")
            
            if "Unknown" in r or "incomplete" in r.lower():
                r = get_rcon_response(f"execute as {player} run spawn")
                print(f"[DEBUG-ACTION] Spawn attempt 3 (as player): {r}")
                
                if "Unknown" in r or "incomplete" in r.lower():
                    # Poslední záchrana - teleport na souřadnice 0, 100, 0 v Overworldu
                    # Používáme execute, aby to fungovalo i z Netheru
                    r = get_rcon_response(f"execute in minecraft:overworld run tp {player} 0 100 0")
                    print(f"[DEBUG-ACTION] Spawn attempt 4 (tp fallback): {r}")
                    return jsonify({"status": "success", "message": f"Příkaz /spawn neexistuje (chybí EssentialsSpawn). Hráč {player} byl teleportován na 0, 100, 0."})
    elif action == 'clear_effects':
        r = get_rcon_response(f"effect clear {player}")
        print(f"[DEBUG-ACTION] Clear result: {r}")
    elif action == 'kick':
        r = get_rcon_response(f"kick {player} Vyrušování")
        print(f"[DEBUG-ACTION] Kick result: {r}")
    elif action == 'authme_unregister':
        r = get_rcon_response(f"authme unregister {player}")
        print(f"[DEBUG-ACTION] Unreg result: {r}")
    
    # Gamemodes
    elif action == 'gamemode_survival':
        r = get_rcon_response(f"gamemode survival {player}")
        print(f"[DEBUG-ACTION] GMS result: {r}")
    elif action == 'gamemode_creative':
        r = get_rcon_response(f"gamemode creative {player}")
        print(f"[DEBUG-ACTION] GMC result: {r}")
    elif action == 'gamemode_spectator':
        r = get_rcon_response(f"gamemode spectator {player}")
        print(f"[DEBUG-ACTION] GMSP result: {r}")
    
    # Admin tools
    elif action == 'op':
        get_rcon_response(f"op {player}")
    elif action == 'deop':
        get_rcon_response(f"deop {player}")
    elif action == 'mute':
        get_rcon_response(f"mute {player} 5m")
    
    # Freeze logic
    elif action == 'freeze':
        get_rcon_response(f"effect give {player} minecraft:slowness 10000 255")
        get_rcon_response(f"effect give {player} minecraft:jump_boost 10000 255")
    elif action == 'unfreeze':
        get_rcon_response(f"effect clear {player} minecraft:slowness")
        get_rcon_response(f"effect clear {player} minecraft:jump_boost")
    
    # Fun & Rewards
    elif action == 'give_diamond':
        get_rcon_response(f"give {player} minecraft:diamond 1")
    elif action == 'give_custom':
        if extra:
            # Podpora pro "item count", např. "diamond 64"
            parts = extra.strip().split()
            item_id = parts[0].lower().replace(" ", "_")
            count = parts[1] if len(parts) > 1 else "1"
            
            r = get_rcon_response(f"give {player} {item_id} {count}")
            print(f"[DEBUG-ACTION] Give Custom result 1: {r}")
            if "Unknown" in r:
                r = get_rcon_response(f"essentials:give {player} {item_id} {count}")
                print(f"[DEBUG-ACTION] Give Custom result 2: {r}")
            return jsonify({"status": "success", "message": f"Předmět {item_id} ({count}ks) byl předán hráči {player}."})
        else:
            return jsonify({"status": "error", "message": "Nezadali jste předmět k předání."})
    elif action == 'lightning':
        get_rcon_response(f"execute at {player} run summon lightning_bolt")
    elif action == 'get_pos':
        # Send message to admin (source), not simple tellraw to player
        get_rcon_response(f"tellraw @a[level=4] {{\"text\":\"Pozice {player} byla zaznamenána (viz konzole).\",\"color\":\"gray\"}}")
        # Also log to console
        get_rcon_response(f"execute as {player} run data get entity @s Pos")

    # Editable Properties (Inside Info Modal)

    # Editable Properties (Inside Info Modal)
    elif action == 'set_fly_on':
        get_rcon_response(f"fly {player} on")
    elif action == 'set_fly_off':
        get_rcon_response(f"fly {player} off")
    elif action == 'set_god_on':
        get_rcon_response(f"god {player} on")
    elif action == 'set_god_off':
        get_rcon_response(f"god {player} off")
    elif action == 'set_xp':
        if extra: get_rcon_response(f"exp set {player} {extra}")
    elif action == 'set_money':
        if extra: get_rcon_response(f"eco set {player} {extra}")
        
    # Plugins
    elif action == 'we_wand':
        get_rcon_response(f"give {player} minecraft:wooden_axe")
    elif action == 'bluemap_update':
        get_rcon_response(f"bluemap update {player}")
    elif action == 'authme_unreg':
        get_rcon_response(f"authme unregister {player}")
    elif action == 'whois':
        resp = get_rcon_response(f"whois {player}")
        print(f"[DEBUG-ACTION] Whois result: {resp}")
        return jsonify({"status": "success", "response": clean_mc_string(resp)})

    # --- GLOBAL ACTIONS ---
    elif action == 'freeze_all':
        get_rcon_response("effect give @a minecraft:slowness 10000 255")
        get_rcon_response("effect give @a minecraft:jump_boost 10000 255")
        return jsonify({"status": "success", "message": "Všichni hráči byli zmrazeni."})
    elif action == 'unfreeze_all':
        get_rcon_response("effect clear @a minecraft:slowness")
        get_rcon_response("effect clear @a minecraft:jump_boost")
        return jsonify({"status": "success", "message": "Všichni hráči byli odmrazeni."})
    elif action == 'tp_all_here':
        # @p doesn't work well from RCON, using 0 100 0 or similar central point
        get_rcon_response("execute in minecraft:overworld run tp @a 0 100 0")
        return jsonify({"status": "success", "message": "Všichni byli teleportováni na spawn."})
    elif action == 'clear_chat_all':
        for _ in range(20): get_rcon_response("say ")
        get_rcon_response("say §6§lChat byl vyčištěn administrátorem.")
        return jsonify({"status": "success", "message": "Chat byl vyčištěn."})
        
    # Catch-all for actions that didn't return early (heal, spawn, etc.)
    return jsonify({"status": "success", "message": f"Akce {action} pro hráče {player} provedena."})

# --- HISTORY & GROUPS API ---

@app.route('/history/table')
@login_required
def history_table():
    """Vrátí HTML tabulku historie (offline i online)."""
    db = get_db()
    
    # Filtrování
    filter_group = request.args.get('group', 'all')
    
    query = "SELECT * FROM players ORDER BY is_online DESC, last_seen DESC"
    args = ()
    
    if filter_group != 'all':
        query = "SELECT * FROM players WHERE group_name = ? ORDER BY is_online DESC, last_seen DESC"
        args = (filter_group,)
        
    rows = db.execute(query, args).fetchall()
    
    players = []
    for row in rows:
        players.append({
            'name': row['name'],
            'first_seen': row['first_seen'],
            'last_seen': row['last_seen'],
            'group': row['group_name'],
            'is_online': bool(row['is_online']),
            'avatar_url': f"https://cravatar.eu/helmavatar/{row['name']}/32.png"
        })
        
    # Get unique groups for filter
    all_groups = [r['group_name'] for r in db.execute("SELECT DISTINCT group_name FROM players").fetchall()]
    
    return render_template('partials/history_table.html', players=players, groups=all_groups, current_filter=filter_group)

@login_required
@app.route('/api/player/group', methods=['POST'])
def set_group():
    # ... stávající kód ...
    name = request.form.get('name')
    group = request.form.get('group')
    if name and group:
        db = get_db()
        db.execute("UPDATE players SET group_name = ? WHERE name = ?", (group, name))
        db.commit()
    return "", 200

# --- WHITELIST API ---
@login_required
@app.route('/api/whitelist')
def get_whitelist():
    response = get_rcon_response("whitelist list")
    # Response is usually: "There are X whitelisted players: player1, player2..."
    players = []
    if "whitelisted players:" in response:
        names_str = response.split("whitelisted players:")[1].strip()
        if names_str:
            players = [n.strip() for n in names_str.split(",")]
    return jsonify(players)

@login_required
@app.route('/api/whitelist/add', methods=['POST'])
def whitelist_add():
    name = request.form.get('name')
    if name:
        get_rcon_response(f"whitelist add {name}")
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@login_required
@app.route('/api/whitelist/remove', methods=['POST'])
def whitelist_remove():
    # ... stávající kód ...
    name = request.form.get('name')
    if name:
        get_rcon_response(f"whitelist remove {name}")
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

# --- LOGS API ---
@login_required
@app.route('/api/logs')
def get_logs():
    log_path = os.environ.get('MC_LOG_PATH', '/home/minecraft/server/logs/latest.log')
    if MOCK_MODE:
        return jsonify("Mock log entry 1\nMock log entry 2\n[16:30:23 INFO]: Done!")
    
    client = get_ssh_client()
    if not client:
        return jsonify("Error: Could not connect via SSH to read logs."), 500
    
    try:
        # Přečteme posledních 100 řádků
        stdin, stdout, stderr = client.exec_command(f"tail -n 100 {log_path}")
        logs_data = stdout.read().decode('utf8', errors='ignore')
        err_data = stderr.read().decode('utf8', errors='ignore')
        
        if err_data and not logs_data:
             return jsonify(f"CHYBA SSH: {err_data}")
        
        return jsonify(logs_data)
    except Exception as e:
        return jsonify(f"Exception reading logs: {e}"), 500
    finally:
        client.close()

# --- BACKUP API ---
@login_required
@app.route('/api/backup', methods=['POST'])
def run_backup():
    # ... stávající kód ...
    server_path = os.environ.get('MC_SERVER_PATH', '/home/mc/server')
    if MOCK_MODE:
        return jsonify({"status": "success", "message": "Mock backup created (simulated)"})
    
    client = get_ssh_client()
    if not client:
        return jsonify({"status": "error", "message": "SSH Connection failed"}), 500
    
    try:
        # Vytvoření zálohy (tar.gz) - provádí se na pozadí nebo synchronně (zde pro jednoduchost synchronně s timeoutem)
        # Záloha se uloží do složky backups na serveru
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_{timestamp}.tar.gz"
        # Příkaz: vytvoř složku backups pokud neexistuje, a pak zabal
        cmd = f"mkdir -p backups && tar -czf backups/{backup_file} -C {server_path} ."
        stdin, stdout, stderr = client.exec_command(cmd)
        
        # Počkáme na dokončení (pozor, velké světy mohou trvat dlouho)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            return jsonify({"status": "success", "message": f"Záloha {backup_file} byla úspěšně vytvořena na serveru."})
        else:
            err = stderr.read().decode()
            return jsonify({"status": "error", "message": f"Chyba při zálohování: {err}"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": f"Exception: {e}"}), 500
    finally:
        client.close()

# --- MODULES API ---
@login_required
@app.route('/api/modules/toggle', methods=['POST'])
def toggle_module():
    m_id = request.form.get('id')
    enabled = request.form.get('enabled') == 'true'
    if m_id:
        db = get_db()
        db.execute("UPDATE modules SET enabled = ? WHERE id = ?", (1 if enabled else 0, m_id))
        db.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@login_required
@app.route('/api/modules')
def get_active_modules():
    db = get_db()
    rows = db.execute("SELECT id, enabled FROM modules").fetchall()
    return jsonify({row['id']: bool(row['enabled']) for row in rows})

@login_required
@app.route('/api/banlist')
def get_banlist():
    """Načte seznam zabanovaných hráčů (SSH JSON nebo RCON fallback)."""
    # 1. Zkusíme načíst banned-players.json přes SSH (Nejpřesnější)
    if os.environ.get('SSH_HOST'):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                os.environ.get('SSH_HOST'), 
                port=int(os.environ.get('SSH_PORT', 22)), 
                username=os.environ.get('SSH_USER'), 
                key_filename=os.environ.get('SSH_KEY_PATH'),
                password=os.environ.get('SSH_PASSWORD')
            )
            
            # Cesta k JSON souboru
            server_path = os.environ.get('MC_SERVER_PATH')
            if server_path:
                json_path = os.path.join(server_path, 'banned-players.json')
                stdin, stdout, stderr = ssh.exec_command(f"cat {json_path}")
                content = stdout.read().decode().strip()
                
                if content:
                    data = json.loads(content)
                    # Vrátíme pouze jména pro kompatibilitu s frontendem
                    # Seřadíme abecedně (case-insensitive)
                    names = sorted([entry['name'] for entry in data], key=lambda x: x.lower())
                    ssh.close()
                    return jsonify(names)
            ssh.close()
        except Exception as e:
            print(f"SSH Banlist Error: {e}")
            # Pokračujeme na RCON fallback
            
    # 2. Fallback: RCON parsování (Méně přesné)
    response = get_rcon_response("banlist players")
    if not response: return jsonify([])
    
    names = parse_banlist(response)
    return jsonify(names)


@login_required
@app.route('/api/banlist/add', methods=['POST'])
def add_to_banlist():
    name = request.form.get('name')
    reason = request.form.get('reason', 'Pravidla serveru')
    if name:
        get_rcon_response(f"ban {name} {reason}")
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "No name provided"}), 400

@login_required
@app.route('/api/banlist/remove', methods=['POST'])
def remove_from_banlist():
    name = request.form.get('name')
    print(f"DEBUG: Unbanning {name}")
    if name:
        # Pro jistotu zkusíme oba příkazy
        get_rcon_response(f"pardon {name}")
        get_rcon_response(f"unban {name}")
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "No name provided"}), 400



@login_required
@app.route('/api/action/clear', methods=['POST'])
def clear_inventory_action():
    name = request.form.get('name')
    if name:
        get_rcon_response(f"clear {name}")
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "No name"}), 400

@login_required
@app.route('/api/console/send', methods=['POST'])
def console_send():
    """Odeslání libovolného příkazu přes RCON."""
    cmd = request.form.get('command')
    if not cmd:
        return jsonify({"status": "error", "message": "Empty command"}), 400
    
    # Bezpečnostní logování
    print(f"CONSOLE COMMAND: {cmd}")
    
    resp = get_rcon_response(cmd)
    return jsonify({"status": "success", "response": resp})

@app.route('/api/power/<action>', methods=['POST'])
@login_required
def server_power_action(action):
    """Ovládání serveru přes SSH (Docker)."""
    if action not in ['start', 'stop', 'restart']:
        return jsonify({"status": "error", "message": "Invalid action"}), 400
    
    # Získání názvu kontejneru (default informatika)
    container_name = os.environ.get('MC_CONTAINER_NAME', 'informatika')
        
    cmd_map = {
        'start': f'docker start {container_name}',
        'stop': f'docker stop {container_name}',
        'restart': f'docker restart {container_name}'
    }
    
    try:
        # Použijeme centrální konfiguraci
        conf = get_connection_config()
        host = conf.get('ssh_host') or os.environ.get('SSH_HOST')
        user = conf.get('ssh_user') or os.environ.get('SSH_USER')
        password = conf.get('ssh_password') or os.environ.get('SSH_PASSWORD')
        port = int(conf.get('ssh_port') or os.environ.get('SSH_PORT', 22))

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=user, password=password)
        
        stdin, stdout, stderr = ssh.exec_command(cmd_map[action])
        exit_status = stdout.channel.recv_exit_status()
        ssh.close()
        
        if exit_status == 0:
            return jsonify({"status": "success", "message": f"Server {action}ed"})
        else:
            return jsonify({"status": "error", "message": stderr.read().decode()}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@login_required
@app.route('/api/power/status')
def server_status():
    try:
        container_name = os.environ.get('MC_CONTAINER_NAME', 'informatika')
        
        conf = get_connection_config()
        host = conf.get('ssh_host') or os.environ.get('SSH_HOST')
        user = conf.get('ssh_user') or os.environ.get('SSH_USER')
        password = conf.get('ssh_password') or os.environ.get('SSH_PASSWORD')
        port = int(conf.get('ssh_port') or os.environ.get('SSH_PORT', 22))

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=user, password=password)
            
        stdin, stdout, stderr = ssh.exec_command(f"docker inspect -f '{{{{.State.Running}}}}' {container_name}")
        status = stdout.read().decode().strip()
        ssh.close()
        
        return jsonify({"status": "running" if status == 'true' else "stopped"})
    except Exception as e:
        print(f"Status check error: {e}")
        return jsonify({"status": "error", "message": str(e)})
        
        if not status: status = 'unknown'
        # Log status for debugging
        print(f"DEBUG: Docker status: {status}")
        return jsonify({"status": status})
            
    except Exception as e:
        print(f"DEBUG: Status check error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@login_required
@app.route('/api/plugins')
def get_plugins():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            os.environ.get('SSH_HOST'), 
            port=int(os.environ.get('SSH_PORT', 22)), 
            username=os.environ.get('SSH_USER'), 
            key_filename=os.environ.get('SSH_KEY_PATH'),
            password=os.environ.get('SSH_PASSWORD')
        )
        
        plugins_path = os.environ.get('MC_SERVER_PATH', '.') + '/plugins'
        stdin, stdout, stderr = ssh.exec_command(f"ls -1 {plugins_path}")
        
        files = []

        if stdout.channel.recv_exit_status() == 0:
            raw_files = stdout.read().decode().splitlines()
            for f in raw_files:
                if f.endswith('.jar'):
                    files.append({'name': f, 'enabled': True})
                elif f.endswith('.jar.disabled'):
                    files.append({'name': f.replace('.jar.disabled', '.jar'), 'enabled': False})
        
        ssh.close()
        # Seřadit: aktivní první, pak podle abecedy
        files.sort(key=lambda x: (not x['enabled'], x['name']))
        return jsonify(files)
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@login_required
@app.route('/api/plugins/toggle', methods=['POST'])
def toggle_plugin():
    name = request.form.get('name')
    target_state = request.form.get('enabled') == 'true'
    
    if not name: return jsonify({"status": "error", "message": "No name"}), 400
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            os.environ.get('SSH_HOST'), 
            port=int(os.environ.get('SSH_PORT', 22)), 
            username=os.environ.get('SSH_USER'), 
            key_filename=os.environ.get('SSH_KEY_PATH'),
            password=os.environ.get('SSH_PASSWORD')
        )

        
        base_path = os.environ.get('MC_SERVER_PATH', '.') + '/plugins/'
        
        if target_state: 
            # Enable: .jar.disabled -> .jar
            # name už obsahuje .jar (např. "plugin.jar")
            src = base_path + name + ".disabled"
            dst = base_path + name
        else:
            # Disable: .jar -> .jar.disabled
            src = base_path + name
            dst = base_path + name + ".disabled"
            
        stdin, stdout, stderr = ssh.exec_command(f"mv {src} {dst}")
        exit_code = stdout.channel.recv_exit_status()
        ssh.close()
        
        if exit_code == 0:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": stderr.read().decode()}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Kontrola existence DB, pokud ne, init
    if not os.path.exists(DB_PATH):
        # Musíme vytvořit kontext ručně
        pass 
    
    # Hack: Init DB před startem
    # Init DB a SSH před startem
    with app.app_context():
        init_db()
        if not MOCK_MODE:
            start_ssh_tunnel()
        
    app.run(host='0.0.0.0', port=5000, debug=True)

