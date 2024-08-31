"""Sandbox code for homeworks."""

import struct
from hw1.sendrecv import *

if __name__ == '__main__':
    # Encoding message
    msg_bytes = b'\x00\xAA\xFF'
    print(f"msg bytes = {msg_bytes}")

    esc_bytes = bytearray()
    for byte in msg_bytes:
        # escape special bytes
        if byte == SEPARATOR_BYTE or byte == ESCAPE_BYTE:
            esc_bytes.append(ESCAPE_BYTE)
        esc_bytes.append(byte)

    print(f"esc bytes = {esc_bytes}")

    send_bytes = esc_bytes + b'\x00'  # send entire message

    # Decoding message
    rec_bits = bytes_to_bits(send_bytes)  # receive message as bits
    print(f"rec bits = {rec_bits}")

    buff = bytearray()
    msg = bytearray()
    escaping = False  # reading escape sequence

    for b in rec_bits:
        buff.append(b)
        if got_a_byte(buff) and got_escape_byte(buff) and not escaping:
            # Read the escape byte, start an escape sequence
            escaping = True
            print("escape")
        elif got_a_byte(buff) and escaping:
            # Finish an escape sequence
            # TODO verify escape sequence
            escaping = False
            last_byte = bits_to_bytes(buff[-8:])
            msg += last_byte
            print(f"- {last_byte}")
        elif got_a_byte(buff) and got_separator_byte(buff) and not escaping:
            # Read the separator byte, end the message
            last_byte = bits_to_bytes(buff[-8:])
            print(f"- {last_byte}")
            break  # got a complete message
        elif got_a_byte(buff):
            # Read a normal character
            last_byte = bits_to_bytes(buff[-8:])
            msg += last_byte
            print(f"- {last_byte}")

    rec_bytes = bits_to_bytes(buff)
    print(f"rec bytes = {rec_bytes}")

    print(f"msg = {msg}")
