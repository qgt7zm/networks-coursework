import config
from dataclasses import dataclass
from typing import Any
from util import Packet, Message, trace
from collections import deque

class TrivialSender:
    def __init__(self):
        pass

    def from_application(self, message):
        packet = Packet()
        packet.data = message.data
        packet.is_end = message.is_end
        packet.seq_num = 0
        self.to_network(packet)
        return True

class TrivialReceiver:
    def __init__(self):
        pass

    def from_network(self, packet):
        message = Message(data=packet.data, is_end=packet.is_end)
        self.to_application(message)
