"""Sandbox code for homeworks."""

import struct

from hw1.sendrecv import *
from hw1.test import Channel

if __name__ == '__main__':
    received_messages = []

    channel = Channel()
    sender = MySender(channel)
    receiver = MyReceiver(lambda m: received_messages.append(bytes(m)))

    messages = [
        b'',
        b'\x00\xAA\xFF',
        b'\xBB\x00\xFF',
        b'\xFF\xCC\x00' * 2,
    ]

    for msg in messages:
        sender.send_message(msg)

    for b in channel.got_bits:
        receiver.handle_bit_from_network(b)

    for msg in received_messages:
        print(f"msg = {msg}")
