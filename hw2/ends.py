import config
from util import Packet, Message, cancel_timer, create_timer, now, trace

# Constants

ACK_PACKET_DATA = b'ACK'
INITIAL_SEQ_NUM = 0

# Class Implementations

class MySender:
    def __init__(self):
        self.seq_num = INITIAL_SEQ_NUM  # seq num of current packet
        self.waiting = False  # waiting for ACK
        self.resend_timer = None  # timer to resend

    # Network Functions

    def from_application(self, message: Message) -> bool:
        packet = Packet(data=message.data, is_end=message.is_end, seq_num=self.seq_num)

        if config.MODE == 'no-ack':
            self.to_network(packet)
        elif config.MODE == 'one-zero':
            if self.waiting:  # don't send if waiting
                return False

            self.send_packet(packet, f"sender sent {packet.seq_num}")
            self.waiting = True
        return True

    def from_network(self, packet: Packet):
        if packet.data != ACK_PACKET_DATA:  # make sure we get ACK packet
            return

        if config.MODE == 'one-zero':
            if packet.seq_num != self.seq_num:  # make sure ACK has correct seq num
                return

            print(f"sender got ACK {packet.seq_num}")
            self.waiting = False
            self.seq_num = 1 - self.seq_num  # flip the sequence bit
            self.ready_for_more_from_application()  # get the next message

    # Helper Functions

    def resend_packet(self, packet: Packet):
        if not self.waiting:  # only resend if still waiting
            return
        self.send_packet(packet, f"sender resent {packet.seq_num}")

    def send_packet(self, packet: Packet, debug: str=None):
        self.to_network(packet)
        if debug:
            print(debug)

        # Start/reset wait timer
        if self.resend_timer:
            cancel_timer(self.resend_timer)
        self.resend_timer = create_timer(
            config.INITIAL_TIMEOUT,
            lambda: self.resend_packet(packet),
            f"resend {packet.seq_num}"
        )

class MyReceiver:
    def __init__(self):
        self.seq_num = INITIAL_SEQ_NUM  # seq num of expected packet
        self.last_seq_num = None  # seq num of last received packet

    # Network Functions

    def from_network(self, packet: Packet) -> None:
        message = Message(data=packet.data, is_end=packet.is_end)

        if config.MODE == 'no-ack':
            self.to_application(message)
        elif config.MODE == 'one-zero':
            if packet.seq_num != self.last_seq_num:  # forward new messages
                self.to_application(message)
                print(f"receiver got {packet.seq_num}")

                self.last_seq_num = packet.seq_num
                self.seq_num = 1 - self.seq_num  # flip the sequence bit

                # Send ACK
                self.send_ack(packet.is_end, packet.seq_num, f"receiver sent ACK {packet.seq_num}")
            else:  # don't forward duplicate messages
                print(f"receiver got duplicate {packet.seq_num}")

                # Resend ACK
                self.send_ack(packet.is_end, self.last_seq_num, f"receiver resent ACK {packet.seq_num}")

    # Helper Functions

    def send_ack(self, is_end:bool, seq_num: int, debug: str=None):
        ack_packet = Packet(data=ACK_PACKET_DATA, is_end=is_end, seq_num=seq_num)
        self.to_network(ack_packet)
        if debug:
            print(debug)
