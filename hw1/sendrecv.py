import struct

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

def convert_to_escape(the_bytes: bytearray) -> bytearray:
    escaped_bytes = bytearray()
    for byte in the_bytes:
        if byte == SEPARATOR_CHAR or byte == ESCAPE_CHAR:
            escaped_bytes.append(ESCAPE_CHAR)
        escaped_bytes.append(byte)
    return escaped_bytes


# Network Implementations

class MySender:
    def __init__(self, channel):
        self.channel = channel

    def send_message(self, message_bytes):
        print(f"msg 1 = {message_bytes}")

        # Escape special characters
        escaped_message = convert_to_escape(message_bytes)

        # Add the checksum
        checksum = crc32(escaped_message)  # 4 bytes unsigned
        checksum_bytes = struct.pack('<L', checksum)
        escaped_checksum = convert_to_escape(checksum_bytes)
        print(f"cksm 1 = {checksum_bytes} = {checksum}")

        # Send the checksum and thea  message
        bytes_to_send = escaped_checksum + bytes([SEPARATOR_CHAR]) + escaped_message + bytes([SEPARATOR_CHAR])
        # print(f"send = {bytes_to_send}")
        self.channel.send_bits(bytes_to_bits(bytes_to_send))

class MyReceiver:
    def __init__(self, got_message_function):
        self.got_message_function = got_message_function
        self.recent_bits = bytearray()  # the bits buffer
        self.escaping = False  # if reading escape sequence
        self.checksum = None  # the message checksum

    def handle_bit_from_network(self, the_bit):
        self.recent_bits.append(the_bit)
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
                # Read the separator byte and end the checksum/message
                self.finish_message()

    def finish_message(self):
        escaped_bytes = bits_to_bytes(self.recent_bits)[:-1]
        self.recent_bits.clear()

        # Decode escape sequences
        message_bytes = bytearray()
        escaping = False

        for byte in escaped_bytes:
            if byte == ESCAPE_CHAR and not escaping:
                escaping = True
                continue
            elif escaping:
                escaping = False
            message_bytes.append(byte)

        if self.checksum is None:
            print(f"cksm bytes = {message_bytes}, {len(message_bytes)}")
            try:
                self.checksum, = struct.unpack('<L', message_bytes)  # keep as tuple, unpack gives errors for blank message
            except struct.error:
                self.checksum = -1  # corrupt checksum if not 4 bytes
                print(f"error")
            print(f"cksm 2 = {message_bytes} = {self.checksum}")
        else:
            # print(f"msg 2 = {message_bytes}")

            # Verify the checksum
            checksum_check = crc32(escaped_bytes)  # 4 bytes unsigned
            if checksum_check == self.checksum:
                print(f"got {message_bytes}")
                self.checksum = None
                self.got_message_function(message_bytes)
            else:
                print(f"missed {message_bytes}")
                self.checksum = None
