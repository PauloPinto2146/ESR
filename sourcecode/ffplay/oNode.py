import socket
import threading
import sys
import subprocess


def handle_client(client_socket,client_address, server_address):
    try:
        print("Conectando ao servidor...\n")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect(server_address)

        def forward_stream(client_host, client_port, server_host, server_port):
            try:
                ffmpeg_command = [
                    "ffmpeg", "-re", "-i", f"udp://10.0.1.1:{server_port}?fifo_size=100000&overrun_nonfatal=1",
                    "-f", "mpegts", "-vsync", "0", 
                    "-flush_packets", "1", "-max_delay", "500000", 
                    "-buffer_size", "5000000", "-t", "50", f"udp://{client_host}:{client_port}"
                ]

                print(f"Conectado ao servidor: {server_host}:{server_port}")
                print(f"Conectado ao cliente: {client_host}:{client_port}")
                print("Redirecionando stream...")
                process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE)
                    
                while True:
                    data = server_socket.recv(4096).decode()
                    print("Recebi data: ",data)
                    if data:
                        print("Fim do fluxo de vídeo ou interrupção no ffmpeg.")
                        break
                    client_socket.sendall(data)

            except Exception as e:
                print(f"Erro ao redirecionar stream no oNode: {e}")
            finally:
                client_socket.close()
                print("Conexão com cliente encerrada.")

        # Iniciar o redirecionamento
        forward_stream(client_address[0], client_address[1], server_address[0], server_address[1])

    except Exception as e:
        print(f"Erro no node: {e}")
    finally:
        client_socket.close()
        server_socket.close()

def start_node(client_host='10.0.0.20', server_host='10.0.1.10', client_port=8080, server_port=8081):
    node_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Binding em: ('10.0.0.1', {client_port})")
    node_socket.bind(('10.0.0.1', client_port))
    node_socket.listen(5)

    while True:
        client_socket, client_address = node_socket.accept()
        print(f"Cliente conectado no node: {client_address}")
        threading.Thread(
            target=handle_client,
            args=(client_socket,(client_host,client_port), (server_host, server_port))
        ).start()

if __name__ == "__main__":
    client_port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server_port = int(sys.argv[2]) if len(sys.argv) > 1 else 8080
    start_node(client_port = client_port, server_port = server_port)
