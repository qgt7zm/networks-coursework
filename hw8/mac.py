
import random

import station

NUM_CHANNELS = 11


class NullMac(station.Station):
    '''
    `NullMac` is essentially having no MAC protocol. The node sends at 0 dB on
    channel 1 whenever it has a packet ready to send, and tries up to two
    retries if it doesn't receive an ACK.

    The node makes no attempt to avoid collisions.
    '''
    def __init__(self, id, q_to_ap, q_to_station, interval):
        super().__init__(id, q_to_ap, q_to_station, interval)

    def run(self):
        # Continuously send packets
        while True:
            # Block until there is a packet ready to send
            pkt = self.wait_for_next_transmission()

            # Try up to three times to send the packet successfully
            for i in range(0, 3):
                # send packet on channel 1 with power 0.0 dBm
                # possible channels are 1 through 11 (inclusive)
                # possible tx powers range up to 20 dBm
                response = self.send(pkt, 0.0, 1)

                # If we get an ACK, we are done with this packet. If all of our
                # retries fail then we just consider this packet lost and wait
                # for the next one.
                if response == 'ACK':
                    break
                else:
                    print(f'{self.id}: failed to send packet, will retry')


class YourMac(station.Station):
    '''
    `YourMac` is your own custom MAC designed as you see fit.

    The sender should use up to two retransmissions if an ACK is not received.
    '''
    def run(self):
        # Divide channels evenly among station IDs
        channel = (self.id % NUM_CHANNELS) + 1  # 1-11
        print(f'{self.id}: using channel {channel}')

        while True:
            # Block until there is a packet ready to send
            pkt = self.wait_for_next_transmission()

            # Implement your MAC protocol here.
            # Try up to three times to send the packet successfully
            for i in range(0, 3):
                response = self.send(pkt, 10.0, channel)

                # If we get an ACK, we are done with this packet. If all of our
                # retries fail then we just consider this packet lost and wait
                # for the next one.
                if response == 'ACK':
                    break
                else:
                    print(f'{self.id}: failed to send packet, will retry')



    # DO NOT CHANGE INIT
    def __init__(self, id, q_to_ap, q_to_station, interval):
        super().__init__(id, q_to_ap, q_to_station, interval)


