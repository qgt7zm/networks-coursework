from collections import deque

class DropTailBuffer:
    def __init__(self, capacity, bandwidth, label):
        self._queue = deque()
        self._capacity = capacity
        self._label = label
        self._size_in_buffer = 0

    def enqueue(self, packet):
        if len(self._queue) < self._capacity:
            trace('buffer-enqueue', f'buffering {packet} to {self._label} (buffer size {self._size_in_buffer}/{self._capacity}')
            self._queue.append(packet)
        else:
            trace('buffer-drop', f'dropping {packet} to {self._label} due to full buffer')

    def dequeue(self):
        if len(self._queue) == 0:
            return None
        else:
            packet = self._queue.popleft()
            self._size_in_buffer -= packet.size
            trace('buffer-dequeue', f'unbuffering {packet} for {self._label}')
            return packet

