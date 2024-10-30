import argparse
import json
import random
import struct
import socket
import sys

IPV4_CODE = 1
IPV6_CODE = 28
QTYPES = {IPV4_CODE: 'ipv4', IPV6_CODE: 'ipv6', 5: 'cname', 2: 'ns'}


def parse_args():
    # Parse args
    # Source: https://stackoverflow.com/questions/20063/whats-the-best-way-to-parse-command-line-arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--send-request', type=str)  # query hostname and read response
    parser.add_argument('--create-request', type=str)  # make query for hostname
    parser.add_argument('--server', type=str)  # server IP
    parser.add_argument('--port', type=int)  # port num
    parser.add_argument('--ipv4', action='store_true')
    parser.add_argument('--ipv6', action='store_true')
    parser.add_argument('--process-response', action='store_true')  # output json
    return parser.parse_args()


def create_request(hostname: str, server: str, port: int, code: int):
    # print(f"Hostname = {hostname}")
    # print(f"Server = {server}")
    # print(f"Port = {port}")

    # Bytes 1-2 are transaction ID
    transaction_id = random.randint(0, 65535)

    # Bytes 3-4 are flags
    # Not a response, standard query, authoritative, no recursion
    header_flags = 0x0400
    header = struct.pack('>HH', transaction_id, header_flags)

    # Bytes 5-12 are record counts
    # One question
    record_counts = [0, 1, 0, 0, 0, 0, 0, 0]
    header += bytes(record_counts)

    # Pack the domain labels
    labels = hostname.split('.')
    for label in labels:
        label_length = len(label)
        if label_length == 0:
            continue
        # Get char values
        label_chars = [ord(ch) for ch in label]
        label_bytes = bytes([label_length] + label_chars)
        # print(label_bytes)
        header += bytes(label_bytes)
    header += b'\x00'

    # Add 4 bytes for question type and class
    # IPv4 or IPv6 and IN (1)
    header += struct.pack('HH', code, 1)

    # Encode 2 bytes for length
    header_length = struct.pack('>H', len(header))

    # for bit in header:
    #     print(f'{bit:02x} ', end='')
    # print()

    sys.stdout.buffer.write(header_length + header)


## Read Response Helpers ##

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


def read_record_data(resource_data, q_type: str, names: list, addresses: list, packet, current_byte: int):
    if q_type == 'ipv4':
        ipv4_address = read_ipv4_address(resource_data)
        addresses.append(ipv4_address)
        print(f"IPv4 = {ipv4_address}")
    elif q_type == 'ipv6':
        ipv6_address = read_ipv6_address(resource_data)
        addresses.append(ipv6_address)
        print(f"IPv6 = {ipv6_address}")
    elif q_type == 'cname':
        # Only used in answer
        resource_cname, _ = read_hostname(packet, current_byte)
        names.append(resource_cname)
        print(f"CNAME = {resource_cname}")
    elif q_type == 'ns':
        # Only used in server
        resource_ns, _ = read_hostname(packet, current_byte)
        names.append(resource_ns)
        print(f"NS name = {resource_ns}")


## Read Response Method ##

def read_response(packet) -> dict:
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

        # Next 8 bytes are question type, class, and TTL
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
        read_record_data(resource_data, q_type, answer_names, answer_addresses, packet, current_byte)

        current_byte += resource_length

    # Read server records
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
        read_record_data(resource_data, q_type, server_names, server_addresses, packet, current_byte)

        current_byte += resource_length

    # Create output dictionary
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


## Main Method ##

if __name__ == '__main__':
    args = parse_args()

    if args.create_request:
        # Display args
        # TODO create DNS request
        if args.ipv4:
            query_code = IPV4_CODE
            # print("IPv4 mode")
        elif args.ipv6:
            query_code = IPV6_CODE
            # print("IPv6 mode")
        else:
            print("Invalid mode")
            exit(1)
        create_request(args.create_request, args.server, args.port, query_code)
        # TODO print request
    elif args.process_response:
        # 2-byte prefix is length
        prefix = sys.stdin.buffer.read(2)
        packet_length = int.from_bytes(prefix)

        # Read remaining data
        input_packet = sys.stdin.buffer.read(packet_length)

        # Print json output
        output = read_response(input_packet)
        print(json.dumps(output, indent=4))

    # TODO send request
