import paramiko
import time

HOST = "192.168.40.103"
USER = "root"
PASS = "S1N0server2021"

def find_log():
    print(f"Connecting to {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, username=USER, password=PASS)
        print("Connected. Searching for 'latest.log'...")
        
        # 1. Zkusíme najít kde to běží pomocí docker inspect (nejpřesnější metoda)
        # Hledáme kontejner 'informatika' a jeho bind mounty
        print("Checking docker mounts for 'informatika'...")
        stdin, stdout, stderr = ssh.exec_command("docker inspect informatika")
        inspect_out = stdout.read().decode()
        
        if inspect_out:
            print("Found container 'informatika'. Parsing mounts...")
            import json
            try:
                data = json.loads(inspect_out)
                mounts = data[0]['Mounts']
                for m in mounts:
                    if m['Destination'] == '/data':
                        host_path = m['Source']
                        print(f"\nSUCCESS! Docker says '/data' is mounted from: {host_path}")
                        print(f"Predicted log path: {host_path}/logs/latest.log")
                        
                        # Verify
                        s_in, s_out, s_err = ssh.exec_command(f"ls -l {host_path}/logs/latest.log")
                        if "No such file" not in s_err.read().decode():
                            print("VERIFIED: File exists on disk!")
                        else:
                            print("WARNING: File not found yet (server might be starting or never ran).")
                        return
            except Exception as e:
                print(f"Error parsing docker inspect: {e}")
        
        # 2. Fallback: Hledání pomocí find, pokud docker inspect selže nebo kontejner neběží
        print("Docker inspect failed or container not running. Searching filesystem (this might take a while)...")
        commands = [
            "find /home -name latest.log 2>/dev/null",
            "find /root -name latest.log 2>/dev/null",
            "find /opt -name latest.log 2>/dev/null"
        ]
        
        for cmd in commands:
            print(f"Running: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            results = stdout.read().decode().strip()
            if results:
                print(f"\nFOUND CANDIDATES:\n{results}")
                return

        print("\nCould not find 'latest.log' in common locations.")
        
    except Exception as e:
        print(f"SSH Error: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    find_log()
