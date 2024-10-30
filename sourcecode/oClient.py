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

    def discover_pops(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    
        # Enviar solicitação de descoberta ao servidor
        clientSocket.sendto(b"FIND_POPS", (self.server_address, self.server_port))
        response, _ = clientSocket.recvfrom(1024)
        if "FOUND_POPS" in response:
            ip_pop = response.split()[1:]
            self.pops = ip_pop
        clientSocket.close()
        print(f"PoPs disponíveis: {self.pops}")

    def monitoring(self):
         while True:
            best_latency = float('inf')
            current_best_pop = None
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for pop in self.pops:
                try:
                    # Medir latência para cada PoP
                    time_send = time.time()
                    client_socket.sendto("CHECK_LATENCY", pop)
                    receive_message, _ = client_socket.recvfrom(1024)
                    
                    # Calcula a latência
                    if receive_message == "LATENCY_CHECK":
                        latency = time.time() - time_send
                        if latency < best_latency:
                            best_latency = latency
                            current_best_pop = pop

                except socket.timeout:
                    print(f"Timeout ao verificar latência para o PoP {pop}")
                    continue

            # Atualiza o melhor PoP
            self.best_pop = current_best_pop
            print(f"Melhor PoP: {self.best_pop} com latência de {best_latency:.2f} ms")
            time.sleep(5)  # Intervalo de monitoramento

    def start(self):
        # Inicializa o cliente, descobre os PoPs e seleciona o melhor
        self.discover_pops()

        update_thread = threading.Thread(target=self.monitoring(self))
        update_thread.start()

        while True:
            selected_pop = self.monitoring()
            if selected_pop:
                print(f"Conectado ao PoP mais conveniente: {selected_pop}")
            time.sleep(5)

# Configuração inicial
if __name__ == "__main__":
    client = oClient("10.0.0.1", 12000)
    client.start()
