import argparse
import json
import struct
import socket
import sys


def parse_args():
    # Parse args
    # Source: https://stackoverflow.com/questions/20063/whats-the-best-way-to-parse-command-line-arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--send-request', type=str)  # hostname
    parser.add_argument('--server', type=str)  # server IP
    parser.add_argument('--port', type=int)  # port num
    parser.add_argument('--ipv4', action='store_true')
    parser.add_argument('--ipv6', action='store_true')
    parser.add_argument('--process-response', action='store_true')  # output json
    return parser.parse_args()


def send_request(request):
    pass


def read_response(response):
    # First two bytes is length
    length = sys.stdin.buffer.read(2)
    length = 128 * length[0] + length[1]
    print(f"length = {length}")

    # Read remaining data
    packet = sys.stdin.buffer.read(length)

    # Second half of fourth byte is reply code
    print(f"packet = {packet}")
    reply_code = packet[3] & 0b1111

    if reply_code != 0:
        print("Error")
        return {'kind': 'error'}

    print(f"Reply code OK")

    return {
        'kind': 'error',
        'addresses': [],
        'next-name': '',
        'next-server-names': [],
        'next-server-addresses': []
    }


if __name__ == '__main__':
    print("Running dns.py")
    args = parse_args()

    # Display args

    if args.send_request:
        # TODO send DNS request
        print("sending request")
        print(f"hostname = {args.send_request}")
        print(f"server = {args.server}")
        print(f"port = {args.port}")
        print(f"ipv4 = {args.ipv4}")
        print(f"ipv6 = {args.ipv6}")
        send_request("foo")
    elif args.process_response:
        # TODO read DNS response
        print("reading input")
        output = read_response("foo")

        # TODO print json output
        print(output)
