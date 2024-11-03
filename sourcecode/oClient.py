import socket
import threading
import time
import supportClient 

class oClient:
    def __init__(self, server_address = supportClient.server, server_port = supportClient.port):
        self.server_address = server_address
        self.server_port = server_port
        self.pops = []  # Lista de IP's de Points of Presence
        self.best_pop = None
        self.timestamp = 5

    def discover_pops(self):
        while True:
            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   
            print("Vou descobrir os Pops") 
            message = "FIND_POPS"
            clientSocket.sendto(message.encode(), (self.server_address, self.server_port))
            
            response, _ = clientSocket.recvfrom(1024)
            response = response.decode('utf-8')
            if "FOUND_POPS" in response:
                listapops = response.split()[1:]
                if listapops == []:
                    self.pops = []
                    print("TOU SEM POP")
                self.pops = [(pop.split(":")[0], 12001) for pop in listapops]
            print(self.pops)
            clientSocket.close()
            print(f"PoPs disponíveis: {self.pops}")
            time.sleep(self.timestamp)

    def monitoring(self):
        while True:
            best_latency = float('inf')
            current_best_pop = None
            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print("Os meus pops são: ",self.pops)
            if self.pops == []:
                self.best_pop = None
                print("Nenhum PoP disponível.")
            else:
                for pop in self.pops:
                    try:
                        # Medir latência para cada PoP
                        time_send = time.time()
                        message = "CHECK_LATENCY"
                        print(f"Vou Enviar Mensagem para {pop}")
                        clientSocket.sendto(message.encode(), (pop[0],12001))

                        receive_message, _ = clientSocket.recvfrom(1024)
                        receive_message = receive_message.decode('utf-8')

                        # Calcula a latência
                        if "LATENCYCHECK" in receive_message:  # Verifique a resposta correta
                            latency = time.time() - time_send
                            if latency < best_latency:
                                best_latency = latency
                                current_best_pop = pop

                    except socket.timeout:
                        print(f"Timeout ao verificar latência para o PoP {pop}")
                        continue
                    except Exception as e:
                        print(f"Erro ao comunicar com o PoP {pop}: {e}")

                # Atualiza o melhor PoP
                self.best_pop = current_best_pop
                if self.best_pop is not None:
                    print(f"Melhor PoP: {self.best_pop} com latência de {best_latency:.2f} ms")
                else:
                    print("Nenhum PoP respondeu.")
                
            time.sleep(self.timestamp)  # Intervalo de monitoramento


    def start(self):
        discover_thread = threading.Thread(target=self.discover_pops)
        discover_thread.start()

        update_thread = threading.Thread(target=self.monitoring,daemon=True)
        update_thread.start()

        

# Configuração inicial
if __name__ == "__main__":
    client = oClient()
    client.start()