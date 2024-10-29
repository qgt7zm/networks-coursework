import argparse
import json
import struct
import socket


def parse_args():
    # Parse args
    # Source: https://stackoverflow.com/questions/20063/whats-the-best-way-to-parse-command-line-arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--send-request', type=str)  # hostname
    parser.add_argument('--server', type=str)  # server IP
    parser.add_argument('--port', type=int)  # port num
    parser.add_argument('--ipv4', action='store_true')
    parser.add_argument('--ipv6', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    print("Running dns.py")
    args = parse_args()

    # Display args
    print(f"hostname = {args.send_request}")
    print(f"server = {args.server}")
    print(f"port = {args.port}")
    print(f"ipv4 = {args.ipv4}")
    print(f"ipv6 = {args.ipv6}")

    # TODO send DNS request
    # TODO read DNS response
    # TODO create output file
