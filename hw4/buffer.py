from collections import deque

from simulator import Packet
from util import trace

class DropTailBuffer:
    """A drop-tail, FIFO buffer."""
    def __init__(self, capacity, bandwidth, label):
        self._queue = deque()
        self._capacity = capacity
        self._label = label
        self._size_in_buffer = 0

    def enqueue(self, packet: Packet):
        if len(self._queue) < self._capacity:
            trace('buffer-enqueue', f'buffering packet from {packet.label} to {self._label} (buffer size {self._size_in_buffer}/{self._capacity})')
            self._queue.append(packet)
            self._size_in_buffer += 1
        else:
            trace('buffer-drop', f'dropping packet from {packet.label} to {self._label} due to full buffer')

    def dequeue(self) -> Packet | None:
        if len(self._queue) == 0:
            return None
        else:
            packet = self._queue.popleft()
            self._size_in_buffer -= 1
            trace('buffer-dequeue', f'unbuffering packet from {packet.label} for {self._label} (buffer size {self._size_in_buffer}/{self._capacity})')
            return packet


class PriorityQueueBuffer:
    """A strict priority buffer that prefers c1 over c2."""
    def __init__(self, capacity, bandwidth, label):
        self._queue1 = deque()  # queue for c1
        self._queue2 = deque()  # queue for c2
        self._capacity = capacity
        self._label = label
        self._size_in_buffer = 0

    def _queue_length(self) -> int:
        return len(self._queue1) + len(self._queue2)

    def enqueue(self, packet: Packet):
        # Queue has room
        if self._queue_length() < self._capacity:
            # Packet from c1
            if packet.label == 'c1':
                self._queue1.append(packet)
            # Packet from c2
            else:
                self._queue2.append(packet)

            self._size_in_buffer += 1
            trace('buffer-enqueue', f'buffering packet from {packet.label} to {self._label} (buffer size {self._size_in_buffer}/{self._capacity})')
        # Queue is full
        else:
            # Replace last from c2 with last from c1
            if len(self._queue2) > 0 and packet.label == 'c1':
                packet_replace = self._queue2.pop()
                trace('buffer-drop', f'replacing packet from {packet_replace.label} to {self._label} due to full buffer')

                self._queue1.append(packet)
                trace('buffer-enqueue',f'buffering packet from {packet.label} to {self._label} (buffer size {self._size_in_buffer}/{self._capacity})')
            # Drop last from c1/c2
            else:
                trace('buffer-drop', f'dropping packet from {packet.label} to {self._label} due to full buffer')

    def dequeue(self) -> Packet | None:
        # Queue is empty
        if self._queue_length() == 0:
            return None
        # Queue has packets
        else:
            # Pop from c1
            if len(self._queue1) > 0:
                packet = self._queue1.popleft()
            # Pop from c2
            else:
                packet = self._queue2.popleft()

            self._size_in_buffer -= 1
            trace('buffer-dequeue', f'unbuffering packet from {packet.label} for {self._label} (buffer size {self._size_in_buffer}/{self._capacity})')
            return packet
