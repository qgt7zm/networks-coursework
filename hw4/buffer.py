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


class WeightedFairQueuingBuffer:
    """A weighted fair queuing buffer that gives c1 twice as much bandwidth as c2."""
    class SubQueue:
        def __init__(self, weight: int):
            self.queue = deque()  # store packets with virtual times
            self.last_finish_time = 0
            self.weight = weight

        def __len__(self):
            return len(self.queue)

        def append(self, item: tuple):
            self.queue.append(item)

        def popleft(self) -> tuple:
            return self.queue.popleft()

        def pop(self) -> tuple:
            return self.queue.pop()

        def get_first_finish(self) -> int | float:
            if len(self.queue) > 0:
                _, finish = self.queue[0]
                return finish
            # nothing in queue
            else:
                return float('inf')

    def __init__(self, capacity, bandwidth, label):
        self._queue1 = self.SubQueue(weight=2)  # queue for c1
        self._queue2 = self.SubQueue(weight=1)  # queue for c2
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
                sub_queue = self._queue1
            # Packet from c2
            else:
                sub_queue = self._queue2

            # Calculate last finish time
            current_finish = sub_queue.last_finish_time + packet.size / sub_queue.weight
            sub_queue.append((packet, current_finish))

            self._size_in_buffer += 1
            trace('buffer-enqueue', f'buffering packet ({current_finish}) from {packet.label} to {self._label} (buffer size {self._size_in_buffer}/{self._capacity})')
            sub_queue.last_finish_time = current_finish
        # Queue is full
        else:
            # Packet from c1
            if packet.label == 'c1':
                own_queue = self._queue1
                other_queue = self._queue2
            # Packet from c2
            else:
                own_queue = self._queue2
                other_queue = self._queue1

            # Compare last finish times
            current_finish = own_queue.last_finish_time + packet.size / own_queue.weight
            other_finish = other_queue.last_finish_time

            # Replace with the new packet
            if current_finish < other_finish:
                if len(other_queue) > 0:
                    packet_replace, other_finish = other_queue.pop()
                    other_queue.last_finish_time -= packet.size / other_queue.weight
                    trace('buffer-drop', f'replacing ({other_finish}) packet from {packet_replace.label} to {self._label} due to full buffer')

                own_queue.append((packet, current_finish))
                own_queue.last_finish_time = current_finish
                trace('buffer-enqueue',f'buffering ({current_finish}) packet from {packet.label} to {self._label} (buffer size {self._size_in_buffer}/{self._capacity})')
            else:
                trace('buffer-drop', f'dropping packet from {packet.label} to {self._label} due to full buffer')

    def dequeue(self) -> Packet | None:
        # Queue is empty
        if self._queue_length() == 0:
            return None
        # Queue has packets
        else:
            # Compare first finish times
            finish1 = self._queue1.get_first_finish()
            finish2 = self._queue2.get_first_finish()

            # Pop from c1
            if finish1 <= finish2:
                packet, current_finish = self._queue1.popleft()
            # Pop from c2
            else:
                packet, current_finish = self._queue2.popleft()
            self._size_in_buffer -= 1
            trace('buffer-dequeue', f'unbuffering packet ({current_finish}) from {packet.label} for {self._label} (buffer size {self._size_in_buffer}/{self._capacity})')
            return packet