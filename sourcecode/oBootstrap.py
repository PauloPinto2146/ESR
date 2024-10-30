import socket
import threading
import bootstrapfile
import time 

class BootstrapServer:
    def __init__(self, host='10.0.0.1', port=12000, bootstrap=bootstrapfile.bootstrap):
        self.host = host
        self.port = port
        self.vizinhos = bootstrap  # {Nomes: {Nomesvizinho: Ipligaçaovizinho}}
        self.nosconectados = {}  # {Nomes: {Ips para bootstrap: timestamp}}
        self.timestamp = 5

    def start(self):
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSocket.bind((self.host, self.port))
        serverSocket.listen(5)  
        print(f"Server is ready to receive at {self.port}")

        serverSocketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverSocketUDP.bind(('', self.port + 1))

        threading.Thread(target=self.monitor_time, daemon=True).start()  # Thread em modo daemon
        threading.Thread(target=self.receive_client,args = serverSocketUDP).start()
        
        while True:
            connectionSocket, addr = serverSocket.accept()
            print(f"Connection received from {addr}")
            threading.Thread(target=self.receive_cliente_message, args=(connectionSocket, addr)).start()

    def receive_client(self, serverSocketUDP):
        while True:
            try:
                message, clientAddress = serverSocketUDP.recvfrom(1024)
                if message.decode() == "FIND_POPS":  # Decodifica a mensagem antes da comparação
                    pops_ips = []
                    for x in bootstrapfile.pops:
                        if x in self.nosconectados:
                            pops_ips.append(bootstrapfile.pops[x])

                    # Envia a lista de IPs como string unida por espaços
                    pops_message = "FOUND_POPS " + " ".join(pops_ips)
                    serverSocketUDP.sendto(pops_message.encode(), clientAddress) 
            except UnicodeDecodeError as e:
                print(f"Erro ao decodificar a mensagem de {clientAddress}: {e}")
            except socket.error as e:
                print(f"Erro de socket ao comunicar com {clientAddress}: {e}")
            except Exception as e:
                print(f"Erro inesperado ao processar a mensagem de {clientAddress}: {e}")

    def receive_cliente_message(self, connectionSocket, addr):
        while True:
            try:
                sentence = connectionSocket.recv(1024).decode()
                if not sentence:
                    break
                protocol  = sentence.split(' ')[0]
                who_send_protocol = sentence.split(' ')[1]

                if protocol == 'REGISTER':
                    if who_send_protocol not in self.nosconectados:
                        self.nosconectados[who_send_protocol] = {}
                    # Registrar nó e atualizar timestamp
                    self.nosconectados[who_send_protocol][addr] = time.time()
                    vizinhos = self.check_vizinhos(who_send_protocol)
                    connectionSocket.send(f"NEIGHBORS {vizinhos}".encode())

                if protocol == 'CHECKREGISTER':
                    vizinhosligados = self.check_vizinhos_up(who_send_protocol)
                    connectionSocket.send(f"NEWREGISTER {vizinhosligados}".encode())
            except Exception as e:
                print(f"Error receiving data from {addr}: {e}")
                break
            
        connectionSocket.close()
        print(f"Connection with {addr} closed.")

    def check_vizinhos(self,who_send_protocol):
            vizinhos = ""
            for vizinho in self.vizinhos[who_send_protocol]:
                if vizinho in self.nosconectados:
                    vizinhos += self.vizinhos[who_send_protocol][vizinho] + " "
            return vizinhos
    
    def check_vizinhos_up(self,who_send_protocol):
        vizinho = ""
        for x in self.vizinhos[who_send_protocol]:
            if x in self.nosconectados:    
                vizinho += self.vizinhos[who_send_protocol][x] + " "
        return vizinho

    def monitor_time(self):
        while True:
            time.sleep(self.timestamp)
            for name in list(self.nosconectados.keys()):
                for addr in list(self.nosconectados[name].keys()):
                    if time.time() - self.nosconectados[name][addr] > self.timestamp:
                        try:
                            print("Enviando heartbeat")
                            # Envia um heartbeat para verificar a conexão
                            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            clientSocket.connect((addr[0], self.port)) 
                            clientSocket.send(f"HEARTBEAT {name}".encode())
                            print("Heartbeat enviado")
                            response = clientSocket.recv(1024).decode()
                            print("Recebi ACK")
                            if response == "HEARTBEAT_ACK":
                                self.nosconectados[name][addr] = time.time()
                            else:
                                del self.nosconectados[name][addr]
                                print(f"Connection with {addr} lost.")
                            clientSocket.close()
                        except Exception as e:
                            del self.nosconectados[name][addr]
                            print(f"Connection with {addr} lost: {e}")

# Iniciar o bootstrap
if __name__ == "__main__":
    bootstrap = BootstrapServer()
    bootstrap.start()
