from collections import deque
from zlib import crc32

# Constants
MAX_LENGTH = 1024
SEPARATOR_CHAR = 0x00
ESCAPE_CHAR = 0xFF


# Helper Functions
def got_a_byte(the_bits: bytearray) -> bool:
    return len(the_bits) % 8 == 0

def got_separator_byte(the_bits: bytearray) -> bool:
    return the_bits[-8:] == bytearray([0, 0, 0, 0, 0, 0, 0, 0])

def got_escape_byte(the_bits: bytearray) -> bool:
    return the_bits[-8:] == bytearray([1, 1, 1, 1, 1, 1, 1, 1])

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
        escaped_message = bytearray()
        for byte in message_bytes:
            if byte == SEPARATOR_CHAR or byte == ESCAPE_CHAR:
                escaped_message.append(ESCAPE_CHAR)
            escaped_message.append(byte)

        print(f"msg 1 = {message_bytes}")

        # Send the escaped message
        self.channel.send_bits(bytes_to_bits(
            escaped_message + bytes([SEPARATOR_CHAR])
        ))

class MyReceiver:
    def __init__(self, got_message_function):
        self.got_message_function = got_message_function
        self.recent_bits = bytearray()  # the bits buffer
        self.escaping = False  # if reading escape sequence

    def handle_bit_from_network(self, the_bit):
        self.recent_bits.append(the_bit)
        # TODO verify checksum

        if got_a_byte(self.recent_bits):
            # Read the next byte
            if got_escape_byte(self.recent_bits) and not self.escaping:
                # Read the escape byte and start an escape sequence
                self.escaping = True
            elif self.escaping:
                # Read a regular character and finish an escape sequence
                # TODO verify escape sequence
                self.escaping = False
            elif got_separator_byte(self.recent_bits) and not self.escaping:
                # Read the separator byte and end the message
                self.finish_message()

    def finish_message(self):
        escaped_message = bits_to_bytes(self.recent_bits)[:-1]
        self.recent_bits.clear()
        print(f"msg 2 = {escaped_message}")

        # Decode escape sequences
        message_bytes = bytearray()
        escaping = False

        # Escape special characters
        for byte in escaped_message:
            if byte == ESCAPE_CHAR and not escaping:
                escaping = True
                continue
            elif escaping:
                escaping = False
            message_bytes.append(byte)

        self.got_message_function(message_bytes)
