"""Sandbox code for homeworks."""

import struct

from hw1.sendrecv import *
from hw1.test import Channel
from zlib import crc32

if __name__ == '__main__':
    received_messages = []

    channel = Channel()
    sender = MySender(channel)
    receiver = MyReceiver(lambda m: received_messages.append(bytes(m)))

    messages = [
        b'\x00\xAA\xFF',
        b'\xBB\x00\xFF',
        b'\x00\xCC\xFF',
    ]

    for msg in messages:
        sender.send_message(msg)

    for b in channel.got_bits:
        receiver.handle_bit_from_network(b)

    for msg in received_messages:
        print(msg)
