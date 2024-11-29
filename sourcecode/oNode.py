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
        self.videostreaming = {}
        self.streaming_port = 20000
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
           # print(self.neighbors)
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
           # print(f"Eu sou {self.nodeName} os meus vizinhos são {self.neighbors}") 
            print("Minha Streaming Table -> ", self.videostreaming)
            time.sleep(5)   

    def forward_message(self, message):
        for neighbor, ip in self.neighbors.items():
            if neighbor not in self.routingtable:
                #print("O meu vizinho: ", neighbor)
                #print("Vou enviar mensagem para -> ", ip)
                
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


    def relay_stream(self,node_port, video_name):
        """
        Relays a UDP stream from the server to all connected clients.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind(("", node_port))
            print(f"oNode listening for server stream on UDP port {node_port} for video '{video_name}'...")

            while True:
                try:
                    data , _ = server_socket.recvfrom(4096)
                    print("Recebi dados do servidor" , data)
                    if not data:
                        break
                    for client in self.videostreaming[video_name]["clients"]:
                        print("Vou enviar para -> ", client)
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
                            client_socket.sendto(data, client)
                except Exception as e:
                    print(f"Error relaying stream for video '{video_name}': {e}")
                    break

            del self.videostreaming[video_name]


    def receive_message(self, connectionSocket, addr):
        while True:
            try:
                # Ler a mensagem completa
                data = connectionSocket.recv(8192)

                # Processar a mensagem
                if data.startswith(b"HEARTBEAT"):
                    #print("Recebi HeartBEAT")
                    connectionSocket.send(b"HEARTBEAT_ACK")

                elif data.startswith(b"REQUESTVIDEO"):
                    data = data.decode("utf-8")
                    message = data.split(" ")
                    video_name = message[1]
                    node_ip = message[2]
                    node_ip = self.neighbors[node_ip]
                    #print("Node IP -> ", node_ip)
                    streaming_port = int(message[3])
                    #print("Streaming Port -> ", streaming_port)
                    node = (node_ip, streaming_port)
                    print(f"Received video request for '{video_name}' from {node_ip}:{streaming_port}")
                    if video_name not in self.videostreaming:
                        print(f"Requesting video '{video_name}' from oNode/Server.")
                        
                        # Conectar a um destino (exemplo: primeiro nó)
                        best_nodes = self.check_tree()
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                            # Conectar ao primeiro nó
                            server_socket.connect((self.neighbors[best_nodes[0]], self.port))
                            message = b"REQUESTVIDEO" + b" " + video_name.encode("utf-8") + b" " + self.nodeName.encode("utf-8") + b" " + str(self.streaming_port).encode("utf-8")
                            server_socket.send(message)  # Enviar a mensagem de solicitação

                            # Fechar o socket após enviar a mensagem
                            server_socket.close()

                        self.videostreaming[video_name] = {
                            "clients": {node},
                            "thread": threading.Thread(
                            target=self.relay_stream, args=(streaming_port,video_name), daemon=True
                            )
                        }
                        self.videostreaming[video_name]["thread"].start()
                    else:
                        self.videostreaming[video_name]["clients"].add(node)

                    print(f"Requested video '{video_name}' from {node_ip}:{streaming_port}")

                
                elif data.startswith(b"BUILDTREE"):
                    #print("RECEBI O PINHEIRO")
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

                    # Atualizar tabela de roteamento
                    self.routingtable[name_sender] = (latencyacumulado, hops+1)

                    # Criar nova mensagem para encaminhamento
                    forward_message = {
                        "type": "BUILDTREE",
                        "name_sender": self.nodeName,
                        "latency": (latencyacumulado, latencyenvio),
                        "hops": hops+1
                    }
                    time.sleep(5)
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
                #print("Vou enviar mensagem para -> ", address)
                serverSocketUDP.sendto(message, address)
                response, _ = serverSocketUDP.recvfrom(1024)
                #print("Recebi a mensagem numero tentativas -> ", retries)
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



    def check_tree(self):
        lista = []
        for x in self.routingtable:
            if lista == []:
                lista.append(x)
            if self.routingtable[x][0] < self.routingtable[lista[0]][0]:
                lista = [x] + lista
            elif self.routingtable[x][0] == self.routingtable[lista[0]][0] and self.routingtable[x][1] < self.routingtable[lista[0]][1]:
                lista = [x] + lista
            else:
                lista.append(x)
        return lista

    def receive_client(self, serverSocketUDP):
        while True:
            try:
                #print("RECEBI A MESSAGEM DO CLIENTE")
                message, client_address = serverSocketUDP.recvfrom(1024)
                message_str = message.decode("utf-8")
                #print("Mensagens clientes -> ", message_str)

                if message_str.startswith("CHECK_LATENCY"):
                    modified_message = b"LATENCYCHECK"
                    self.send_message_with_ack(modified_message, client_address, serverSocketUDP)

                elif message_str.startswith("REQUESTVIDEO"):
                    parts = message_str.split(' ')
                    video_name = parts[1]
                    client_ip = parts[2]
                    client_port = parts[3]
                    client_port = int(client_port)
                    client = (client_ip, client_port)

                    if video_name not in self.videostreaming:
                        print(f"Requesting video '{video_name}' from oNode/Server.")
                        
                        # Conectar a um destino (exemplo: primeiro nó)
                        best_nodes = self.check_tree()
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                            # Conectar ao primeiro nó
                            server_socket.connect((self.neighbors[best_nodes[0]], self.port))
                            message = b"REQUESTVIDEO " + video_name.encode("utf-8") + b" " + self.nodeName.encode("utf-8") + b" " + str(self.streaming_port).encode("utf-8")
                            server_socket.send(message)  # Enviar a mensagem de solicitação
                            # Fechar o socket após enviar a mensagem
                            server_socket.close()
                            print(f"Mensagem enviada para {self.neighbors[best_nodes[0]]}. Desconectado.")

                        self.videostreaming[video_name] = {
                            "clients": {client},
                            "thread": threading.Thread( target=self.relay_stream, args=(self.streaming_port, video_name), daemon=True)
                        }
                        self.videostreaming[video_name]["thread"].start()
                        self.streaming_port += 1
                    else:
                        self.videostreaming[video_name]["clients"].add(client)

                    print(f"Requested video '{video_name}' from {client_ip}:{client_port}")         
            except Exception as e:
                print(f"Erro ao receber mensagem UDP cliente: {e}")
            
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
