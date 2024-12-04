import socket
import threading
import time
import supportClient
import pickle
import os
import subprocess
import tkinter as tk
from tkinter import messagebox

class oClient:
    def __init__(self, server_address=supportClient.server, server_port=supportClient.port, video_name=None, client_ip=None, client_port=None, pipe_name=None):
        self.server_address = server_address
        self.server_port = server_port
        self.pops = {}  # Nome do PoP: Lista de possíveis ligações
        self.best_pop = None  # (ip, porta)
        self.timestamp = 20
        self.max_retry = 5
        self.retry_timeout = 10
        self.threshold = 5
        self.status = "NotStreaming"
        self.video_name = video_name
        self.client_ip = client_ip
        self.client_port = client_port
        self.pipe_name = pipe_name
        self.BUFFER_SIZE = 2048  
        self.receveing_data = False
        self.results = []
        self.clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.clientSocket.settimeout(self.retry_timeout)

    def discover_pops(self):
        while True:
            message = b"FIND_POPS"
            response = self.send_message_with_ack(message, (self.server_address, self.server_port))
            if response:
                if response.startswith(b"FOUND_POPS "):
                    pops_data = response[len(b"FOUND_POPS "):]
                    pops = pickle.loads(pops_data)
                    self.pops = pops
            print(f"PoPs disponíveis: {self.pops}")
            time.sleep(self.timestamp)

    def send_message_with_ack(self, message, address):
        retries = 0
        while retries < self.max_retry:
            try:
                print("Vou enviar mensagem para -> ", address)
                self.clientSocket.sendto(message, address)
                response, _ = self.clientSocket.recvfrom(1024)
                return response
            except socket.timeout:
                retries += 1
                print(f"Timeout ao enviar mensagem para {address}. Tentativa {retries}/{self.max_retry}")
            except Exception as e:
                print(f"Erro ao enviar mensagem para {address}: {e}")
                retries += 1
        self.clientSocket.close()
        print(f"Não foi possível enviar mensagem para {address}")
        return None

    def check_latency_for_pop(self, pop, ipspos, port, port_request):
        try:
            time_send = time.time()
            message = b"CHECK_LATENCY"
            receive_message = self.send_message_with_ack(message, (ipspos, port))
            if receive_message and receive_message.startswith(b"LATENCYCHECK"):
                latency = time.time() - time_send
                print(f"PoP {pop} -> Latência: {latency}")
                self.results.append((latency, pop, ipspos, port, port_request))
        except socket.timeout:
            print(f"Timeout ao verificar latência para o PoP {pop}")
        except Exception as e:
            print(f"Erro ao comunicar com o PoP {pop}: {e}")

    def monitoring(self):
        while True:
            if not self.pops:
                self.best_pop = None
                print("Nenhum PoP disponível.")
                time.sleep(self.timestamp)
                continue
            self.results = []  
            threads = []
            for pop, pop_data in self.pops.items():
                for ipspos in pop_data[0]:
                    port = pop_data[1]
                    port_request = pop_data[2]
                    thread = threading.Thread(target=self.check_latency_for_pop, args=(pop, ipspos, port, port_request))
                    threads.append(thread)
                    thread.start()

            for thread in threads:
                thread.join() 

            best_latency = float('inf')
            current_best_pop = None
            best_pop_ip = None
            best_pop_port = None
            best_pop_port_request = None

            for latency, pop, ip, port, port_request in self.results:
                if latency < best_latency:
                    best_latency = latency
                    current_best_pop = pop
                    best_pop_ip = ip
                    best_pop_port = port
                    best_pop_port_request = port_request

            if current_best_pop:
                self.best_pop = (best_pop_ip, best_pop_port, best_pop_port_request)
                print("Vou Começar a enviar Heatbeat")
                print(f"Melhor PoP: {current_best_pop} com latência de {best_latency:.2f} ms")
            else:
                print("Nenhum PoP respondeu.")

            time.sleep(self.timestamp)

    def request_video(self, onode_ip, onode_port, video_name, client_ip, client_port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((onode_ip, onode_port))
                message = b"REQUESTVIDEOTOPOP " + video_name.encode("utf-8") + b" " + client_ip.encode("utf-8") + b" " + str(client_port).encode("utf-8")
                s.sendall(message)
                print(f"Requested video '{video_name}' from {onode_ip}:{onode_port}")
                time.sleep(5)
                while True:
                    print("Enviei Heartbeat")
                    message = b"CLIENTBEAT " + self.client_ip.encode("utf-8")
                    s.sendall(message)
                    print("Heartbeat enviado.")
                    time.sleep(3)
        except Exception as e:
            print(f"Error sending TCP request to oNode: {e}")

    def listen_to_stream(self, client_port):
        try:
            if not os.path.exists(self.pipe_name):
                print(f"Erro: Não foi possível criar o FIFO {self.pipe_name}")
                return
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                try:
                    s.bind(("", client_port))
                    print(f"Escutando na porta {client_port}...")
                except Exception as e:
                    print(f"Erro ao tentar associar o socket à porta {client_port}: {e}")
                    return
                print("Socket criado e associado à porta com sucesso.")
                try:
                    with open(self.pipe_name, "wb") as pipe:
                        print("FIFO aberto para escrita.")
                        while True:
                            self.receveing_data = True
                            data, addr = s.recvfrom(self.BUFFER_SIZE)
                            if data:
                                pipe.write(data) 
                            else:
                                print("Pacote vazio recebido, interrompendo o listener.")
                                break
                except Exception as e:
                    print(f"Erro ao tentar abrir o FIFO ou escrever: {e}")
        except Exception as e:
            print(f"Erro na função listen_to_stream: {e}")

    def play_stream(self, pipe_name):
        try:
            print("Starting ffplay to play the stream...")
            command = [
                "ffplay",
                "-f", "mpegts",
                "-i", pipe_name,
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-ac", "2",
                "-ar", "44100",
                "-analyzeduration", "0",
                "-probesize", "32",
                "-sync", "video",
            ]
            subprocess.Popen(command)
        except Exception as e:
            print(f"Error starting ffplay: {e}")

    def start(self):
        discover_thread = threading.Thread(target=self.discover_pops)
        discover_thread.start()

        time.sleep(2)

        update_thread = threading.Thread(target=self.monitoring, daemon=True)
        update_thread.start()

        while self.best_pop is None:
            print("Nenhum PoP disponível.")
            time.sleep(5)

        ip = self.best_pop[0]
        request_port = self.best_pop[2]

        time.sleep(10)
        requesting_thread = threading.Thread(target=self.request_video, args=(ip, request_port, self.video_name, self.client_ip, self.client_port), daemon=True)
        requesting_thread.start()
        self.status = "Streaming"

        listener_thread = threading.Thread(target=self.listen_to_stream, args=(self.client_port,), daemon=True)
        listener_thread.start()

        print("Reproduzindo o vídeo...")
        self.play_stream(self.pipe_name)

        listener_thread.join()  
        if os.path.exists(self.pipe_name):
            os.remove(self.pipe_name)

if __name__ == "__main__":
    def start_gui():
        root = tk.Tk()
        root.title("oClient GUI")

        tk.Label(root, text="Nome do Vídeo").grid(row=0, column=0, padx=5, pady=5)
        tk.Label(root, text="IP do Cliente").grid(row=1, column=0, padx=5, pady=5)
        tk.Label(root, text="Porta do Cliente").grid(row=2, column=0, padx=5, pady=5)
        tk.Label(root, text="Nome do Pipe").grid(row=3, column=0, padx=5, pady=5)

        video_entry = tk.Entry(root)
        client_ip_entry = tk.Entry(root)
        client_port_entry = tk.Entry(root)
        pipe_name_entry = tk.Entry(root)
        
        video_entry.grid(row=0, column=1, padx=5, pady=5)
        client_ip_entry.grid(row=1, column=1, padx=5, pady=5)
        client_port_entry.grid(row=2, column=1, padx=5, pady=5)
        pipe_name_entry.grid(row=3, column=1, padx=5, pady=5)
        
        def start_client():
            video_name = video_entry.get()
            client_ip = client_ip_entry.get()
            client_port = int(client_port_entry.get())
            pipe_name = pipe_name_entry.get()

            if not all([video_name, client_ip, client_port, pipe_name]):
                messagebox.showerror("Erro", "Todos os campos devem ser preenchidos!")
                return
            
            if not os.path.exists(pipe_name):
                os.mkfifo(pipe_name)
            
            client = oClient(
                video_name=video_name,
                client_ip=client_ip,
                client_port=client_port,
                pipe_name=pipe_name
            )
            threading.Thread(target=client.start, daemon=True).start()
            
            video_entry.config(state="disabled")
            client_ip_entry.config(state="disabled")
            client_port_entry.config(state="disabled")
            pipe_name_entry.config(state="disabled")
            start_button.config(state="disabled")
            
            messagebox.showinfo("Iniciado", "oClient iniciado com sucesso! Stream começará em breve")
        
        start_button = tk.Button(root, text="Iniciar oClient", command=start_client)
        start_button.grid(row=4, column=0, columnspan=2, pady=10)
        
        root.mainloop()

    start_gui()
