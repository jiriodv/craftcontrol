import os
import paramiko
from dotenv import load_dotenv

# Load env vars manually just in case
# (In app context they are loaded, here we simulate)
SSH_HOST = os.environ.get('SSH_HOST', '192.168.0.121')
SSH_PORT = int(os.environ.get('SSH_PORT', 22))
SSH_USER = os.environ.get('SSH_USER', 'root')
SSH_KEY_PATH = os.environ.get('SSH_KEY_PATH', '/root/.ssh/id_rsa') # Default in container?
SSH_PASSWORD = os.environ.get('SSH_PASSWORD', 'Juraj12552')

print(f"Testing SSH connection to {SSH_USER}@{SSH_HOST}:{SSH_PORT}...")

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Try connecting
    # Note: In docker-compose, we use password or key. App uses password from env?
    # Let's verify what App uses.
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD, timeout=5)
    
    print("SSH Connection: SUCCESS")
    
    # Try executing a docker command
    stdin, stdout, stderr = ssh.exec_command("docker ps --format '{{.Names}}'")
    exit_status = stdout.channel.recv_exit_status()
    
    if exit_status == 0:
        print("Docker Command Execution: SUCCESS")
        containers = stdout.read().decode().strip().split('\n')
        print(f"Running Containers: {containers}")
        if 'mc_server-mc-1' in containers:
            print(">> Target 'mc_server-mc-1' FOUND. Power commands WILL work.")
        else:
            print(">> Target 'mc_server-mc-1' NOT FOUND via SSH. Power commands might fail.")
    else:
        print(f"Docker Command Failed: {stderr.read().decode()}")

    ssh.close()
except Exception as e:
    print(f"SSH Connection FAILED: {str(e)}")
