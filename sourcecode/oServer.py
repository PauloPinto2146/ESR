import socket
import pickle
import time
import threading
import subprocess

class StreamingServer:
    def __init__(self, serverName, port=12000, bootstrap_host='10.0.0.1', bootstrap_port=12000):
        self.serverName = serverName
        self.port = port
        self.bootstrap_host = bootstrap_host
        self.bootstrap_port = bootstrap_port
        self.neighbors = {} # Nome do No : IP
        self.routingtable = {}
        self.timestamp = 5
        self.videoslist =  {"canario": "Canario.mp4",
                            "movie": "movie.Mjpeg",}

    def register_with_bootstrap(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((self.bootstrap_host, self.bootstrap_port))
        message = f"REGISTER {self.serverName}"
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
            message = f"CHECKREGISTER {self.serverName}"
            clientSocket.send(message.encode())
            response = clientSocket.recv(1024)
            if response.startswith(b"NEWREGISTER"):
                data = pickle.loads(response[len(b"NEWREGISTER"):])
                self.neighbors = data
            print(f"Eu sou {self.serverName} os meus vizinhos são {self.neighbors}") 
            time.sleep(5)  

    def stream_to_socket(self,video_file, node_ip, node_port):
        """
        Streams a video to a node over a TCP socket in a separate thread.
        """
        def stream():
             with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
                try:
                    print(f"Connecting to {node_ip}:{node_port}...")
                    command = [
                                "ffmpeg", "-re", "-stream_loop", "-1", "-i", video_file,
                                "-preset", "ultrafast", "-f", "mpegts", "-c:v", "h264", "-b:v", "500k", 
                                "-maxrate", "1M", "-bufsize", "2M", "-c:a", "aac", "-flush_packets", "1",
                                "-max_delay", "5000", "-g", "15", "pipe:1"
                                ]
                    process = subprocess.Popen(command, stdout=subprocess.PIPE)
                    print(f"Streaming {video_file} to {node_ip}:{node_port}")
                    while chunk := process.stdout.read(4096):
                        server_socket.sendto(chunk, (node_ip, node_port))
                except Exception as e:
                    print(f"Error during streaming: {e}")
    
        threading.Thread(target=stream, daemon=True).start() 

    def receive_message(self, connectionSocket, addr):
        while True:
            try:
                sentence = connectionSocket.recv(1024)

                if not sentence:
                    break

                print("Recebi HeartBEAT")

                if sentence.startswith(b"HEARTBEAT"):
                    connectionSocket.send(b"HEARTBEAT_ACK")

                elif sentence.startswith(b"REQUESTVIDEO"):
                    sentence = sentence.decode("utf-8")
                    message = sentence.split(" ")
                    video_name = message[1]
                    node_ip = message[2]
                    streaming_port = message[3]
                    node = (node_ip, streaming_port)
                    print(f"Received video request for '{video_name}' from {node_ip}:{streaming_port}")
                    if video_name in self.videoslist:
                        print("Video Found")
                        video_file = self.videoslist[video_name]
                        streaming_port = int(streaming_port)
                        node_ip = self.neighbors[node_ip]
                        self.stream_to_socket(video_file, node_ip, streaming_port)

                    else:
                        print("VIDEO NOT FOUND")

                    print(f"Requested video '{video_name}' from {node_ip}:{streaming_port}")
            except Exception as e:
                print(f"Error receiving data from {addr}: {e}")
                break


    def create_control_message(self):
        message = {
            "type": "BUILDTREE",
            "name_sender": self.serverName,
            "latency": (0,time.time()), ## TEMPO ACUMULADO, TEMPO DE ENVIO
            "hops" : 0
        }
        return message
    
    def send_control_message(self):
        message = self.create_control_message()
        for neighbor in self.neighbors:
            ip = self.neighbors[neighbor]
            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                clientSocket.connect((ip, self.port))
                # Serializar e construir a mensagem
                serialized_message = pickle.dumps(message)
                prefixed_message = b"BUILDTREE" + serialized_message

                # Enviar tamanho da mensagem primeiro
                clientSocket.sendall(prefixed_message)  # Enviar a mensagem
            finally:
                clientSocket.close()

    def periodic_send_control_message(self):
        while True:
            print("Vou Construir a árvore")
            self.send_control_message()
            time.sleep(self.timestamp)


    def start(self):
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSocket.bind(('0.0.0.0', self.port))
        serverSocket.listen(5)

        # Registrar no bootstrap
        self.register_with_bootstrap()
        
        # Iniciar thread para atualizar vizinhos
        update_thread = threading.Thread(target=self.connection_bootstrap_handler)
        update_thread.start()    

        build_thread = threading.Thread(target=self.periodic_send_control_message)
        build_thread.start() 

        # Aguardar mensagens
        while True:
            connectionSocket, addr = serverSocket.accept()
            threading.Thread(target=self.receive_message, args=(connectionSocket, addr)).start()

# Iniciar o Server
if __name__ == "__main__":
    serverName = input("Nome do Server: ")
    Server = StreamingServer(serverName)
    Server.start()
