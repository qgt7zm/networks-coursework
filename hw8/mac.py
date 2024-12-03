"""
Eric Weng (qgt7zm)
CS 4457
Tue 12/3/24
Wireless Assignment

Methodology: The MAC implementation uses a combination of carrier-sense collision detection
and and carrier-sense collision avoidance.

1. First, channels were uniformly divided among stations by ID so that each channel would be
expected to have the same frequency of collisions.

2. Next, if the station detects a collision after an unsuccessful send, it waits a random
number of slots before retransmitting. Every time such a collision is detected, the maximum
number of slots doubles.

3. Lastly, if the channel is still busy before sending, the station waits until the channel
is no longer busy.

4. Although the transmission delay was given to be 10 ms, a slot duration of 100 ms was found
to work better. Time slots longer would slow down the protocol, while time slots shorter would
cause too many collisions.

5. Transmission power was set to 20 dB, as adjustments to transmission power did not appear
to impact the frequency of collisions. However, power values too low often caused messages
to not make it to the access point.

Testing: The program was tested by running the program with 20 packets per second and 150
packets received using simulated time.
"""

import random

import station
import simtime

NUM_CHANNELS = 11
SEND_POWER = 20.0
SLOT_TIME = 0.1  # transmission delay is 10 ms, but 100 ms works better


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
            num_slots = 1

            # Try up to three times to send the packet successfully
            for i in range(0, 3):
                # Collision avoidance: If channel is still busy, wait for one slot
                while self.sense(channel):
                    print(f'channel {channel} is busy before sending')
                    simtime.sleep(SLOT_TIME)

                response = self.send(pkt, SEND_POWER, channel)
                if response == 'ACK':
                    break
                else:
                    if i == 2:
                        print(f'{self.id}: failed to send packet, dropping')
                    else:
                        print(f'{self.id}: failed to send packet, will retry')

                    # Collision Detection: If channel was busy, wait before retransmitting
                    if self.sense(channel):
                        print(f'channel {channel} was busy while sending')

                        # Use exponential backoff to determine how many slots to choose from
                        num_slots *= 2
                        self.wait(num_slots)

    # DO NOT CHANGE INIT
    def __init__(self, id, q_to_ap, q_to_station, interval):
        super().__init__(id, q_to_ap, q_to_station, interval)

    # Wait for the given number of time slots
    def wait(self, num_slots):
        slot = random.randint(0, num_slots - 1)
        if slot > 0:
            print(f'{self.id}: waiting {slot} slots')
            simtime.sleep(slot * SLOT_TIME)


