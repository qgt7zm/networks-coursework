from collections import deque
from zlib import crc32

# Constants
MAX_LENGTH = 1024
SEPARATOR_BYTE = 0x00
ESCAPE_BYTE = 0xFF


# Helper Functions
def got_a_byte(the_bytes: bytearray) -> bool:
    return len(the_bytes) % 8 == 0


def got_separator_byte(the_bytes: bytearray) -> bool:
    return the_bytes[-8:] == bytearray([0, 0, 0, 0, 0, 0, 0, 0])


def got_escape_byte(the_bytes: bytearray) -> bool:
    return the_bytes[-8:] == bytearray([1, 1, 1, 1, 1, 1, 1, 1])

# Note: little-endian
def bytes_to_bits(the_bytes):
    result = bytearray()
    for a_byte in the_bytes:
        for i in range(8):
            result.append(0 if (a_byte & (0x1 << i)) == 0 else 1)
    return result

def bits_to_bytes(the_bits):
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
        # Escape special characters
        bytes_to_send = bytearray()
        for byte in message_bytes:
            if byte == SEPARATOR_BYTE or byte == ESCAPE_BYTE:
                bytes_to_send.append(ESCAPE_BYTE)
            bytes_to_send.append(byte)

        # Send the escaped message
        self.channel.send_bits(bytes_to_bits(bytes_to_send + b'\x00'))

class MyReceiver:
    def __init__(self, got_message_function):
        self.got_message_function = got_message_function
        self.escaping = False  # if reading escape sequence
        self.recent_bits = bytearray()  # the receiver buffer
        self.message_bytes = bytearray()  # the message buffer

    def handle_bit_from_network(self, the_bit):
        self.recent_bits.append(the_bit)
        # TODO unescape sequences starting with \0xFF
        # TODO checksum

        if got_a_byte(self.recent_bits):
            # Decode escape sequences
            if got_escape_byte(self.recent_bits) and not self.escaping:
                # Read the escape byte and start an escape sequence
                self.escaping = True
            elif self.escaping:
                # Finish an escape sequence
                # TODO verify escape sequence
                self.escaping = False
                last_byte = bits_to_bytes(self.recent_bits[-8:])
                self.message_bytes += last_byte
            elif got_separator_byte(self.recent_bits) and not self.escaping:
                # Read the separator byte and end the message
                self.recent_bits.clear()
                self.got_message_function(self.message_bytes)
                self.message_bytes.clear()
            else:
                # Read a normal character
                last_byte = bits_to_bytes(self.recent_bits[-8:])
                self.message_bytes += last_byte
