import socket
import pickle
import time
import threading

class StreamingServer:
    def __init__(self, serverName, port=12000, bootstrap_host='10.0.0.1', bootstrap_port=12000):
        self.serverName = serverName
        self.port = port
        self.bootstrap_host = bootstrap_host
        self.bootstrap_port = bootstrap_port
        self.neighbors = {} # Nome do No : IP
        self.routingtable = {}
        self.timestamp = 5

    def register_with_bootstrap(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((self.bootstrap_host, self.bootstrap_port))
        message = f"REGISTER {self.serverName}"
        clientSocket.send(message.encode())
        response = clientSocket.recv(1024)
        if response.startswith(b"NEIGHBORS"):
            data = pickle.loads(response[len(b"NEIGHBORS"):])
            self.neighbors = data
            print(self.neighbors)
        clientSocket.close()

    def connection_bootstrap_handler(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((self.bootstrap_host, self.bootstrap_port))
        while True:
            message = f"CHECKREGISTER {self.serverName}"
            clientSocket.send(message.encode())
            response = clientSocket.recv(1024)
            if response.startswith(b"NEWREGISTER"):
                data = pickle.loads(response[len(b"NEWREGISTER"):])
                self.neighbors = data
            print(f"Eu sou {self.serverName} os meus vizinhos são {self.neighbors}") 
            time.sleep(5)   

    def receive_message(self, connectionSocket, addr):
        while True:
            try:
                sentence = connectionSocket.recv(1024).decode()
                if not sentence:
                    break
                print("Recebi HeartBEAT")
                if sentence.startswith("HEARTBEAT"):
                    connectionSocket.send("HEARTBEAT_ACK".encode())
            except Exception as e:
                print(f"Error receiving data from {addr}: {e}")
                break


    def create_control_message(self):
        message = {
            "type": "BUILDTREE",
            "name_sender": self.serverName,
            "latency": (0,time.time()), ## TEMPO ACUMULADO, TEMPO DE ENVIO
            "hops" : 0
        }
        return message
    
    def send_control_message(self):
        message = self.create_control_message()
        for neighbor in self.neighbors:
            ip = self.neighbors[neighbor]
            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                clientSocket.connect((ip, self.port))
                # Serializar e construir a mensagem
                serialized_message = pickle.dumps(message)
                prefixed_message = b"BUILDTREE" + serialized_message

                # Enviar tamanho da mensagem primeiro
                clientSocket.sendall(prefixed_message)  # Enviar a mensagem
            finally:
                clientSocket.close()

    def periodic_send_control_message(self):
        while True:
            print("Vou Construir a árvore")
            self.send_control_message()
            time.sleep(self.timestamp)


    def start(self):
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSocket.bind(('0.0.0.0', self.port))
        serverSocket.listen(5)

        # Registrar no bootstrap
        self.register_with_bootstrap()
        
        # Iniciar thread para atualizar vizinhos
        update_thread = threading.Thread(target=self.connection_bootstrap_handler)
        update_thread.start()    

        build_thread = threading.Thread(target=self.periodic_send_control_message)
        build_thread.start() 

        # Aguardar mensagens
        while True:
            connectionSocket, addr = serverSocket.accept()
            threading.Thread(target=self.receive_message, args=(connectionSocket, addr)).start()

# Iniciar o Server
if __name__ == "__main__":
    serverName = input("Nome do Server: ")
    Server = StreamingServer(serverName)
    Server.start()
