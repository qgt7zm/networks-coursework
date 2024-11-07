import argparse
import socket
import struct


def get_args() -> tuple:
    parser = argparse.ArgumentParser()
    parser.add_argument('ip', type=str)  # host IP address
    parser.add_argument('port', type=int)  # host port
    args = parser.parse_args()
    return args.ip, args.port


if __name__ == '__main__':
    ip, port = get_args()
    print(f"Running webserver on http://{ip}:{port}")

    # Using IPv4 address
    # HTTP uses TCP streams
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    server_socket.bind((ip, port))
    server_socket.listen()
    connection, address = server_socket.accept()
    with connection:
        client_ip, client_port = address
        print(f"Received connection from {client_ip}:{client_port}")
    server_socket.close()
