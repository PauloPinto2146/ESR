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
                            "movie": "movie.Mjpeg",
                            "videoA": "videoA.mp4"}
        self.videostreaming = {} # Nome do video : processID
        self.fixedNeighbors = {}

    def register_with_bootstrap(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect((self.bootstrap_host, self.bootstrap_port))
        message = f"REGISTER {self.serverName}"
        clientSocket.send(message.encode())
        response = clientSocket.recv(1024)
        if response.startswith(b"NEIGHBORS"):
            data = pickle.loads(response[len(b"NEIGHBORS"):])
            self.fixedNeighbors = data
            print(self.neighbors)
        clientSocket.close()

    def connection_bootstrap_handler(self):
        while True:
            time.sleep(self.timestamp)
            for x in self.fixedNeighbors:
                ip = self.fixedNeighbors[x]
                try:
                    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    clientSocket.connect((ip, self.port)) 
                    clientSocket.send(f"HEARTBEAT {self.serverName}".encode())
                    response = clientSocket.recv(1024).decode()
                    if response == "HEARTBEAT_ACK":
                        self.neighbors[x] = ip
                        print(f"Este é o meu self.neighbors: {self.neighbors}")
                    else:
                        if x in self.neighbors:
                            del self.neighbors[x]
                            clientSocket.close()
                        else:
                            print("Não eliminei nada do dicionario")
                except Exception as e:
                    if x in self.neighbors:
                        del self.neighbors[x]
                        print(self.neighbors)
                    else:
                        print("Não eliminei nada do dicionario")

    def stream_to_socket(self,video_file, node_ip, node_port):
        def stream():
             with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
                try:
                    print(f"Connecting to {node_ip}:{node_port}...")
                    command = [
                                "ffmpeg", "-re", "-stream_loop", "-1", "-i", video_file,
                                "-preset", "ultrafast", "-f", "mpegts", "-c:v", "h264", "-b:v", "400k", 
                                "-maxrate", "500k", "-bufsize", "5M", "-c:a", "aac","-b:a", "64k", "-flush_packets", "1",
                                "-max_delay", "5000", "-g", "15", "pipe:1"
                                ]

                    process = subprocess.Popen(command, stdout=subprocess.PIPE)
                    self.videostreaming[video_file] = process.pid
                    print(f"Streaming {video_file} to {node_ip}:{node_port}")
                    while chunk := process.stdout.read(2048):
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

                elif sentence.startswith(b"NEEDVIDEO"):
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
                        print(f"Requested video '{video_name}' from {node_ip}:{streaming_port}")
                    else:
                        print("VIDEO NOT FOUND")
                elif sentence.startswith(b"STOPSTREAMING"):
                    sentence = sentence.decode("utf-8")
                    sentence = sentence.split(" ")
                    video_name = sentence[1]
                    sender = sentence[2]
                    print(f"Stopping streaming for video '{video_name}'")
                    print(f"Sender -> {sender}")
                    print(f"Streaming Table -> {self.videostreaming}")
                    if self.videoslist[video_name] in self.videostreaming:
                        video_name = self.videoslist[video_name]
                        print(f"Video Found", video_name)
                        process = self.videostreaming[video_name]
                        print(f"Killing process {process}")
                        print(f"videoStreaming, {self.videostreaming}")
                        subprocess.Popen(f"kill -9 {process}", shell=True)
                        del self.videostreaming[video_name]
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
                serialized_message = pickle.dumps(message)
                prefixed_message = b"BUILDTREE" + serialized_message

                clientSocket.sendall(prefixed_message)  
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

        self.register_with_bootstrap()

        update_thread = threading.Thread(target=self.connection_bootstrap_handler)
        update_thread.start()    

        build_thread = threading.Thread(target=self.periodic_send_control_message)
        build_thread.start() 

        while True:
            connectionSocket, addr = serverSocket.accept()
            threading.Thread(target=self.receive_message, args=(connectionSocket, addr)).start()


if __name__ == "__main__":
    serverName = input("Nome do Server: ")
    Server = StreamingServer(serverName)
    Server.start()
