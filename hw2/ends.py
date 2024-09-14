import config
from util import Packet, Message, cancel_timer, create_timer, now, trace

# Constants

NO_ACK_MODE = 'no-ack'
STOP_AND_WAIT = 'one-zero'

ACK_PACKET_DATA = b'ACK'
INITIAL_SEQ_NUM = 0
ALPHA = 0.2

# Helper Functions

def debug(msg: str | None) -> None:
    if msg:  # Print if debug mode is on
        trace('debug', msg)

# Class Implementations

class MySender:
    def __init__(self):
        self.seq_num = INITIAL_SEQ_NUM  # seq num of current packet
        self.waiting = False  # waiting for ACK
        self.resend_timer = None  # timer to resend
        self.avg_rtt = config.INITIAL_TIMEOUT  # average RTT

    # Network Functions

    def from_application(self, message: Message) -> bool:
        packet = Packet(data=message.data, is_end=message.is_end, seq_num=self.seq_num)

        if config.MODE == NO_ACK_MODE:
            self.to_network(packet)
        elif config.MODE == STOP_AND_WAIT:
            if self.waiting:  # don't send if waiting
                return False

            self.send_packet(packet, f"sender sent {packet.seq_num}")
            self.waiting = True
        return True

    def from_network(self, packet: Packet):
        if packet.data != ACK_PACKET_DATA:  # make sure we get ACK packet
            return

        if config.MODE == 'one-zero':
            if packet.ack_num != self.seq_num:  # make sure ACK has correct seq num
                return

            debug(f"sender got ACK {packet.ack_num}")

            # Calculate new average RTT
            rtt = now() - packet.timestamp
            debug(f"rtt = {rtt}")
            self.avg_rtt = rtt * ALPHA + self.avg_rtt * (1 - ALPHA)
            debug(f"new avg = {self.avg_rtt}")

            # Get the next message
            self.waiting = False
            self.seq_num = 1 - self.seq_num  # flip the sequence bit
            self.ready_for_more_from_application()

    # Helper Functions

    def resend_packet(self, packet: Packet):
        if not self.waiting:  # only resend if still waiting
            return
        self.send_packet(packet, f"sender resent {packet.seq_num}")

    def send_packet(self, packet: Packet, msg: str=None):
        packet.timestamp = now()
        self.to_network(packet)
        debug(msg)

        # Start/reset wait timer
        if self.resend_timer:
            cancel_timer(self.resend_timer)
        self.resend_timer = create_timer(
            self.avg_rtt * 2.0,
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

        if config.MODE == NO_ACK_MODE:
            self.to_application(message)
        elif config.MODE == STOP_AND_WAIT:
            if packet.seq_num != self.last_seq_num:  # forward new messages
                self.to_application(message)
                debug(f"receiver got {packet.seq_num}")

                self.last_seq_num = packet.seq_num
                self.seq_num = 1 - self.seq_num  # flip the sequence bit

                # Send ACK
                self.send_ack(packet, f"receiver sent ACK {packet.seq_num}")
            else:  # don't forward duplicate messages
                debug(f"receiver got duplicate {packet.seq_num}")

                # Resend ACK
                self.send_ack(packet, f"receiver resent ACK {packet.seq_num}")

    # Helper Functions

    def send_ack(self, packet:Packet, msg: str=None):
        ack_packet = Packet(data=ACK_PACKET_DATA, is_end=packet.is_end, ack_num=packet.seq_num, timestamp=packet.timestamp)
        self.to_network(ack_packet)
        debug(msg)
