import socketio
import time

# Crea un'istanza del client Socket.IO in modalità bloccante
sio = socketio.Client()

# Connette il client al server
sio.connect()
print("Connected to server")


try:
    while True:
        message = (cmd + chr(13)+chr(10)).encode()
        sio.emit(message)
        # Attende il messaggio del server
        message = sio.call('server_message', timeout=10)
        if message:
            print(f"Message from server: {message}")
            sio.emit('client_response', 'Pong from client')
        else:
            print("Timeout: No response from server")

        # Attende 10 secondi prima di inviare il prossimo messaggio
        time.sleep(10)
except KeyboardInterrupt:
    pass
finally:
    sio.disconnect()
    print("Disconnected from server")