import socket
import threading
import time
import pickle
import signal
import sys

# Nó cliente/servidor
class Node:
    def __init__(self, nodeName, port=12000, bootstrap_host='10.0.0.1', bootstrap_port=12000,streaming_port = 20000):
        self.nodeName = nodeName
        self.port = port
        self.bootstrap_host = bootstrap_host
        self.bootstrap_port = bootstrap_port
        self.neighbors = {} # Nome do No : IP
        self.retry_timeout = 10
        self.max_retry = 5
        self.videostreaming = {}
        self.streaming_port = streaming_port
        self.routingtable = {} # Dicionario  ->   nomedosender: (tempoacumalado,saltos)
        self.activeclients = {}
        self.clienttimeout = 15
        self.fixedNeighbors = {}
        self.running =  True

                
    def register_with_bootstrap(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((self.bootstrap_host, self.bootstrap_port))
        message = f"REGISTER {self.nodeName}"
        clientSocket.send(message.encode())
        response = clientSocket.recv(1024)
        if response.startswith(b"NEIGHBORS"):
            data = pickle.loads(response[len(b"NEIGHBORS"):])
            self.fixedNeighbors = data
            print(f"Vizinhos fixos -> {self.fixedNeighbors}")
        clientSocket.close()

    def connection_bootstrap_handler(self):
        while True:
            time.sleep(5)
            for x in self.fixedNeighbors:
                ip = self.fixedNeighbors[x]
                try:
                    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    clientSocket.connect((ip, self.port)) 
                    clientSocket.send(f"HEARTBEAT {self.nodeName}".encode())
                    response = clientSocket.recv(1024).decode()
                    if response == "HEARTBEAT_ACK":
                        self.neighbors[x] = ip
                        print(f"Este é o meu self.neighbors: {self.neighbors}")
                    else:
                        if x in self.neighbors:
                            del self.neighbors[x]
                        if x in self.routingtable:
                            del self.routingtable[x]
                            print(f"Connection with {x} lost.")
                            clientSocket.close()
                        else:
                            print("Não eliminei nada do dicionario")
                except Exception as e:
                    if x in self.neighbors:
                        del self.neighbors[x]
                    if x in self.routingtable:
                        del self.routingtable[x]
                        print(self.neighbors)
                        print(f"Connection with {x} lost: {e}")
                    else:
                        print("Não eliminei nada do dicionario")

    def forward_message(self, message):
        for neighbor, ip in self.neighbors.items():
            if neighbor not in self.routingtable:
                #print("O meu vizinho: ", neighbor)
                #print("Vou enviar mensagem para -> ", ip)
                try:
                    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    PORT = 12000 
                    clientSocket.connect((ip, PORT))
                    full_message = b"BUILDTREE" + pickle.dumps(message)
                    clientSocket.send(full_message)
                    print("Mensagem enviada com sucesso!")
                except socket.error as e:
                    print(f"Erro ao enviar mensagem para {ip}: {e}")
                finally:
                    clientSocket.close()


    def relay_stream(self, node_port, video_name):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind(("", node_port))
            print(f"oNode listening for server stream on UDP port {node_port} for video '{video_name}'...")
            print(f"Thread ID: {threading.get_ident()} - Start relaying stream for video '{video_name}' on port {node_port}")

            while len(self.videostreaming[video_name]["clients"]) >= 1:
                try:
                    data, _ = server_socket.recvfrom(2048)
                    if not data:
                        break
                    clients = list(self.videostreaming[video_name]["clients"])
                    for client in clients:
                        try:
                            server_socket.sendto(data, client)
                        except Exception as e:
                            print(f"Error sending data to client {client}: {e}")
                except Exception as e:
                    print(f"Error relaying stream for video '{video_name}': {e}")
                    break
            print("A stream parou neste NO")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.connect((self.neighbors[self.videostreaming[video_name]["best_node"]], self.port))
                message = b"STOPSTREAMING " + video_name.encode("utf-8") + b" " + self.nodeName.encode("utf-8")
                server_socket.send(message)
                server_socket.close()
            del self.videostreaming[video_name]
            print(self.videostreaming)



    def receive_message(self, connectionSocket, addr):
        while True:
            try:
                data = connectionSocket.recv(8192)
                if data.startswith(b"HEARTBEAT"):
                    #print("Recebi HeartBEAT")
                    connectionSocket.send(b"HEARTBEAT_ACK")

                if data.startswith(b"CLIENTBEAT"):
                    data = data.decode("utf-8")
                    client = data.split(" ")[1]
                    self.activeclients[client] = time.time()

                elif data.startswith(b"REQUESTVIDEOTOPOP"):
                    print("RECIEVED REQUEST TO POP")
                    data = data.decode("utf-8")
                    parts = data.split(" ")
                    video_name = parts[1]
                    client_ip = parts[2]
                    client_port = parts[3]
                    client_port = int(client_port)
                    client = (client_ip, client_port)
                    print("IP DO CLIENTE -> ", client_ip)

                    if video_name not in self.videostreaming:
                        self.streaming_port += 1
                        print(f"Requesting video '{video_name}' from oNode/Server.")
                        # Conectar a um destino (exemplo: primeiro nó)
                        best_nodes = self.check_tree()
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                            # Conectar ao primeiro nó
                            server_socket.connect((self.neighbors[best_nodes[0]], self.port))
                            message = b"NEEDVIDEO " + video_name.encode("utf-8") + b" " + self.nodeName.encode("utf-8") + b" " + str(self.streaming_port).encode("utf-8")
                            server_socket.send(message) 
                            server_socket.close()
                            print(f"Mensagem enviada para {self.neighbors[best_nodes[0]]}. Desconectado.")

                        self.videostreaming[video_name] = {
                            "clients": {client},
                            "thread": threading.Thread( target=self.relay_stream, args=(self.streaming_port, video_name), daemon=True),
                            "best_node": best_nodes[0]
                        }
                        self.videostreaming[video_name]["thread"].start()
                        print(f"Tabela de streaming -> {self.videostreaming}")
                    else:
                        self.videostreaming[video_name]["clients"].add(client)

                elif data.startswith(b"NEEDVIDEO"):
                    data = data.decode("utf-8")
                    message = data.split(" ")
                    video_name = message[1]
                    node_ip = message[2]
                    node_ip = self.neighbors[node_ip]
                    streaming_port = int(message[3])
                    node = (node_ip, streaming_port)
                    print(f"Received video request for '{video_name}' from {node_ip}:{streaming_port}")
                    if video_name not in self.videostreaming:
                        print(f"Requesting video '{video_name}' from oNode/Server.")
                        best_nodes = self.check_tree()
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                            server_socket.connect((self.neighbors[best_nodes[0]], self.port))
                            message = b"NEEDVIDEO" + b" " + video_name.encode("utf-8") + b" " + self.nodeName.encode("utf-8") + b" " + str(streaming_port).encode("utf-8")
                            server_socket.send(message) 
                            server_socket.close()

                        self.videostreaming[video_name] = {
                            "clients": {node},
                            "thread": threading.Thread(
                            target=self.relay_stream, args=(streaming_port,video_name), daemon=True
                            ),
                            "best_node": best_nodes[0]
                        }
                        self.videostreaming[video_name]["thread"].start()
                    else:
                        self.videostreaming[video_name]["clients"].add(node)

                    print(f"Requested video '{video_name}' from {node_ip}:{streaming_port}")

                elif data.startswith(b"BUILDTREE"):
                    try:
                        message = pickle.loads(data[len(b"BUILDTREE"):])
                    except Exception as e:
                        print(f"Erro ao desserializar mensagem BUILDTREE: {e}")
                        continue
                    name_sender = message["name_sender"]
                    latencyacumulado, latencyenvio = message["latency"]
                    hops = message["hops"]
                    latencyacumulado += time.time() - latencyenvio

                    self.routingtable[name_sender] = (latencyacumulado, hops+1)

                    message = {
                        "type": "BUILDTREE",
                        "name_sender": self.nodeName,
                        "latency": (latencyacumulado, latencyenvio),
                        "hops": hops+1
                    }
                    time.sleep(5)
                    self.forward_message(message)
                    print(self.routingtable)

                elif data.startswith(b"STOPSTREAMING"):
                    data = data.decode("utf-8")
                    data = data.split(" ")
                    video_name = data[1]
                    sender = data[2]
     
                    print(f"Stopping streaming for video '{video_name}'")
                    print(f"Sender -> {sender}")
                    print(f"Streaming Table -> {self.videostreaming}")


                    clients_to_remove = [client_streaming for client_streaming in self.videostreaming[video_name]["clients"]
                                        if client_streaming[0] == self.neighbors[sender]]
                    for client in clients_to_remove:
                        self.videostreaming[video_name]["clients"].remove(client)
                        print(f"Cliente {client} removido da lista de streaming")

                    print("TABELA DE STREAMING -> ", self.videostreaming)

            except Exception as e:
                print(f"Error receiving data from {addr}: {e}")
                break



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


    def send_message_with_ack(self, message,address,serverSocketUDP):
            serverSocketUDP.settimeout(self.retry_timeout)
            retries = 0
            while retries < self.max_retry:
                try:
                    serverSocketUDP.sendto(message, address)
                    response, _ = serverSocketUDP.recvfrom(1024)
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

    def monitorClients(self):
        while True:
            for client in list(self.activeclients): 
                print(f"Cliente {client} ativo")
                if time.time() - self.activeclients[client] > self.clienttimeout:
                    print(f"TABELA DE STREAMING -> {self.videostreaming}")
                    for video in list(self.videostreaming):
                        for client_streaming in list(self.videostreaming[video]["clients"]):
                            if client_streaming[0] == client:
                                self.videostreaming[video]["clients"].remove(client_streaming)
                                print(f"Cliente {client} removido da lista de streaming")
                    del self.activeclients[client]
                    print(f"Cliente {client} desconectado")
                    print(f"Streaming Table -> {self.videostreaming}")
            time.sleep(5)


    def receive_client(self, serverSocketUDP):
        while True:
            try:
                message, client_address = serverSocketUDP.recvfrom(1024)
                message_str = message.decode("utf-8")
                if message_str.startswith("CHECK_LATENCY"):
                    modified_message = b"LATENCYCHECK"
                    self.send_message_with_ack(modified_message, client_address, serverSocketUDP)
            except Exception as e:
                print(f"Erro ao receber mensagem UDP cliente: {e}")
            
    def shutdown(self,serverSocket,serverSocketUDP):
        print("\nShutting down node...")
        self.running = False
        if serverSocket:
            serverSocket.close()
        if serverSocketUDP:
            serverSocketUDP.close()
        sys.exit(0)


    def start(self):
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSocket.bind(('0.0.0.0', self.port))
        serverSocket.listen(5)

        serverSocketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverSocketUDP.bind(('', self.port+1))
        #serverSocketUDP.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 64)

        # Registrar no bootstrap
        self.register_with_bootstrap()
        
        # Iniciar thread para atualizar vizinhos
        update_thread = threading.Thread(target=self.connection_bootstrap_handler)
        update_thread.start()

        update_thread2 = threading.Thread(target=self.receive_client,args = (serverSocketUDP,))
        update_thread2.start()

        monitor_thread = threading.Thread(target=self.monitorClients)
        monitor_thread.start()

        signal.signal(signal.SIGINT, lambda signum, frame: self.shutdown(serverSocket, serverSocketUDP))

        # Aguardar mensagens
        while self.running:
            connectionSocket, addr = serverSocket.accept()
            threading.Thread(target=self.receive_message, args=(connectionSocket, addr)).start()


# Iniciar o n처
if __name__ == "__main__":
    nodeName = input("Nome do nó: ")
    if "PP" in nodeName:
         streaming_port = input("Digite a streaming port: ")
         node = Node(nodeName,streaming_port=streaming_port)
    node = Node(nodeName)
    node.start()
