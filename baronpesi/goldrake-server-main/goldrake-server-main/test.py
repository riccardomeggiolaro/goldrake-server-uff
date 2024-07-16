import socket
import select
import time

class Client:
    def __init__(self, host, port, timeout=1):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.conn = None

    def connect(self):
        try:
            if self.conn:
                self.conn.close()
                print("Closed previous connection.")
            
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.setblocking(False)
            self.conn.settimeout(self.timeout)
            self.conn.connect((self.host, self.port))
            print("Connected to the server.")
        except (socket.error, socket.timeout) as e:
            print(f"Connection error: {e}")

    def send_message(self, message):
        try:
            if not self.conn:
                print("No connection found. Connecting...")
                self.connect()
            
            # Usa select per verificare se la connessione è pronta per scrivere
            readable, writable, _ = select.select([], [self.conn], [], self.timeout)
            
            for conn in writable:
                conn.sendall(message[:1024])
                response = conn.recv(1024)
                print(f"Server response: {response.decode('utf-8')}")
        except (socket.error, socket.timeout) as e:
            print(f"Connection error: {e}")
            self.close_connection()
            print("Reconnecting...")
            self.connect()
            self.send_message(message)

    def close_connection(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            print("Connection closed.")

# Esempio di utilizzo
client = Client('192.168.0.229', 4001)

while True:
    try:
        client.send_message(("01DINT2710" + chr(13)+chr(10)).encode())
        time.sleep(1)
    except KeyboardInterrupt:
        exit()

# Chiudi la connessione
client.close_connection()