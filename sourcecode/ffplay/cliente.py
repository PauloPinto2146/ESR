import socket
import subprocess
import sys

def start_client(node_host='10.0.0.1'):
    node_port = int(sys.argv[1])
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((node_host, node_port))
    print(f"Conectei me ao nodo (node_host, port) = ({node_host},{node_port})")

    try:
        ffplay_command = [
                "ffplay", "-f", "mpegts", f"udp://{node_host}:{node_port}"
            ]
        process = subprocess.Popen(ffplay_command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        while True:
            stderr_line = process.stderr.readline()
            if stderr_line:
                print(f"FFplay STDERR: {stderr_line.decode('utf-8')}")
            else:
                break
            process.wait()
    except Exception as e:
        print(f"Erro ao executar o ffplay: {e}")
    finally:
        client_socket.close()
        print("Conexão com node encerrada.")

if __name__ == "__main__":
    start_client()
