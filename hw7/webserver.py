import argparse
import socket
import sys



def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('ip', type=str)  # host IP address
    parser.add_argument('port', type=int)  # host port
    parser.add_argument('--request', action='store_true')  # sample request
    return parser.parse_args()


def process_request(request: bytes) -> dict:
    request_str = request.decode('utf-8')
    request_lines = request_str.split('\r\n')

    # Parse header
    request_header = request_lines[0].split(' ')
    request_method = request_header[0]
    request_path = request_header[1]

    response = {}

    if request_method == 'GET':
        print("using GET")
        print("path = " + request_path)
        # return 200 OK, 301 redirect, 404 or not found
    elif request_method == 'HEAD':
        print("using HEAD")
        print("path = " + request_path)
    else:
        print(f"invalid method: {request_method}")
        response['code'] = 405  # method not allowed

    return response


if __name__ == '__main__':
    args = get_args()
    if args.request:
        print("Parsing sample request")
        client_request = sys.stdin.buffer.read()
        process_request(client_request)
        exit(0)

    ip, port = args.ip, args.port
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
