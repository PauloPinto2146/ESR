import socket
import threading
import bootstrapfile
import time 
import pickle

class BootstrapServer:
    def __init__(self, host='10.0.0.1', port=12000, bootstrap=bootstrapfile.bootstrap):
        self.host = host
        self.port = port
        self.vizinhos = bootstrap  # {Nomes: {Nomesvizinho: Ip ligaçaovizinho}}
        self.timestamp = 5

    def start(self):
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSocket.bind((self.host, self.port))
        serverSocket.listen(5)  
        print(f"Server is ready to receive at {self.port}")

        serverSocketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverSocketUDP.bind(('', self.port + 1))

        threading.Thread(target=self.receive_client, args=(serverSocketUDP,),daemon=True).start()

        while True:
            connectionSocket, addr = serverSocket.accept()
            print(f"Connection received from {addr}")
            threading.Thread(target=self.receive_cliente_message, args=(connectionSocket, addr)).start()

    def receive_client(self, serverSocketUDP):
        while True:
            dic = {}
            try:
                message, clientAddress = serverSocketUDP.recvfrom(1024)
                if message.decode() == "FIND_POPS": 
                    for x in bootstrapfile.pops:
                        dic[x] = (bootstrapfile.pops[x],bootstrapfile.udp_connection_ports,bootstrapfile.tcp_connection_ports)
                    pops_data = pickle.dumps(dic)
                    pops_message = b"FOUND_POPS " + pops_data
                    serverSocketUDP.sendto(pops_message, clientAddress)
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
                    data = pickle.dumps(bootstrapfile.bootstrap[who_send_protocol])
                    connectionSocket.send(b"NEIGHBORS" + data)
            except Exception as e:
                print(f"Error receiving data from {addr}: {e}")
                break
            
        connectionSocket.close()
        print(f"Connection with {addr} closed.")

if __name__ == "__main__":
    bootstrap = BootstrapServer()
    bootstrap.start()
