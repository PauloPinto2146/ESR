import socket
import threading
import time
from socket import *

# Nó cliente/servidor
class Node:
    def __init__(self, node_name, port=12000, bootstrap_host='10.0.0.1', bootstrap_port=12000):
        self.node_name = node_name
        self.port = port
        self.bootstrap_host = bootstrap_host
        self.bootstrap_port = bootstrap_port
        self.neighbors = [] # IP dos vizinhos

    def register_with_bootstrap(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((self.bootstrap_host, self.bootstrap_port))
        message = f"REGISTER {self.node_name}"
        clientSocket.send(message.encode())
        response = clientSocket.recv(1024).decode('utf-8')
        if "NEIGHBORS" in response:
            ip = response.split()[1:]
            self.neighbors.append(ip)
        clientSocket.close()

    def connection_bootstrap_handler(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((self.bootstrap_host, self.bootstrap_port))
        while True:
            message = f"CHECKREGISTER {self.node_name}"
            clientSocket.send(message.encode())
            response = clientSocket.recv(1024).decode('utf-8')
            if "NEWREGISTER" in response:
                test = response.split()[1:]
                if test not in self.neighbors:
                    self.neighbors.append(test)
            print(f"Eu sou {self.node_name} os meus vizinhos s찾o {self.neighbors}") 
            time.sleep(5)

    def receive_message(self, connectionSocket, addr):
        while True:
            try:
                sentence = connectionSocket.recv(1024).decode()
                if not sentence:
                    break
                print("Recebi HeartBEAT")
                # Responde ao heartbeat do bootstrap
                if sentence.startswith("HEARTBEAT"):
                    connectionSocket.send("HEARTBEAT_ACK".encode())
                else:
                    print(sentence)

            except Exception as e:
                print(f"Error receiving data from {addr}: {e}")
                break

    def receive_client(self, serverSocketUDP):
        while True:
            try:
                message, client_address = serverSocketUDP.recvfrom(1024)
                if message.decode() == "CHECKLATENCY":
                    modified_message = "LATENCYCHECK"
                    serverSocketUDP.sendto(modified_message.encode(), client_address)
            except Exception as e:
                print(f"Erro ao receber mensagem UDP: {e}")

    def start(self):
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSocket.bind(('0.0.0.0', self.port))
        serverSocket.listen(5)

        serverSocketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverSocketUDP.bind(('', self.port))

        # Registrar no bootstrap
        self.register_with_bootstrap()
        
        # Iniciar thread para atualizar vizinhos
        update_thread = threading.Thread(target=self.connection_bootstrap_handler)
        update_thread.start()

        update_thread2 = threading.Thread(target=self.receive_client,args = (serverSocketUDP))
        update_thread2.start()

        # Aguardar mensagens
        while True:
            connectionSocket, addr = serverSocket.accept()
            threading.Thread(target=self.receive_message, args=(connectionSocket, addr)).start()

# Iniciar o n처
if __name__ == "__main__":
    node_name = input("Nome do nó: ")
    node = Node(node_name)
    node.start()
