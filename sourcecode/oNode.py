import socket
import threading
import time
import pickle

# Nó cliente/servidor
class Node:
    def __init__(self, nodeName, port=12000, bootstrap_host='10.0.0.1', bootstrap_port=12000):
        self.nodeName = nodeName
        self.port = port
        self.bootstrap_host = bootstrap_host
        self.bootstrap_port = bootstrap_port
        self.neighbors = {} # Nome do No : IP
        self.retry_timeout = 15
        self.max_retry = 5
        '''
        Info da routing table
        message = {
            "Type": "BUILDTREE"
            "name_sender": self.serverName,
            "latency": (0,time.time()), ## TEMPO ACUMULADO, TEMPO DE ENVIO
            "hops" : 0
        }
        '''
        self.routingtable = {} # Dicionario  ->   nomedosender: (tempoacumalado,saltos)
        
    def register_with_bootstrap(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((self.bootstrap_host, self.bootstrap_port))
        message = f"REGISTER {self.nodeName}"
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
            message = f"CHECKREGISTER {self.nodeName}"
            clientSocket.send(message.encode())
            response = clientSocket.recv(1024)
            if response.startswith(b"NEWREGISTER"):
                data = pickle.loads(response[len(b"NEWREGISTER"):])
                self.neighbors = data
                for x in data:
                    if x not in self.neighbors:
                        if x in self.routingtable:
                           del self.routingtable[x]
            print(f"Eu sou {self.nodeName} os meus vizinhos são {self.neighbors}") 
            time.sleep(5)   

    def forward_message(self, message):
        for neighbor, ip in self.neighbors.items():
            if neighbor not in self.routingtable:
                print("O meu vizinho: ", neighbor)
                print("Vou enviar mensagem para -> ", ip)
                
                try:
                    # Criar o socket
                    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    
                    # Conectar ao vizinho (substitua `PORT` pela porta correta)
                    PORT = 12000  # Ajuste para a porta correta
                    clientSocket.connect((ip, PORT))
                    
                    # Enviar a mensagem
                    full_message = b"BUILDTREE" + pickle.dumps(message)
                    clientSocket.send(full_message)
                    print("Mensagem enviada com sucesso!")
                
                except socket.error as e:
                    print(f"Erro ao enviar mensagem para {ip}: {e}")
                
                finally:
                    # Fechar o socket após o uso
                    clientSocket.close()


    def receive_message(self, connectionSocket, addr):
        while True:
            try:
                # Ler a mensagem completa
                data = connectionSocket.recv(8192)

                # Processar a mensagem
                if data.startswith(b"HEARTBEAT"):
                    print("Recebi HeartBEAT")
                    connectionSocket.send(b"HEARTBEAT_ACK")
                    
                elif data.startswith(b"BUILDTREE"):
                    print("RECEBI O PINHEIRO")
                    try:
                        # Remover o prefixo e desserializar
                        message = pickle.loads(data[len(b"BUILDTREE"):])
                    except Exception as e:
                        print(f"Erro ao desserializar mensagem BUILDTREE: {e}")
                        continue

                    # Processar o conteúdo da mensagem
                    name_sender = message["name_sender"]
                    latencyacumulado, latencyenvio = message["latency"]
                    hops = message["hops"]
                    latencyacumulado += time.time() - latencyenvio

                    # Recebe  a mensagem, se nao houver entrada na routing 
                    # table o nodo/server que envia a mensagem, 
                    # coloca na routing table
                    
                    # Se houver, então substitui todos parametros, 
                    # da routing table, pelos parametros recebidos na nova mensagem

                    # Se algum vizinho morre, então a sua entrada deve ser 
                    # tambem retirada da routing table

                    # Atualizar tabela de roteamento
                    self.routingtable[name_sender] = (latencyacumulado, hops+1)

                    # Criar nova mensagem para encaminhamento
                    forward_message = {
                        "type": "BUILDTREE",
                        "name_sender": self.nodeName,
                        "latency": (latencyacumulado, latencyenvio),
                        "hops": hops+1
                    }
                    self.forward_message(forward_message)
                    print(self.routingtable)

            except Exception as e:
                print(f"Error receiving data from {addr}: {e}")
                break

    def send_message_with_ack(self, message,address,serverSocketUDP):
        serverSocketUDP.settimeout(self.retry_timeout)
        retries = 0
        while retries < self.max_retry:
            try:
                print("Vou enviar mensagem para -> ", address)
                serverSocketUDP.sendto(message, address)
                response, _ = serverSocketUDP.recvfrom(1024)
                print("Recebi a mensagem numero tentativas -> ", retries)
                return response
            except socket.timeout:
                retries += 1
                print(f"Timeout ao enviar mensagem para {address}. Tentativa {retries}/{self.max_retry}")
            except Exception as e:
                print(f"Erro ao enviar mensagem para {address}: {e}")
                retries += 1
        serverSocketUDP.close()
        print(f"Não foi possível enviar mensagem para {address}")
        return None

    def receive_client(self, serverSocketUDP):
        while True:
            try:
                print("RECEBI A MESSAGEM DO CLIENTE")
                message, client_address = serverSocketUDP.recvfrom(1024)
                if message.startswith(b"CHECK_LATENCY"):
                    modified_message = b"LATENCYCHECK"
                    self.send_message_with_ack(modified_message, client_address,serverSocketUDP)
            except Exception as e:
                print(f"Erro ao receber mensagem UDP: {e}")
            time.sleep(5)

    def start(self):
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSocket.bind(('0.0.0.0', self.port))
        serverSocket.listen(5)

        serverSocketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverSocketUDP.bind(('', self.port+1))

        # Registrar no bootstrap
        self.register_with_bootstrap()
        
        # Iniciar thread para atualizar vizinhos
        update_thread = threading.Thread(target=self.connection_bootstrap_handler)
        update_thread.start()

        update_thread2 = threading.Thread(target=self.receive_client,args = (serverSocketUDP,))
        update_thread2.start()

        # Aguardar mensagens
        while True:
            connectionSocket, addr = serverSocket.accept()
            threading.Thread(target=self.receive_message, args=(connectionSocket, addr)).start()

# Iniciar o n처
if __name__ == "__main__":
    nodeName = input("Nome do nó: ")
    node = Node(nodeName)
    node.start()
