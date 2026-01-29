import paramiko
import os

HOST = "192.168.40.103"
USER = "root"
PASS = "S1N0server2021"
REMOTE_PATH = "/root/Docker/MC/petka/data/server.properties"

def debug_rcon():
    print(f"Connecting to {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(HOST, username=USER, password=PASS)
        print("Connected.")
        
        # 1. Check server.properties
        print(f"\n--- Checking {REMOTE_PATH} ---")
        stdin, stdout, stderr = ssh.exec_command(f"cat {REMOTE_PATH} | grep rcon")
        content = stdout.read().decode().strip()
        if content:
            print(content)
        else:
            print("WARNING: No 'rcon' settings found in server.properties!")
            
        # 2. Check if port is listening
        print("\n--- Checking Port 25575 on remote ---")
        stdin, stdout, stderr = ssh.exec_command("netstat -tulpn | grep 25575")
        netstat = stdout.read().decode().strip()
        if netstat:
            print(f"LISTENING:\n{netstat}")
        else:
            print("NOT LISTENING: Port 25575 is closed/ignored on remote server.")
            
        # 3. Check docker logs tail for RCON
        print("\n--- Checking Container Logs for RCON errors ---")
        stdin, stdout, stderr = ssh.exec_command("docker logs informatika --tail 50 | grep -i rcon")
        logs = stdout.read().decode().strip()
        print(logs if logs else "No RCON mentions in last 50 log lines.")

    except Exception as e:
        print(f"SSH Fatal Error: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    debug_rcon()
