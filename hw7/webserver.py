import argparse
import socket
import struct


def get_args() -> tuple:
    parser = argparse.ArgumentParser()
    parser.add_argument('ip', type=str)  # host IP address
    parser.add_argument('port', type=int)  # host port
    args = parser.parse_args()
    return args.ip, args.port


def process_request(request: bytes) -> dict:
    print(request)
    request_op = request[:request.find(b' ')].decode('utf-8')

    if request_op == 'GET':
        print("using GET")
        # return 200 OK, 301 redirect, 404 or not found
    elif request_op == 'HEAD':
        print("using HEAD")
    else:
        # return 405 method not allowed
        print("invalid op")

    return {}


if __name__ == '__main__':
    ip, port = get_args()
    print(f"Running webserver on http://{ip}:{port}")

    # Using IPv4 address
    # HTTP uses TCP streams
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((ip, port))
    server_socket.listen()
    connection, address = server_socket.accept()
    with connection:
        client_ip, client_port = address
        print(f"Received connection from {client_ip}:{client_port}")

        client_request = connection.recv(1000)
        process_request(client_request)
    server_socket.close()
