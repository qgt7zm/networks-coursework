import config
from util import Packet, Message, trace, now, create_timer, cancel_timer
from collections import deque
from dataclasses import dataclass
from typing import Any

def _next(i) -> int:
    """Compute next sequence number after `i`."""
    return (i + 1) % (config.MAXIMUM_SEQUENCE + 1)

def _delta(i, j) -> int:
    """Compute difference between sequence numbers i (first) and j (later) (taking into account wraparound).
    Always returns a positive number.

    For example, if i == config.MAXIMUM_SEQUENCE and j == 0, returns 1.
    If i == 5 and j == 4, returns config.MAXIMUM_SEQUENCE.
    """
    return (j - i + config.MAXIMUM_SEQUENCE + 1) % (config.MAXIMUM_SEQUENCE + 1)

@dataclass
class SendPacketInfo:
    packet: Packet
    timer: Any

class MySender:
    def __init__(self):
        self.window_size = config.INITIAL_WINDOW
        self.last_adjust_time = 0
        self.last_frame_sent = config.MAXIMUM_SEQUENCE
        self.last_ack_received = config.MAXIMUM_SEQUENCE
        self.queue = {}

        # Create output file
        self.output_file = open('last-window-sizes.csv', 'w')
        self.output_file.write('time,window\n')

    def _do_send_packet(self, packet):
        self.to_network(packet)
        self.queue[packet.seq_num] = \
            SendPacketInfo(
                packet=packet,
                timer=create_timer(config.INITIAL_TIMEOUT, lambda: self._do_send_packet(packet)),
            )

    def from_application(self, message):
        missing_count = _delta(self.last_ack_received, self.last_frame_sent)
        trace('sender', f'missing_count = {missing_count}')

        if missing_count >= self.window_size:
            # Packet not window
            return False
        else:
            # Send packet
            packet = Packet()
            packet.data = message.data
            packet.is_end = message.is_end
            self.last_frame_sent = packet.seq_num = _next(self.last_frame_sent)
            assert packet.seq_num <= config.MAXIMUM_SEQUENCE
            self._do_send_packet(packet)
            return True

    def from_network(self, packet):
        trace('sender', f'sender from_network (initially): LAR={self.last_ack_received} LFS={self.last_frame_sent} window={self.window_size}')

        # Checking > max window size because _delta can't return negative numbers,
        # So we'll get a big positive _delta is packet.ack_num is before LAR
        if _delta(self.last_ack_received, packet.ack_num) > config.MAXIMUM_WINDOW:
            trace('sender', f'ignoring ACK {packet.ack_num} that appears to be old')
        else:
            # Mark all sequence numbers covered by new ACK as done
            while self.last_ack_received != packet.ack_num:
                trace('sender', f'marking {self.last_ack_received} as done for {packet.ack_num}')
                self.last_ack_received = _next(self.last_ack_received)
                item = self.queue.pop(self.last_ack_received, None)
                if item is not None and item.timer is not None:
                    cancel_timer(item.timer)

        missing_count = _delta(self.last_ack_received, self.last_frame_sent)
        trace('sender', f'sender from_network (after processing): LAR={self.last_ack_received} LFS={self.last_frame_sent} window={self.window_size}')
        if missing_count < self.window_size:
            self.ready_for_more_from_application()

class MyReceiver:
    def __init__(self):
        self.last_frame_received = config.MAXIMUM_SEQUENCE
        self.last_ack_sent = config.MAXIMUM_SEQUENCE
        self.queue = {}

    def from_network(self, packet):
        trace('receiver', f'from_network: LFR={self.last_frame_received} (next: {_next(self.last_frame_received)}) LAS={self.last_ack_sent}')

        if _delta(self.last_frame_received, packet.seq_num) > config.MAXIMUM_WINDOW or \
        self.last_frame_received == packet.seq_num:
            # Got duplicate packet
            trace('receiver', f'presumed duplicate data {packet.seq_num}')
        else:
            # Read all received messages
            message = Message(data=packet.data, is_end=packet.is_end)
            self.queue[packet.seq_num] = message
            while True:
                idx = _next(self.last_frame_received)
                message = self.queue.pop(idx, None)
                trace('receiver', f'for {idx}, got {message}')
                if message is not None:
                    self.last_frame_received = idx
                    self.to_application(message)
                else:
                    break

        # ACK all previous messages
        out_packet = Packet(ack_num=self.last_frame_received)
        self.last_ack_sent = packet.ack_num
        self.to_network(out_packet)
