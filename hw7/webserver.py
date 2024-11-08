import argparse
import datetime
import socket
import sys

from pathlib import Path

RESPONSE_CODES = {
    200: 'OK',
    301: 'Moved Permanently',
    404: 'Not Found',
    405 : 'Method Not Allowed'
}

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('ip', type=str)  # host IP address
    parser.add_argument('port', type=int)  # host port
    parser.add_argument('--request', action='store_true')  # sample request
    return parser.parse_args()


def is_path_valid(request_path) -> bool:
    path = Path('webroot' + request_path)
    return path.is_file()


def get_response_code(method: str, path: str) -> int:
    if method == 'GET' or method == 'HEAD':
        print("method: " + method)

        if is_path_valid(path):
            if 'redirect' in path:
                print(f"redirect: {path}")
                return 301  # moved permanently
            else:
                print(f"OK: {path}")
                return 200  # OK
        else:
            print(f"not found: {path}")
            return 404  # not found
    else:
        print(f"invalid method: {method}")
        return 405  # method not allowed


def process_request(request: bytes) -> dict:
    request_str = request.decode('utf-8')
    request_lines = request_str.split('\r\n')

    # Get response code from header
    request_header = request_lines[0].split(' ')
    response_code = get_response_code(request_header[0], request_header[1])

    response_data = {
        'code': response_code
    }

    if response_code == 200:
        # TODO get file type
        pass
    elif response_code == 301:
        # TODO find redirect target
        pass
    elif response_code == 404:
        pass
    elif response_code == 504:
        pass

    return response_data


def create_response(response_data: dict) -> bytes:
    code = response_data['code']
    date = datetime.datetime.now()
    date_fmt = date.strftime("%a, %d %b %Y %H:%M:%S %Z")

    response_lines = [
        f"HTTP/1.1 {code} {RESPONSE_CODES[code]}",
        f"Date: {date_fmt}",
        f"Server: Python",
        f"Content-Length: 0",
        f"Content-Type: text/html; charset=UTF-8",
        "",
        "",
    ]
    response = '\r\n'.join(response_lines)
    print(response)
    return bytes(response, 'utf-8')


if __name__ == '__main__':
    args = get_args()
    if args.request:
        print("Parsing sample request")
        client_request = sys.stdin.buffer.read()
        response_data = process_request(client_request)
        server_response = create_response(response_data)
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
