import argparse
import socket
import struct

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('ip', type=str)  # host IP address
    parser.add_argument('port', type=int)  # host port
    args = parser.parse_args()

    ip = args.ip
    port = args.port
    print(f"Running webserver on https://{ip}:{port}")