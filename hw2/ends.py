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
            seq_num = (self.last_sent + 1) % config.MAXIMUM_SEQUENCE
            packet = Packet(data=message.data, is_end=message.is_end, seq_num=seq_num)

            # Don't send if packet is after window
            window_start = (self.last_acked + 1) % config.MAXIMUM_SEQUENCE
            window_end = (self.last_acked + config.INITIAL_WINDOW) % config.MAXIMUM_SEQUENCE

            if window_start <= window_end:  # window is normal
                if seq_num > window_end or seq_num < window_start:
                    debug(f"did not send {seq_num}")
                    return False
            else:  # window is split
                if window_end < seq_num < window_start:
                    debug(f"did not send {seq_num}")
                    return False

            self.send_packet(packet, f"sender sent {seq_num} {message.data}")
            self.last_sent = seq_num
        return True

    def from_network(self, packet: Packet):
        if packet.data != ACK_PACKET_DATA:  # make sure we get ACK packet
            return

        # Calculate new average RTT
        rtt = now() - packet.timestamp
        # debug(f"rtt = {rtt}")
        self.avg_rtt = rtt * ALPHA + self.avg_rtt * (1 - ALPHA)
        # debug(f"new avg = {self.avg_rtt}")

        if config.MODE == STOP_AND_WAIT_MODE:
            if packet.ack_num != self.seq_num:  # make sure ACK has correct seq num
                return

            debug(f"sender got ACK {packet.ack_num}")

            # Get the next message
            self.waiting = False
            self.seq_num = 1 - self.seq_num  # flip the sequence bit
            self.ready_for_more_from_application()
        elif config.MODE == SLIDING_WINDOW_MODE:
            debug(f"sender got ACK {packet.ack_num}")

            # Update window
            self.last_acked = packet.ack_num

            window_start = (self.last_acked + 1) % config.MAXIMUM_SEQUENCE
            window_end = (self.last_acked + config.INITIAL_WINDOW) % config.MAXIMUM_SEQUENCE
            debug(f"sender window {window_start}-{window_end}")

            self.ready_for_more_from_application()

    # Helper Functions

    def resend_packet(self, packet: Packet) -> None:
        seq_num = packet.seq_num

        if config.MODE == STOP_AND_WAIT_MODE and not self.waiting:  # don't resend if not waiting for ACK
            return
        elif config.MODE == SLIDING_WINDOW_MODE:  # don't resend if discarded
            window_start = self.last_acked + 1
            window_end = self.last_acked + config.INITIAL_WINDOW

            if window_start <= window_end:  # window is normal
                if seq_num < window_start:
                    debug(f"don't resend {packet.seq_num}")
                    return
            else:  # window is split
                if window_end < seq_num < window_start:
                    debug(f"don't resend {packet.seq_num}")
                    return
        self.send_packet(packet, f"sender resent {packet.seq_num}")

    def send_packet(self, packet: Packet, msg: str=None, timer: bool=True) -> None:
        packet.timestamp = now()
        self.to_network(packet)
        debug(msg)

        # Start/reset wait timer
        seq_num = packet.seq_num
        packet_timer = create_timer(
            self.avg_rtt * 2.0,
            lambda: self.resend_packet(packet),
            f"resend {seq_num}"
        )

        if config.MODE == STOP_AND_WAIT_MODE:
            if self.resend_timer:
                cancel_timer(self.resend_timer)
            if timer:
                self.resend_timer = packet_timer
        elif config.MODE == SLIDING_WINDOW_MODE:
            if seq_num in self.timers.keys():
                cancel_timer(self.timers.pop(seq_num))
            if timer:
                self.timers[seq_num] = packet_timer

class MyReceiver:
    def __init__(self):
        self.seq_num = INITIAL_SEQ_NUM  # seq num of expected packet
        self.last_seq_num = None  # seq num of last received packet
        self.last_received = -1  # LFR
        self.last_accepted = self.last_received + config.INITIAL_WINDOW  # LAF
        self.recent_packets = {}  # packets received out-of-order
        # Window = [LFR + 1, LAF]

    # Network Functions

    def from_network(self, packet: Packet) -> None:
        message = Message(data=packet.data, is_end=packet.is_end)

        if config.MODE == NO_ACK_MODE:
            self.to_application(message)
        # Forward new messages to application
        elif config.MODE == STOP_AND_WAIT_MODE:
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
            window_start = (self.last_received + 1) % config.MAXIMUM_SEQUENCE
            window_end = self.last_accepted
            seq_num = packet.seq_num

            # Ignore packet if out of window
            if window_start <= window_end:  # if window is normal
                if seq_num > window_end:
                    debug(f"receiver got {seq_num} outside window {window_start}-{window_end}")
                    return
                # Resend missing ACKs even if packet out of window
                elif seq_num < window_start:
                    self.send_ack(packet, f"receiver resent ACK {self.last_received}")
            else:
                if window_start < packet.seq_num < window_end:
                    debug(f"receiver got {packet.seq_num} outside window {self.last_received + 1}-{config.MAXIMUM_SEQUENCE - 1}, {0}-{self.last_accepted}")
                    return

            # Reply if packet is next in sequence
            if seq_num == window_start:
                self.to_application(message)
                debug(f"receiver got {seq_num} {message.data}")

                # Find last in-order packet stored
                for i in range(seq_num + 1, self.last_accepted + 1):
                    if i not in self.recent_packets.keys():
                        break

                    # Send packet to application
                    packet = self.recent_packets.pop(i)
                    message = Message(data=packet.data, is_end=packet.is_end)
                    self.to_application(message)
                    debug(f"receiver popped {packet.seq_num} {message.data}")

                # Send latest ACK and update window
                self.send_ack(packet, f"receiver sent ACK {packet.seq_num}")
                self.last_received = packet.seq_num
                self.last_accepted = (self.last_received + config.INITIAL_WINDOW) % config.MAXIMUM_SEQUENCE

                window_start = (self.last_received + 1) % config.MAXIMUM_SEQUENCE
                window_end = self.last_accepted
                if window_start <= window_end:  # if window is normal
                    debug(f"receiver window {window_start}-{window_end}")
                else:  # if window is split
                    debug(f"receiver window {window_start}-{config.MAXIMUM_SEQUENCE - 1}, {0}-{window_end}")
            # Store packet if out-of-order
            elif seq_num > window_start:
                self.recent_packets[seq_num] = packet
                debug(f"receiver got out-of-order {seq_num}, window {window_start}-{window_end}")

    # Helper Functions

    def send_ack(self, packet:Packet, msg: str=None):
        ack_packet = Packet(data=ACK_PACKET_DATA, is_end=packet.is_end, ack_num=packet.seq_num, timestamp=packet.timestamp)
        self.to_network(ack_packet)
        debug(msg)
