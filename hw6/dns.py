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
    # 2-byte prefix is length
    prefix = sys.stdin.buffer.read(2)
    length = int.from_bytes(prefix)

    # Read remaining data
    packet = sys.stdin.buffer.read(length)

    # Bytes 1-2 are ID

    # Second half of byte 4 is reply code
    print(f"packet = {packet}")
    reply_code = packet[3] & 0b1111
    if reply_code != 0:
        return {'kind': 'error'}

    # Bytes 5-6 are question count
    q_count = int.from_bytes(packet[4:6])
    print(f"{q_count} questions")

    # Bytes 7-12 are answer, NS, and AR count
    a_count = int.from_bytes(packet[6:8])
    a_count += int.from_bytes(packet[8:10])
    a_count += int.from_bytes(packet[10:12])
    print(f"{a_count} answers")

    return {
        'kind': 'address',
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
