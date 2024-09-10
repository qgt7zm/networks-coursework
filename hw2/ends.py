import config
from util import Packet, Message, now, trace

# Constants

ACK_PACKET_DATA = b'ACK'

# Class Implementations

class MySender:
    def __init__(self):
        self.seq_num = 0  # seq num of current packet
        self.waiting = False  # waiting for ACK

    def from_application(self, message: Message) -> bool:
        packet = Packet(data=message.data, is_end=message.is_end, seq_num=self.seq_num)

        if config.MODE == 'no-ack':
            self.to_network(packet)
        elif config.MODE == 'one-zero':
            if self.waiting:
                return False
            self.to_network(packet)
            print(f"sender sent {packet.seq_num}")

            # Wait for ACK
            self.waiting = True
        return True

    def from_network(self, packet: Packet):
        if packet.data != ACK_PACKET_DATA:  # make sure we get ACK packet
            return

        print(f"sender got ACK {packet.seq_num}")
        if config.MODE == 'one-zero':
            if packet.seq_num == self.seq_num:  # make sure ACK has correct seq num
                self.waiting = False
                self.seq_num = 1 - self.seq_num  # flip the sequence bit
                self.ready_for_more_from_application()  # get the next message

class MyReceiver:
    def __init__(self):
        pass

    def from_network(self, packet: Packet) -> None:
        message = Message(data=packet.data, is_end=packet.is_end)

        if config.MODE == 'no-ack':
            self.to_application(message)
        elif config.MODE == 'one-zero':
            self.to_application(message)
            print(f"receiver got {packet.seq_num}")

            # Send ACK
            ack_packet = Packet(data=ACK_PACKET_DATA, is_end=packet.is_end, seq_num=packet.seq_num)
            self.to_network(ack_packet)
