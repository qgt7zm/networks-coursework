"""
Frame format:
<checksum> (4 bytes) + <message> (variable bytes) + 010 (3 bits)
"""

import struct

from zlib import crc32

# Constants

MAX_LENGTH = 1024
SEPARATOR_BITS = bytes([0, 1, 0])
CHECKSUM_SIZE_BYTES = 4

# Conversion Functions

def bytes_to_bits(the_bytes: bytearray) -> bytearray:
    # Note: little-endian
    result = bytearray()
    for a_byte in the_bytes:
        for i in range(8):
            result.append(0 if (a_byte & (0x1 << i)) == 0 else 1)
    return result

def bits_to_bytes(the_bits: bytearray) -> bytearray:
    result = bytearray()
    for i in range(0, len(the_bits), 8):
        current = 0
        for j in range(8):
            current += (the_bits[i+j] << j)
        result.append(current)
    return result

# Network Implementations

class MySender:
    def __init__(self, channel):
        self.channel = channel

    def send_message(self, message_bytes):
        # print(f"msg 1 = {message_bytes}")

        # Compute the checksum
        checksum = crc32(message_bytes)  # 4 bytes unsigned
        checksum_bytes = struct.pack('<L', checksum)
        # print(f"cksm 1 = {checksum:#032b}")

        # Convert checksum/message to bits
        data_bits = bytes_to_bits(checksum_bytes + message_bytes)
        # print(f"bits 1 = {bytes(data_bits)}")

        # Escape checksum/message bits
        escaped_bits = bytearray()
        last_bit = None
        for this_bit in data_bits:
            escaped_bits.append(this_bit)
            # If last two bits are "01", add another 1
            if last_bit == 0 and this_bit == 1:
                escaped_bits.append(1)
            last_bit = this_bit

        # Send the frame
        bits_to_send = bytearray(escaped_bits + SEPARATOR_BITS)
        # print(f"sent = {bytes(bits_to_send)}")
        self.channel.send_bits(bits_to_send)

class MyReceiver:
    def __init__(self, got_message_function):
        self.got_message_function = got_message_function
        self.recent_bits = bytearray()  # the bits buffer
        self.checksum = None  # the message checksum

    # Helper Functions

    def got_separator_bits(self) -> bool:
        return self.recent_bits[-3:] == bytearray([0, 1, 0])

    # Receiver Functions

    def handle_bit_from_network(self, the_bit):
        self.recent_bits.append(the_bit)

        # Stop at the separator
        if len(self.recent_bits) >= 3 and self.got_separator_bits():
            # print(f"got = {bytes(self.recent_bits)}")

            # Unescape the message
            escaped_bits = self.recent_bits[:-3]

            data_bits = bytearray()
            last_last_bit = None
            last_bit = None

            for this_bit in escaped_bits:
                # If last two bits are "01" and this bit is "1", skip
                if last_last_bit == 0 and last_bit == 1 and this_bit == 1:
                    pass
                else:
                    data_bits.append(this_bit)
                last_last_bit, last_bit = last_bit, this_bit
            # print(f"bits 2 = {bytes(data_bits)}, {len(data_bits)}")

            # Convert checksum/message to bytes
            if len(data_bits) % 8 != 0:
                # Not enough bits for whole bits
                data_bytes = bytearray()
            else:
                data_bytes = bits_to_bytes(data_bits)

            # Read checksum
            checksum_bytes = data_bytes[:CHECKSUM_SIZE_BYTES]
            if len(checksum_bytes) < CHECKSUM_SIZE_BYTES:
                # Not enough bytes for checksum
                self.checksum = -1
            else:
                self.checksum, = struct.unpack('<L', checksum_bytes)
            # print(f"cksm 2 = {self.checksum:#032b}")

            # Read message
            message_bytes = data_bytes[CHECKSUM_SIZE_BYTES:]

            # Verify the checksum
            checksum_check = crc32(message_bytes)
            if checksum_check == self.checksum:
                # print(f"received msg 2 = {bytes(message_bytes)}")
                self.got_message_function(message_bytes)
            else:
                # print(f"missed msg 2 = {bytes(message_bytes)}")
                pass

            self.checksum = None
            self.recent_bits.clear()
