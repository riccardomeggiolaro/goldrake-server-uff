import psutil

def close_connections(target_ip, target_port):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.raddr and (conn.raddr[0] == target_ip and conn.raddr[1] == target_port):
                    proc.terminate()
                    print(f"Terminated process {proc.pid} which had connection to {target_ip}:{target_port}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

# Indirizzo IP e porta da chiudere
target_ip = '192.168.0.229'
target_port = 4101

close_connections(target_ip, target_port)