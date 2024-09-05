"""
Frame format:
<checksum> (4 bytes) + <message> (variable bytes) + SEPARATOR_CHAR (1 byte)
"""

import struct

from zlib import crc32

# Constants
MAX_LENGTH = 1024
SEPARATOR_BITS = bytes([0, 1, 0])
SEPARATOR_CHAR = 0x00
ESCAPE_CHAR = 0xFF
CHECKSUM_SIZE_BITS = 32

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

def convert_to_escape(the_bytes: bytearray) -> bytearray:
    escaped_bytes = bytearray()
    for byte in the_bytes:
        if byte == SEPARATOR_CHAR or byte == ESCAPE_CHAR:
            escaped_bytes.append(ESCAPE_CHAR)
        escaped_bytes.append(byte)
    return escaped_bytes

def convert_from_escape(the_bytes: bytearray) -> bytearray:
    message_bytes = bytearray()
    escaping = False

    for byte in the_bytes:
        if byte == ESCAPE_CHAR and not escaping:
            escaping = True
            continue
        elif escaping:
            escaping = False
        message_bytes.append(byte)
    return message_bytes


# Network Implementations

class MySender:
    def __init__(self, channel):
        self.channel = channel

    def send_message(self, message_bytes):
        print(f"msg 1 = {message_bytes}")

        # Compute the checksum
        checksum = crc32(message_bytes)  # 4 bytes unsigned
        checksum_bytes = struct.pack('<L', checksum)
        # print(f"cksm 1 = {checksum:#032b}")

        # Convert to bits
        data_bits = bytes_to_bits(checksum_bytes + message_bytes)
        print(f"bits 1 = {bytes(data_bits)}")

        # Escape bits
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
        print(f"sent = {bytes(bits_to_send)}")
        self.channel.send_bits(bits_to_send)

class MyReceiver:
    def __init__(self, got_message_function):
        self.got_message_function = got_message_function
        self.recent_bits = bytearray()  # the bits buffer
        self.escaping = False  # if reading escape sequence
        self.checksum = None  # the message checksum
        self.recovering = False # recovering from corrupt message

    # Helper Functions

    def got_a_byte(self) -> bool:
        return len(self.recent_bits) % 8 == 0

    def got_separator_bits(self) -> bool:
        return self.recent_bits[-3:] == bytearray([0, 1, 0])

    def got_separator_byte(self) -> bool:
        return self.recent_bits[-8:] == bytearray([0, 0, 0, 0, 0, 0, 0, 0])

    def got_escape_byte(self) -> bool:
        return self.recent_bits[-8:] == bytearray([1, 1, 1, 1, 1, 1, 1, 1])

    # Receiver Functions

    def handle_bit_from_network(self, the_bit):
        self.recent_bits.append(the_bit)

        # Stop at the separator
        if len(self.recent_bits) >= 3 and self.got_separator_bits():
            print(f"got = {bytes(self.recent_bits)}")

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

            print(f"bits 2 = {bytes(data_bits)}")

            # Read the checksum
            checksum_bits = data_bits[:CHECKSUM_SIZE_BITS]
            checksum_bytes = bits_to_bytes(checksum_bits)
            self.checksum, = struct.unpack('<L', checksum_bytes)
            # print(f"cksm 2 = {self.checksum:#032b}")

            # Read the message
            message_bits = data_bits[CHECKSUM_SIZE_BITS:]
            message_bytes = bits_to_bytes(message_bits)
            print(f"msg 2 = {bytes(message_bytes)}")

            # Verify the checksum
            checksum_check = crc32(message_bytes)
            if checksum_check == self.checksum:
                print(f"got {bytes(message_bytes)}")
                self.checksum = None
                self.recent_bits.clear()
                self.got_message_function(message_bytes)
            else:
                print(f"missed {bytes(message_bytes)}")
                self.checksum = None
                self.recent_bits.clear()

        # # Read the checksum bit by bit
        # if self.checksum is None:
        #     if len(self.recent_bits) >= CHECKSUM_SIZE_BITS:
        #         self.finish_checksum()
        #
        # # Read the message byte by byte
        # elif self.got_a_byte():
        #     if self.got_escape_byte() and not self.escaping:
        #         # Read the escape byte and start an escape sequence
        #         self.escaping = True
        #     elif self.escaping:
        #         # Read a regular character and finish an escape sequence
        #         self.escaping = False
        #     elif self.got_separator_byte() and not self.escaping:
        #         # Read the separator byte and end the checksum/message
        #         self.finish_message()

    def finish_checksum(self):
        print(f"got = {bytes(self.recent_bits)}", end='')
        checksum_bytes = bits_to_bytes(self.recent_bits)
        self.recent_bits.clear()

        try:
            self.checksum, = struct.unpack('<L', checksum_bytes)
        except struct.error:
            self.checksum = -1 # corrupted checksum, will not usually happen
        # print(f"cksm 2 = {checksum_bytes} = {self.checksum}")

    def finish_message(self):
        print(bytes(self.recent_bits))
        escaped_bytes = bits_to_bytes(self.recent_bits)[:-1]  # ignore separator
        self.recent_bits.clear()

        # De-escape message
        message_bytes = convert_from_escape(escaped_bytes)

        # Verify the checksum
        checksum_check = crc32(escaped_bytes)  # 4 bytes unsigned
        if checksum_check == self.checksum:
            print(f"got {bytes(message_bytes)}")
            self.checksum = None
            self.got_message_function(message_bytes)
        else:
            print(f"missed {bytes(message_bytes)}")
            self.checksum = None
