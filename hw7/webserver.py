import argparse
import datetime
import os
import socket
import sys

from pathlib import Path

RESPONSE_CODES = {
    200: 'OK',
    301: 'Moved Permanently',
    404: 'Not Found',
    405: 'Method Not Allowed'
}


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('ip', type=str)  # host IP address
    parser.add_argument('port', type=int)  # host port
    parser.add_argument('--request', action='store_true')  # sample request
    return parser.parse_args()


def get_response_code(method: str, path: str) -> int:
    if method == 'GET' or method == 'HEAD':
        print("Method: " + method)

        file_path = Path('webroot' + path)
        if file_path.is_file():
            if not os.access(file_path, os.R_OK):
                return 403  # not authorized
            elif 'redirect' in path:
                return 301  # moved permanently
            else:
                return 200  # OK
        else:
            return 404  # not found
    else:
        return 405  # method not allowed


def process_request(request: bytes) -> dict:
    request_str = request.decode('utf-8')
    request_lines = request_str.split('\r\n')

    # Parse the header
    request_header = request_lines[0].split(' ')
    request_method = request_header[0]
    request_path = request_header[1]

    # Get the response code
    response_code = get_response_code(request_method, request_path)

    response_data = {
        'code': response_code
    }

    # Create the response parameters
    if response_code == 200:
        if request_method == 'GET':
            # Get the file type
            file_ext = request_path[request_path.find('.') + 1:]
            if file_ext == 'html' or file_ext == 'htm':
                response_data['type'] = 'text/html'
            else:
                response_data['type'] = 'text/plain'

            # Read the file
            file_path = Path('webroot' + request_path)
            with open(file_path, 'r') as file:
                contents = file.read()
                response_data['body'] = contents
                response_data['length'] = len(contents)
        else:
            response_data['body'] = None
    elif response_code == 301:
        # Get the redirect target
        response_data['body'] = f"Redirect: {request_path}"
        response_data['location'] = "/redirect-target.html"
        pass
    elif response_code == 404:
        response_data['body'] = f"File not found: {request_path}"
    elif response_code == 405:
        response_data['body'] = f"Unsupported method: {request_method}"

    return response_data


def create_response(response_data: dict) -> bytes:
    code = response_data['code']
    date = datetime.datetime.now()
    date_fmt = date.strftime("%a, %d %b %Y %H:%M:%S %Z")

    response_lines = [
        f"HTTP/1.1 {code} {RESPONSE_CODES[code]}",
        f"Date: {date_fmt}",
        f"Server: Python",
        # f"Last Modified: {date_fmt}",
        # "Connection: Keep-Alive",
    ]

    # Check for redirect target
    if 'location' in response_data:
        response_lines.append(f"Location: {response_data['location']}")

    # Check for message body
    if response_data['body'] is not None:
        # Check for file contents
        if 'length' in response_data:
            response_lines.append(f"Content-Length: {response_data['length']}")
            response_lines.append(f"Content-Type: {response_data['type']}")

        response_lines.append(response_data['body'])

    response = '\r\n'.join(response_lines)
    print(response)
    return bytes(response, 'utf-8')


if __name__ == '__main__':
    args = get_args()
    if args.request:
        client_request = sys.stdin.buffer.read()
        data = process_request(client_request)
        server_response = create_response(data)
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
