import socket
import subprocess
import sys


def start_server(host='10.0.1.10', video_file='videoB.mp4'):
    port = int(sys.argv[1])
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Servidor iniciado em {host}:{port}")

    while True:
        node_socket, node_address = server_socket.accept()
        print(f"oNode conectado: {node_address}")
        try:
            ffmpeg_command = [
                    "ffmpeg", "-re", "-i", video_file, 
                    "-f", "mpegts", "-vsync", "0", 
                    "-flush_packets", "1", "-max_delay", "500000",
                    f"udp://{node_address[0]}:{port}"
                ]

            print(f"Estou a enviar o video para {node_address[0]}:{node_address[1]}\n")
            process = subprocess.Popen(
                ffmpeg_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE  # Captura erros do ffmpeg
            )

            # Log do stderr para diagnóstico
            while True:
                stderr_line = process.stderr.readline()
                if stderr_line:
                    print(f"FFmpeg STDERR: {stderr_line.decode('utf-8')}")
                else:
                    break

            # Envia os dados do ffmpeg para o node
            while True:
                data = process.stdout.read(4096)
                if not data:
                    print("Fim do fluxo de vídeo ou interrupção no ffmpeg.")
                    msg = "PAREI"
                    node_socket.send(msg.encode())
                    break

        except Exception as e:
            print(f"Erro durante o streaming: {e}")
        finally:
            node_socket.close()
            print("Conexão com node encerrada.")

if __name__ == "__main__":
    start_server()
