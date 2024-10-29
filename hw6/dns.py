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


def read_response(packet):
    # Bit 1 of byte 3 is response
    response_mode = packet[2] >> 7
    if response_mode != 1:
        # Response mode should be 1
        return {'kind': 'malformed'}

    # Bits 5-8 of byte 4 are reply code
    reply_code = packet[3] & 0b1111
    if reply_code != 0:
        # Reply code should be 1
        return {'kind': 'error'}

    # Bytes 5-6 are question count
    q_count = int.from_bytes(packet[4:6])
    print(f"{q_count} questions")

    # Bytes 7-12 are answer, NS, and AR count
    a_count = int.from_bytes(packet[6:8])
    a_count += int.from_bytes(packet[8:10])
    a_count += int.from_bytes(packet[10:12])
    print(f"{a_count} answers")

    # TODO read questions and answers
    # Questions start after byte 13
    current_byte = 12
    addresses = []

    for i in range(q_count):
        hostname = ""

        # Read next question hostname
        while True:
            # First byte is label length
            label_length = packet[current_byte]
            current_byte += 1
            if label_length == 0:
                break

            # Read next label
            label = packet[current_byte:current_byte + label_length].decode('utf-8')
            hostname += label + '.'
            current_byte += label_length

        if len(hostname) > 0:
            addresses.append(hostname)

        # Next 4 bytes are question type and class
        q_type = int.from_bytes(packet[current_byte:current_byte + 2])
        q_class = int.from_bytes(packet[current_byte + 2:current_byte + 4])
        current_byte += 4

        print(hostname)
        print(q_type)
        print(q_class)

    return {
        'kind': 'address',
        'addresses': addresses,
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
        # 2-byte prefix is length
        prefix = sys.stdin.buffer.read(2)
        length = int.from_bytes(prefix)

        # Read remaining data
        input_packet = sys.stdin.buffer.read(length)
        output = read_response(input_packet)

        # TODO print json output
        print(output)
