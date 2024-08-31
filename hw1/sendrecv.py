from collections import deque

MAX_LENGTH = 1024


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

class MySender:
    def __init__(self, channel):
        self.channel = channel

    def send_message(self, message_bytes):
        self.channel.send_bits(bytes_to_bits(message_bytes + b'\x00'))

class MyReceiver:
    def __init__(self, got_message_function):
        self.got_message_function = got_message_function
        self.recent_bits = bytearray()

    def handle_bit_from_network(self, the_bit):
        self.recent_bits.append(the_bit)
        if len(self.recent_bits) % 8 == 0 and self.recent_bits[-8:] == bytearray([0,0,0,0,0,0,0,0]):
            message_with_0 = bits_to_bytes(self.recent_bits)
            self.recent_bits.clear()
            self.got_message_function(message_with_0[:-1])
