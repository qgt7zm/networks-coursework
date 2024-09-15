import config
from util import Packet, Message, cancel_timer, create_timer, now, trace

# Constants

NO_ACK_MODE = 'no-ack'
STOP_AND_WAIT_MODE = 'one-zero'
SLIDING_WINDOW_MODE = 'sliding-window'

ACK_PACKET_DATA = b'ACK'
INITIAL_SEQ_NUM = 0
ALPHA = 0.2

# Helper Functions

def debug(msg: str | None) -> None:
    if msg:
        trace('debug', msg)

# Class Implementations

class MySender:
    def __init__(self):
        self.seq_num = INITIAL_SEQ_NUM  # seq num of current packet
        self.waiting = False  # waiting for ACK
        self.resend_timer = None  # timer to resend
        self.avg_rtt = config.INITIAL_TIMEOUT  # average RTT
        self.last_acked = -1  # LAR
        self.last_sent = -1  # LFS
        self.timers = {}  # for resending packets not ACKed
        # Window = [LAR + 1, LAR + SWS]

    # Network Functions

    def from_application(self, message: Message) -> bool:
        packet = Packet(data=message.data, is_end=message.is_end, seq_num=self.seq_num)

        if config.MODE == NO_ACK_MODE:
            self.to_network(packet)
        elif config.MODE == STOP_AND_WAIT_MODE:
            if self.waiting:  # don't send if waiting
                return False

            self.send_packet(packet, f"sender sent {packet.seq_num}")
            self.waiting = True
        elif config.MODE == SLIDING_WINDOW_MODE:
            packet = Packet(data=message.data, is_end=message.is_end, seq_num=self.last_sent + 1)

            # Don't send if packet is after window
            window_start = self.last_acked + 1
            if packet.seq_num >= window_start + config.INITIAL_WINDOW:
                return False

            self.send_packet(packet, f"sender sent {packet.seq_num}", True)
            self.last_sent += 1
        return True

    def from_network(self, packet: Packet):
        if packet.data != ACK_PACKET_DATA:  # make sure we get ACK packet
            return

        if config.MODE == STOP_AND_WAIT_MODE:
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
        elif config.MODE == SLIDING_WINDOW_MODE:
            debug(f"sender got ACK {packet.ack_num}")

            # Update window
            self.last_acked = packet.ack_num
            self.ready_for_more_from_application()

    # Helper Functions

    def resend_packet(self, packet: Packet):
        if config.MODE == STOP_AND_WAIT_MODE and not self.waiting:  # don't resend if not waiting for ACK
            return
        elif config.MODE == SLIDING_WINDOW_MODE and packet.seq_num <= self.last_acked:  # don't resend if discarded
            return
        self.send_packet(packet, f"sender resent {packet.seq_num}")

    def send_packet(self, packet: Packet, msg: str=None, timer: bool=True):
        packet.timestamp = now()
        self.to_network(packet)
        debug(msg)

        # Start/reset wait timer
        if config.MODE == STOP_AND_WAIT_MODE:
            if self.resend_timer:
                cancel_timer(self.resend_timer)
            if timer:
                self.resend_timer = create_timer(
                    self.avg_rtt * 2.0,
                    lambda: self.resend_packet(packet),
                    f"resend {packet.seq_num}"
                )
        elif config.MODE == SLIDING_WINDOW_MODE:
            seq_num = packet.seq_num
            if seq_num in self.timers.keys():
                cancel_timer(self.timers.pop(seq_num))
            if timer:
                self.timers[seq_num] = create_timer(
                    self.avg_rtt * 2.0,
                    lambda: self.resend_packet(packet),
                    f"resend {packet.seq_num}"
                )

class MyReceiver:
    def __init__(self):
        self.seq_num = INITIAL_SEQ_NUM  # seq num of expected packet
        self.last_seq_num = None  # seq num of last received packet
        self.last_received = -1  # LFR
        self.last_accepted = -1  # LAF
        self.recent_packets = {}
        # Window = [LFR + 1, LAF]

    # Network Functions

    def from_network(self, packet: Packet) -> None:
        message = Message(data=packet.data, is_end=packet.is_end)

        if config.MODE == NO_ACK_MODE:
            self.to_application(message)
        elif config.MODE == STOP_AND_WAIT_MODE:
            # Forward new messages to application
            if packet.seq_num != self.last_seq_num:
                self.to_application(message)
                debug(f"receiver got {packet.seq_num}")

                self.last_seq_num = packet.seq_num
                self.seq_num = 1 - self.seq_num  # flip the sequence bit

                # Send ACK
                self.send_ack(packet, f"receiver sent ACK {packet.seq_num}")
            # Don't forward duplicate messages
            else:
                debug(f"receiver got duplicate {packet.seq_num}")

                # Resend ACK
                self.send_ack(packet, f"receiver resent ACK {packet.seq_num}")
        elif config.MODE == SLIDING_WINDOW_MODE:
            # Ignore packet if out of window
            window_start = self.last_received + 1
            window_end = max(self.last_received + config.INITIAL_WINDOW, self.last_accepted)  # edge case for first frame
            if packet.seq_num > window_end:
                debug(f"receiver got {packet.seq_num} outside window {window_start}-{window_end}")
                return
            elif packet.seq_num < window_start:
                # Resend missing ACKs even if packet out of window
                self.send_ack(packet, f"receiver resent ACK {self.last_received}")

            # Reply if packet is next in sequence
            if packet.seq_num == window_start:
                self.to_application(message)
                debug(f"receiver got {packet.seq_num}")
                self.last_received += 1

                # Find last in-order packet stored
                for i in range(self.last_received + 1, self.last_accepted + 1):
                    if i not in self.recent_packets.keys():
                        break

                    # Send packet to application
                    packet = self.recent_packets.pop(i)
                    message = Message(data=packet.data, is_end=packet.is_end)
                    self.to_application(message)
                    self.last_received += 1
                    debug(f"receiver popped {packet.seq_num}")

                # Send latest ACK and update window
                self.send_ack(packet, f"receiver sent ACK {packet.seq_num}")
                self.last_accepted = self.last_received + config.INITIAL_WINDOW
                debug(f"receiver set window {self.last_received + 1}-{self.last_accepted}")
            # Store packet if out-of-order
            elif packet.seq_num > window_start:
                self.recent_packets[packet.seq_num] = packet
                debug(f"receiver got out-of-order {packet.seq_num}, window {window_start}-{window_end}")

    # Helper Functions

    def send_ack(self, packet:Packet, msg: str=None):
        ack_packet = Packet(data=ACK_PACKET_DATA, is_end=packet.is_end, ack_num=packet.seq_num, timestamp=packet.timestamp)
        self.to_network(ack_packet)
        debug(msg)
