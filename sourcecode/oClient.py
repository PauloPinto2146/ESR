import socket
import threading
import time
import supportClient 
import pickle

class oClient:
    def __init__(self, server_address=supportClient.server, server_port=supportClient.port, video_name=None, client_ip=None, client_port=None):
        self.server_address = server_address
        self.server_port = server_port
        self.pops = {}  # Nome do PoP: Lista de possíveis ligações
        self.best_pop = None  # (ip, porta)
        self.timestamp = 5
        self.max_retry = 5
        self.retry_timeout = 15
        self.threshold = 5
        self.status = "NotStreaming"
        self.video_name = video_name
        self.client_ip = client_ip
        self.client_port = client_port

    def discover_pops(self):
        while True:
            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            message = b"FIND_POPS"
            response = self.send_message_with_ack(message, (self.server_address, self.server_port))
            if response:
                if response.startswith(b"FOUND_POPS "):
                    # Separar a mensagem inicial da parte serializada
                    pops_data = response[len(b"FOUND_POPS "):]
                    
                    # Desserializar os dados
                    pops = pickle.loads(pops_data)
                    self.pops = pops
            print(f"PoPs disponíveis: {self.pops}")
            clientSocket.close()
            time.sleep(self.timestamp)

    def send_message_with_ack(self, message, address):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        clientSocket.settimeout(self.retry_timeout)
        retries = 0
        while retries < self.max_retry:
            try:
                print("Vou enviar mensagem para -> ", address)
                clientSocket.sendto(message, address)
                response, _ = clientSocket.recvfrom(1024)
                return response
            except socket.timeout:
                retries += 1
                print(f"Timeout ao enviar mensagem para {address}. Tentativa {retries}/{self.max_retry}")
            except Exception as e:
                print(f"Erro ao enviar mensagem para {address}: {e}")
                retries += 1
        clientSocket.close()
        print(f"Não foi possível enviar mensagem para {address}")
        return None

    def monitoring(self):
        while True:
            best_latency = float('inf')
            current_best_pop = None
            if self.pops == {}:
                self.best_pop = None
                print("Nenhum PoP disponível.")
            else:
                for pop in self.pops:
                    for ipspos in self.pops[pop][0]:
                        try:
                            port = self.pops[pop][1]
                            # Medir latência para cada PoP
                            time_send = time.time()
                            message = b"CHECK_LATENCY"
                            receive_message = self.send_message_with_ack(message, (ipspos, port))

                            if receive_message:
                                if receive_message.startswith(b"LATENCYCHECK"):
                                    latency = time.time() - time_send
                                    print(f"EU SOU {pop} e a minha latência é -> {latency}")
                                    if latency < best_latency:  # and best_latency - latency > self.threshold:
                                        best_latency = latency
                                        current_best_pop = pop
                        except socket.timeout:
                            print(f"Timeout ao verificar latência para o PoP {pop}")
                            continue
                        except Exception as e:
                            print(f"Erro ao comunicar com o PoP {pop}: {e}")

                # Atualiza o melhor PoP
                self.best_pop = (ipspos, port)
                if self.best_pop is not None:
                    print(f"Melhor PoP: {self.best_pop} com latência de {best_latency:.2f} ms")
                else:
                    print("Nenhum PoP respondeu.")
                
            time.sleep(self.timestamp)  # Intervalo de monitoramento

    def request_video(self, onode_ip, onode_port, video_name, client_ip, client_port):
        """
        Sends a video request to the oNode.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                message = b"REQUESTVIDEO " + video_name.encode("utf-8") + b" " + client_ip.encode("utf-8") + b" " + str(client_port).encode("utf-8")
                s.sendto(message, (onode_ip, onode_port))
                print(f"Requested video '{video_name}' from {onode_ip}:{onode_port}")
        except Exception as e:
            print(f"Error sending request to oNode: {e}")


    def start(self):
        discover_thread = threading.Thread(target=self.discover_pops)
        discover_thread.start()

        update_thread = threading.Thread(target=self.monitoring, daemon=True)
        update_thread.start()

        while self.status == "NotStreaming":
            if self.best_pop is None:
                print("Nenhum PoP disponível.")
            else:
                time.sleep(15)
                self.request_video(self.best_pop[0], self.best_pop[1], self.video_name, self.client_ip, self.client_port)
                self.status = "Streaming"

# Configuração inicial
if __name__ == "__main__":
    videoname = input("Digite o nome do vídeo: ")
    clientip = input("Digite o IP do cliente: ")
    clientport = int(input("Digite a porta do cliente: "))
    client = oClient(video_name=videoname, client_ip=clientip, client_port=clientport)
    client.start()
