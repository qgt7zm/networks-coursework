import argparse
import json
import struct
import socket
import sys

QTYPES = {1: 'ipv4', 28: 'ipv6', 5: 'cname', 2: 'ns'}


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


# Read response helpers

def read_hostname(packet, start_byte):
    hostname = ''
    current_byte = start_byte
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
    return hostname[:-1], current_byte


def read_ipv4_address(resource_data):
    ipv4_address = ''
    for i in range(4):
        # Get 8-bit decimal segment
        ipv4_address += str(resource_data[i]) + '.'
    return ipv4_address[:-1]


def read_ipv6_address(resource_data):
    ipv6_address = ''
    for i in range(8):
        # Get 16-bit padded hex segment
        ipv6_segment = int.from_bytes(resource_data[2 * i: 2 * (i + 1)])
        ipv6_address += f'{ipv6_segment:04x}' + ':'
    return ipv6_address[:-1]


# Read response method

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
    question_count = int.from_bytes(packet[4:6])
    # print(f"{question_count} questions")

    # Bytes 7-12 are answer, NS, and AR count
    answer_count = int.from_bytes(packet[6:8])
    authority_count = int.from_bytes(packet[8:10])
    additional_count = int.from_bytes(packet[10:12])
    # print(f"{answer_count + authority_count + additional_count} resources")

    # Read question records
    current_byte = 12

    for i in range(question_count):
        # Read next question hostname
        hostname, current_byte = read_hostname(packet, current_byte)
        print(f"Question name = {hostname}")

        # Next 4 bytes are question type and class
        current_byte += 4

    # Read addresses and CNAMES from answers

    answer_names = []
    answer_addresses = []
    found_address = False  # No addresses found
    found_cname = False  # No CNAMEs found

    for _ in range(answer_count):
        # Read next resource hostname
        hostname, current_byte = read_hostname(packet, current_byte)
        print(f"Answer {hostname} with ", end='')

        # Next 8 bytes are question type, question class, and TTL
        q_type_val = int.from_bytes(packet[current_byte:current_byte + 2])
        q_type = QTYPES[q_type_val]
        current_byte += 8

        if q_type.startswith('ip'):
            found_address = True
        elif q_type == 'cname':
            found_cname = True

        # Next 2 bytes is resource data length
        resource_length = int.from_bytes(packet[current_byte:current_byte + 2])
        current_byte += 2

        # Parse resource data
        resource_data = packet[current_byte:current_byte + resource_length]

        if q_type == 'ipv4':
            ipv4_address = read_ipv4_address(resource_data)
            answer_addresses.append(ipv4_address)
            print(f"IPv4 = {ipv4_address}")
        elif q_type == 'ipv6':
            ipv6_address = read_ipv6_address(resource_data)
            answer_addresses.append(ipv6_address)
            print(f"IPv6 = {ipv6_address}")
        elif q_type == 'cname':
            resource_cname, _ = read_hostname(packet, current_byte)
            answer_names.append(resource_cname)
            print(f"CNAME = {resource_cname}")

        current_byte += resource_length

    # Read server records
    # TODO read separately
    server_names = []
    server_addresses = []

    for _ in range(authority_count + additional_count):
        # Read next resource hostname
        hostname, current_byte = read_hostname(packet, current_byte)
        print(f"Server {hostname} with ", end='')

        # Next 8 bytes are question type, question class, and TTL
        q_type_val = int.from_bytes(packet[current_byte:current_byte + 2])
        q_type = QTYPES[q_type_val]
        current_byte += 8

        # Next 2 bytes is resource data length
        resource_length = int.from_bytes(packet[current_byte:current_byte + 2])
        current_byte += 2

        # Parse resource data
        resource_data = packet[current_byte:current_byte + resource_length]

        if q_type == 'ipv4':
            ipv4_address = read_ipv4_address(resource_data)
            server_addresses.append(ipv4_address)
            print(f"IPv4 = {ipv4_address}")
        elif q_type == 'ipv6':
            ipv6_address = read_ipv6_address(resource_data)
            server_addresses.append(ipv6_address)
            print(f"IPv6 = {ipv6_address}")
        elif q_type == 'ns':
            resource_cname, _ = read_hostname(packet, current_byte)
            server_names.append(resource_cname)
            print(f"NS name = {resource_cname}")

        current_byte += resource_length

    # Create output
    output_dict = {}

    if found_address:
        output_dict['kind'] = 'address'  # Addresses found
        output_dict['addresses'] = answer_addresses
    elif found_cname:
        output_dict['kind'] = 'next-name'  # CNAMEs and no addresses found
        output_dict['next-name'] = answer_names[-1]
    else:
        output_dict['kind'] = 'next-server'  # No addresses or CNAMEs found
        output_dict['next-server-names'] = server_names
        output_dict['next-server-addresses'] = server_addresses

    return output_dict


if __name__ == '__main__':
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
        packet_length = int.from_bytes(prefix)

        # Read remaining data
        input_packet = sys.stdin.buffer.read(packet_length)
        output = read_response(input_packet)

        # Print json output
        print(json.dumps(output, indent=4))
