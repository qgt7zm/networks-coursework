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
        b'\x7E',
        b'\x7E' * 4,
    ]

    for msg in messages:
        sender.send_message(msg)

    for b in channel.got_bits:
        receiver.handle_bit_from_network(b)

    for msg1, msg2 in zip(messages, received_messages):
        print(f"msg = {msg2} -> {"correct" if msg1 == msg2 else "corrupted"}")
