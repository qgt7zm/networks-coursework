import random

import station
import simtime

NUM_CHANNELS = 11
SEND_POWER = 20.0
SLOT_TIME = 0.1  # transmission delay is 10 ms, but 100 ms works better
NUM_SLOTS = 10


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
            slot = 0
            num_slots = 1

            # Try up to three times to send the packet successfully
            for i in range(0, 3):
                # Wait for given number of slots
                if slot > 0:
                    simtime.sleep(slot * SLOT_TIME)

                response = self.send(pkt, SEND_POWER, channel)
                if response == 'ACK':
                    break
                else:
                    if i == 2:
                        # Converged on a power value too low, double power
                        print(f'{self.id}: failed to send packet, dropping')
                    else:
                        # Raise power for next transmission
                        print(f'{self.id}: failed to send packet, will retry')

                    # If channel was busy, wait a random number of time slots
                    busy = self.sense(channel)
                    if busy:
                        print(f'channel {channel} is busy')

                        # Use exponential backoff to determine how many slots to choose from
                        num_slots *= 2
                        slot = random.randint(0, num_slots - 1)
                        print(f'{self.id}: waiting {slot} slots')


    # DO NOT CHANGE INIT
    def __init__(self, id, q_to_ap, q_to_station, interval):
        super().__init__(id, q_to_ap, q_to_station, interval)


