import socket
import pickle
import time
import threading

class StreamingServer:
    def __init__(self, serverName, address, port):
        self.serverName = serverName
        self.address = address
        self.port = port
        self.neighbors = []  # Lista de (endereço, porta) dos vizinhos
    
    def create_control_message(self):
        # Cria uma mensagem de controle como dicionário
        message = {
            'serverName': self.serverName,
            'latency': (time.time(),time.time()),
            'hops': 0,
            'route': [self.serverName]
        }
        return message
    
    def send_control_message(self):
        sockServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        message = self.create_control_message()
        for neighbor in self.neighbors:
            sockServer.sendto(f"ROUTINGTABLE {pickle.dumps(message)}", neighbor)
        print(f"Servidor {self.serverName}: Mensagem de controle enviada para os vizinhos.")
    
    def periodic_announcements(self, interval=5):
        while True:
            self.send_control_message()
            time.sleep(interval)

    def start(self):
        #Inicia o servidor e o envio de anúncios periódicos
        threading.Thread(target=self.periodic_announcements,daemon=True).start()
        print(f"Servidor {self.serverName} iniciado e enviado anúncios de controle a cada 5 segundos.")